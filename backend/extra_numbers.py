"""Extra phone numbers: one per agent (each agent = a branch or a company). Billed monthly on the tenant's Stripe subscription."""
import asyncio
import logging
import os

import stripe
from bson import ObjectId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import billing as B
import emailer
import phone_numbers as N
import zadarma as Z
from db import db
from extra_routes import CurrentUser, require_admin
from fastapi import Depends
from models import now_iso

log = logging.getLogger("vozlead.extra_numbers")
router = APIRouter(prefix="/api")
PRICE = {"ES": ("eur", 1000), "CL": ("clp", 13000)}
OPEN = ["comprando", "activo", "pendiente_aprobacion", "error"]


def price_label(country: str) -> str:
    cur, amt = PRICE.get(country, PRICE["ES"])
    return f"{amt:,} CLP".replace(",", ".") if cur == "clp" else f"{amt / 100:.0f} €"


def _out(r: dict) -> dict:
    return {"id": str(r["_id"]), "extra": bool(r.get("extra")), "agent_id": r.get("agent_id") if r.get("extra") else r.get("inbound_agent_id"),
            "number": r.get("number"), "status": r.get("status"), "country": r.get("country"), "error": r.get("error", ""),
            "price": price_label(r.get("country", "ES")) if r.get("extra") else "Incluido en tu plan"}


async def _agent(user_id: str, agent_id: str) -> dict:
    a = await db.agents.find_one({"_id": ObjectId(agent_id), "tenant_id": user_id}) if ObjectId.is_valid(agent_id) else None
    if not a:
        raise HTTPException(404, "Agente no encontrado")
    return a


async def _product(c, mode: str) -> str:
    key = f"extra_number_product_{mode}"
    doc = await db.platform_settings.find_one({"_id": "stripe"}) or {}
    if doc.get(key):
        return doc[key]
    p = await asyncio.to_thread(c.v1.products.create, {"name": "Número adicional VozLeads"})
    await db.platform_settings.update_one({"_id": "stripe"}, {"$set": {key: p["id"]}}, upsert=True)
    return p["id"]


async def _charge(user: dict, country: str) -> str:
    """Add the extra number to the tenant's subscription and charge the prorated part now. Returns the item id."""
    if user.get("role") == "admin":
        return ""
    if not user.get("stripe_subscription_id") or user.get("billing_status") != "active":
        raise HTTPException(409, "Necesitas un plan activo para añadir números. Contrátalo desde «Mi plan».")
    mode = user.get("stripe_mode", "live")
    c, _, proxy = await B.client(mode)
    if proxy:
        raise HTTPException(409, "Para cobrar números adicionales conecta tu cuenta de Stripe propia en Super Admin.")
    cur, amt = PRICE.get(country, PRICE["ES"])
    try:
        item = await asyncio.to_thread(c.v1.subscription_items.create, {
            "subscription": user["stripe_subscription_id"], "proration_behavior": "always_invoice",
            "metadata": {"kind": "extra_number"},
            "price_data": {"currency": cur, "unit_amount": amt, "recurring": {"interval": "month"}, "product": await _product(c, mode)}})
    except stripe.error.StripeError as e:
        raise HTTPException(402, f"No se pudo cobrar el número: {e.user_message or str(e)[:160]}")
    return item["id"]


async def _uncharge(user: dict, item_id: str):
    if not item_id:
        return
    c, _, _ = await B.client(user.get("stripe_mode", "live"))
    try:
        await asyncio.to_thread(c.v1.subscription_items.delete, item_id, {"proration_behavior": "none"})
    except stripe.error.StripeError as e:
        log.warning("Could not remove extra number item %s: %s", item_id, e)


@router.get("/numbers")
async def list_numbers(user=CurrentUser):
    rows = await db.tenant_numbers.find({"tenant_id": user["id"], "status": {"$ne": "liberado"}}).sort("created_at", 1).to_list(50)
    return {"numbers": [_out(r) for r in rows], "prices": {c: price_label(c) for c in PRICE}}


class ExtraIn(BaseModel):
    agent_id: str = Field(min_length=24, max_length=24)


@router.post("/numbers/extra")
async def add_extra(body: ExtraIn, user=CurrentUser):
    agent = await _agent(user["id"], body.agent_id)
    country = agent.get("country", "ES")
    if await db.tenant_numbers.find_one({"tenant_id": user["id"], "extra": True, "agent_id": body.agent_id, "status": {"$in": OPEN}}):
        raise HTTPException(409, "Este agente ya tiene su propio número.")
    item = await _charge(user, country)
    cfg = await Z.creds()
    auto = bool(cfg.get("auto_provision") and cfg.get("key"))
    doc = {"tenant_id": user["id"], "extra": True, "agent_id": body.agent_id, "country": country, "stripe_item_id": item,
           "status": "comprando" if auto else "pendiente_aprobacion", "created_at": now_iso(), "updated_at": now_iso()}
    doc["_id"] = (await db.tenant_numbers.insert_one(doc)).inserted_id
    if auto:
        await N.provision(user["id"], doc["_id"])
    else:
        admin = await db.users.find_one({"role": "admin"}, {"email": 1})
        if admin:
            await emailer.send(admin["email"], "Número adicional pendiente de aprobar", "Un cliente ha pedido un número adicional", [
                ("Cliente", user.get("business_name") or user["email"]), ("Agente", agent["name"]), ("País", country),
                ("Precio", f"{price_label(country)}/mes")], os.environ["APP_PUBLIC_URL"] + "/app/admin")
    return _out(await db.tenant_numbers.find_one({"_id": doc["_id"]}))


class AssignIn(BaseModel):
    agent_id: str = Field("", max_length=24)


async def _mine(user: dict, num_id: str) -> dict:
    r = await db.tenant_numbers.find_one({"_id": ObjectId(num_id), "tenant_id": user["id"]}) if ObjectId.is_valid(num_id) else None
    if not r:
        raise HTTPException(404, "Número no encontrado")
    return r


@router.put("/numbers/{num_id}")
async def assign(num_id: str, body: AssignIn, user=CurrentUser):
    r = await _mine(user, num_id)
    if body.agent_id:
        a = await _agent(user["id"], body.agent_id)
        if a.get("country", "ES") != r.get("country"):
            raise HTTPException(422, "Ese agente es de otro país que el número.")
        if r.get("extra") and await db.tenant_numbers.find_one({"_id": {"$ne": r["_id"]}, "tenant_id": user["id"], "extra": True,
                                                                  "agent_id": body.agent_id, "status": {"$in": OPEN}}):
            raise HTTPException(409, "Ese agente ya tiene otro número.")
    field = "agent_id" if r.get("extra") else "inbound_agent_id"
    await db.tenant_numbers.update_one({"_id": r["_id"]}, {"$set": {field: body.agent_id or None, "updated_at": now_iso()}})
    return _out(await db.tenant_numbers.find_one({"_id": r["_id"]}))


@router.delete("/numbers/{num_id}")
async def remove_extra(num_id: str, user=CurrentUser):
    r = await _mine(user, num_id)
    if not r.get("extra"):
        raise HTTPException(409, "El número incluido en tu plan no se puede dar de baja aquí.")
    if r.get("status") == "activo" or r.get("status") == "error":
        await N.release(user["id"], r["_id"])
    await db.tenant_numbers.update_one({"_id": r["_id"]}, {"$set": {"status": "liberado", "released_at": now_iso()}})
    await _uncharge(user, r.get("stripe_item_id", ""))
    return {"ok": True}


@router.get("/admin/numbers/extra")
async def pending_extra(user=Depends(require_admin)):
    rows = await db.tenant_numbers.find({"extra": True, "status": {"$in": ["pendiente_aprobacion", "error"]}}).to_list(200)
    users = {str(u["_id"]): u async for u in db.users.find({"_id": {"$in": [ObjectId(r["tenant_id"]) for r in rows]}}, {"business_name": 1, "email": 1})}
    return [{**_out(r), "business": (users.get(r["tenant_id"]) or {}).get("business_name") or (users.get(r["tenant_id"]) or {}).get("email")} for r in rows]


@router.post("/admin/numbers/extra/{num_id}/approve")
async def approve_extra(num_id: str, user=Depends(require_admin)):
    r = await db.tenant_numbers.find_one({"_id": ObjectId(num_id), "extra": True}) if ObjectId.is_valid(num_id) else None
    if not r:
        raise HTTPException(404, "Número no encontrado")
    if r["status"] not in ("pendiente_aprobacion", "error"):
        raise HTTPException(409, "Este número ya está activo o en compra.")
    await db.tenant_numbers.update_one({"_id": r["_id"]}, {"$set": {"status": "pendiente"}})
    await N.provision(r["tenant_id"], r["_id"])
    return _out(await db.tenant_numbers.find_one({"_id": r["_id"]}))
