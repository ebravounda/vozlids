"""Super admin «Pagos»: Stripe invoices (paid / pending / overdue), renewal dates per account, charge now, send card link."""
import asyncio
import os
from datetime import datetime, timezone

import stripe
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import billing as B
import emailer
from db import db
from extra_routes import require_admin

router = APIRouter(prefix="/api/admin/payments")


def _iso(ts) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat() if ts else ""


def _period_end(sub) -> int:
    items = (sub.get("items") or {}).get("data") or []
    return sub.get("current_period_end") or (items[0].get("current_period_end") if items else 0) or 0


async def _mode_data(mode: str) -> dict:
    c, s, proxy = await B.client(mode)
    if mode == "test" and not s.get("test_key"):
        return {}
    if proxy:
        return {"error": "Conecta tu cuenta de Stripe en Super admin → Stripe para ver y cobrar los pagos."}
    try:
        inv = await asyncio.to_thread(c.v1.invoices.list, {"limit": 100})
        subs = await asyncio.to_thread(c.v1.subscriptions.list, {"limit": 100, "status": "all"})
    except stripe.error.StripeError as e:
        return {"error": e.user_message or str(e)[:200]}
    return {"invoices": [dict(i, _mode=mode) for i in inv.data], "subs": {x["id"]: x for x in subs.data}}


@router.get("")
async def payments(user=Depends(require_admin)):
    data = {m: await _mode_data(m) for m in ("live", "test")}
    users = {u.get("stripe_customer_id"): u async for u in db.users.find({"stripe_customer_id": {"$nin": [None, ""]}})}
    plans = {str(p["_id"]): p["name"] async for p in db.plans.find({}, {"name": 1})}
    now = datetime.now(timezone.utc).timestamp()
    invoices = []
    for m, d in data.items():
        for i in d.get("invoices", []):
            u = users.get(i.get("customer")) or {}
            st = i.get("status")
            overdue = st == "open" and i.get("due_date") and i["due_date"] < now
            invoices.append({"id": i["id"], "mode": m, "account": u.get("business_name") or i.get("customer_email") or "",
                             "user_id": str(u["_id"]) if u else "", "amount": (i.get("amount_paid") if st == "paid" else i.get("amount_due")) or 0,
                             "currency": i.get("currency"), "status": "vencida" if overdue else {"paid": "pagada", "open": "pendiente",
                             "uncollectible": "impagada", "void": "anulada", "draft": "borrador"}.get(st, st),
                             "created": _iso(i.get("created")), "due": _iso(i.get("due_date")), "url": i.get("hosted_invoice_url") or ""})
    accounts = []
    async for u in db.users.find({"role": "business"}).sort("business_name", 1):
        sub = (data.get(u.get("stripe_mode", "live")) or {}).get("subs", {}).get(u.get("stripe_subscription_id") or "")
        accounts.append({"id": str(u["_id"]), "name": u.get("business_name") or u["email"], "email": u["email"], "country": u.get("country", "ES"),
                         "plan": plans.get(u.get("plan_id") or "", ""), "plan_id": u.get("plan_id") or "", "billing_status": u.get("billing_status") or "",
                         "stripe": bool(sub), "sub_status": (sub or {}).get("status", ""), "renews": _iso(_period_end(sub)) if sub else "",
                         "cancel_at_end": bool((sub or {}).get("cancel_at_period_end"))})
    paid = [i for i in invoices if i["status"] == "pagada"]
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    return {"invoices": invoices, "accounts": accounts, "errors": {m: d["error"] for m, d in data.items() if d.get("error")},
            "totals": {"paid_month": sum(1 for i in paid if i["created"].startswith(month)),
                       "pending": sum(1 for i in invoices if i["status"] in ("pendiente", "vencida")),
                       "overdue": sum(1 for i in invoices if i["status"] == "vencida")}}


@router.post("/invoices/{inv_id}/pay")
async def charge_now(inv_id: str, mode: str = "live", user=Depends(require_admin)):
    c, _, _ = await B.client("test" if mode == "test" else "live")
    try:
        i = await asyncio.to_thread(c.v1.invoices.pay, inv_id)
    except stripe.error.StripeError as e:
        raise HTTPException(402, f"No se pudo cobrar: {e.user_message or str(e)[:200]}")
    return {"ok": True, "status": i.get("status")}


class LinkIn(BaseModel):
    user_id: str
    plan_id: str


@router.post("/send-link")
async def send_link(body: LinkIn, user=Depends(require_admin)):
    u = await db.users.find_one({"_id": ObjectId(body.user_id)}) if ObjectId.is_valid(body.user_id) else None
    if not u:
        raise HTTPException(404, "Cuenta no encontrada")
    site = os.environ["APP_PUBLIC_URL"].rstrip("/")
    s = await B.checkout(B.CheckoutIn(plan_id=body.plan_id, origin_url=site), {**u, "id": str(u["_id"])})
    plan = await db.plans.find_one({"_id": ObjectId(body.plan_id)}, {"name": 1})
    await emailer.send(u["email"], "Activa tu suscripción de VozLeads", "Tu enlace para activar la suscripción", [
        ("Plan", (plan or {}).get("name", "")), ("Cómo", "Pulsa el botón, introduce tu tarjeta y tu suscripción queda activa al momento."),
        ("Seguridad", "El pago se hace en Stripe; VozLeads no ve los datos de tu tarjeta.")], s["checkout_url"],
        "Te enviamos el enlace seguro para registrar tu tarjeta y activar tu plan.", "Registrar mi tarjeta")
    return {"ok": True, "url": s["checkout_url"]}
