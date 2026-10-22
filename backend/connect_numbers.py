"""Super admin: connect numbers already owned in the platform's Zadarma account to a client (main line or one agent)."""
import re

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import extra_numbers as E
import kyc
import phone_numbers as N
import vapi
import zadarma as Z
from db import db
from extra_routes import require_admin
from models import now_iso

router = APIRouter(prefix="/api/admin/zadarma")
PREFIX = {"34": "ES", "56": "CL"}


def _norm(n) -> str:
    return "+" + re.sub(r"\D", "", str(n or ""))


async def _in_use() -> dict:
    used = {r["number"]: r["tenant_id"] async for r in db.tenant_numbers.find(
        {"number": {"$nin": [None, ""]}, "status": {"$in": E.OPEN}}, {"number": 1, "tenant_id": 1})}
    plat = (await db.platform_settings.find_one({"_id": "platform_inbound"}) or {}).get("number")
    if plat:
        used[_norm(plat)] = "plataforma"
    return used


@router.get("/my-numbers")
async def my_numbers(user=Depends(require_admin)):
    try:
        rows = await Z.my_numbers()
    except Z.ZadarmaError as e:
        raise HTTPException(424, str(e))
    used = await _in_use()
    names = {str(u["_id"]): u.get("business_name") or u["email"] async for u in db.users.find(
        {"_id": {"$in": [ObjectId(t) for t in used.values() if ObjectId.is_valid(t)]}}, {"business_name": 1, "email": 1})}
    out = []
    for r in rows:
        n = _norm(r.get("number"))
        owner = used.get(n)
        out.append({"number": n, "country": PREFIX.get(n[1:3], ""), "description": r.get("description") or r.get("number_name") or "",
                    "status": r.get("status", ""), "stop_date": r.get("stop_date", ""),
                    "used_by": "Número de la plataforma" if owner == "plataforma" else names.get(owner, "") if owner else ""})
    return out


@router.get("/connect-options/{tid}")
async def connect_options(tid: str, user=Depends(require_admin)):
    u = await db.users.find_one({"_id": ObjectId(tid)}) if ObjectId.is_valid(tid) else None
    if not u:
        raise HTTPException(404, "Cliente no encontrado")
    main = await N.record(tid)
    return {"kyc_ok": await kyc.group_for(tid) is not None, "has_main": bool(main and main.get("status") == "activo"),
            "main_number": (main or {}).get("number") if main and main.get("status") == "activo" else "",
            "price": E.price_label(u.get("country", "ES")),
            "agents": [{"id": str(a["_id"]), "name": a["name"], "role": a.get("role", "")}
                       async for a in db.agents.find({"tenant_id": tid}, {"name": 1, "role": 1})]}


class ConnectIn(BaseModel):
    number: str = Field(min_length=6, max_length=20)
    tenant_id: str
    agent_id: str = ""


@router.post("/connect")
async def connect(body: ConnectIn, user=Depends(require_admin)):
    number = _norm(body.number)
    u = await db.users.find_one({"_id": ObjectId(body.tenant_id)}) if ObjectId.is_valid(body.tenant_id) else None
    if not u:
        raise HTTPException(404, "Cliente no encontrado")
    if u.get("role") != "admin" and await kyc.group_for(body.tenant_id) is None:
        raise HTTPException(409, "Este cliente aún no tiene sus documentos de identidad aprobados. Revísalos en «Documentos de los titulares».")
    try:
        owned = {_norm(r.get("number")) for r in await Z.my_numbers()}
    except Z.ZadarmaError as e:
        raise HTTPException(424, str(e))
    if number not in owned:
        raise HTTPException(404, "Ese número no está en tu cuenta de Zadarma.")
    if number in await _in_use():
        raise HTTPException(409, "Ese número ya está en uso en VozLeads.")
    country = PREFIX.get(number[1:3], u.get("country", "ES"))
    tid = body.tenant_id
    if body.agent_id:
        agent = await E._agent(tid, body.agent_id)
        if await db.tenant_numbers.find_one({"tenant_id": tid, "extra": True, "agent_id": body.agent_id, "status": {"$in": E.OPEN}}):
            raise HTTPException(409, f"{agent['name']} ya tiene un número propio.")
        bill = u.get("country", "ES")
        item = await E._charge(u, bill)
        res = await db.tenant_numbers.insert_one({"tenant_id": tid, "extra": True, "agent_id": body.agent_id, "country": bill,
                                                  "number": number, "status": "comprando", "stripe_item_id": item,
                                                  "created_at": now_iso(), "updated_at": now_iso(), "source": "zadarma_existente"})
        filt, inbound = {"_id": res.inserted_id}, body.agent_id
    else:
        main = await N.record(tid)
        if main and main.get("status") == "activo":
            raise HTTPException(409, f"Este cliente ya tiene su número principal ({main.get('number')}). Elige un agente para conectarlo como adicional.")
        filt = {"_id": main["_id"]} if main else {"tenant_id": tid, **N.PRIMARY}
        await db.tenant_numbers.update_one(filt, {"$set": {"tenant_id": tid, "country": country, "number": number, "status": "comprando",
                                                           "error": "", "updated_at": now_iso(), "source": "zadarma_existente"},
                                                  "$setOnInsert": {"created_at": now_iso()}}, upsert=True)
        filt = {"_id": (await db.tenant_numbers.find_one(filt))["_id"]}
        inbound = (main or {}).get("inbound_agent_id") or await N._default_agent(tid, country)
    try:
        await N.activate(filt, u, number, inbound)
    except (Z.ZadarmaError, vapi.VapiError) as e:
        await db.tenant_numbers.update_one(filt, {"$set": {"status": "error", "error": str(e)[:300]}})
        raise HTTPException(424, f"No se pudo conectar: {str(e)[:250]}. Puedes reintentar o rechazarlo (se devuelve el cobro).")
    return {"ok": True, "number": number, "extra": bool(body.agent_id)}
