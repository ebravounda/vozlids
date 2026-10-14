import asyncio
import logging
import os
from typing import Optional
import stripe
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
import auth as A
import emailer
from db import db
from extra_routes import require_admin
from models import now_iso

router = APIRouter(prefix="/api")
CurrentUser = Depends(A.get_current_user)
log = logging.getLogger("vozlead.billing")
PROXY = "https://integrations.emergentagent.com/stripe"
EVENTS = ["checkout.session.completed", "customer.subscription.updated", "customer.subscription.deleted",
          "invoice.payment_failed", "invoice.paid"]


async def settings() -> dict:
    return await db.platform_settings.find_one({"_id": "stripe"}) or {}


def make_client(key: str) -> stripe.StripeClient:
    if "sk_test_emergent" in key:
        return stripe.StripeClient(key, base_addresses={"api": PROXY})
    return stripe.StripeClient(key)


async def client() -> tuple:
    s = await settings()
    key = s.get("secret_key") or os.environ["STRIPE_API_KEY"]
    return make_client(key), s, "sk_test_emergent" in key


def mode_of(key: str) -> str:
    return "live" if key.startswith(("sk_live_", "rk_live_")) else "test"


# ---------- Super admin: Stripe account ----------
class StripeIn(BaseModel):
    secret_key: str = Field(min_length=10, max_length=300)


@router.get("/admin/stripe")
async def stripe_status(user=Depends(require_admin)):
    s = await settings()
    key = s.get("secret_key")
    return {"connected": bool(key), "mode": mode_of(key) if key else "test", "key_last4": key[-4:] if key else None,
            "account_name": s.get("account_name"), "webhook": bool(s.get("webhook_secret")),
            "updated_at": s.get("updated_at")}


@router.put("/admin/stripe")
async def stripe_connect(body: StripeIn, user=Depends(require_admin)):
    key = body.secret_key.strip()
    if not key.startswith(("sk_test_", "sk_live_", "rk_test_", "rk_live_")):
        raise HTTPException(422, "La clave debe empezar por sk_live_ o sk_test_ (clave secreta de Stripe).")
    c = make_client(key)
    try:
        acct = await asyncio.to_thread(c.v1.accounts.retrieve_current)
        url = f"{os.environ['PUBLIC_BACKEND_URL'].rstrip('/')}/api/billing/webhook"
        old = await settings()
        if old.get("webhook_id") and old.get("secret_key") == key:
            await asyncio.to_thread(c.v1.webhook_endpoints.delete, old["webhook_id"])
        wh = await asyncio.to_thread(c.v1.webhook_endpoints.create, {"url": url, "enabled_events": EVENTS,
                                                                     "description": "VozLeads suscripciones"})
    except stripe.error.AuthenticationError:
        raise HTTPException(400, "Stripe rechazó la clave. Revisa que sea la clave secreta correcta.")
    except stripe.error.StripeError as e:
        raise HTTPException(400, f"Stripe respondió: {e.user_message or str(e)[:200]}")
    name = (acct.get("business_profile") or {}).get("name") or acct.get("email") or acct.get("id")
    await db.platform_settings.update_one({"_id": "stripe"}, {"$set": {
        "secret_key": key, "webhook_id": wh.id, "webhook_secret": wh.secret, "account_name": name,
        "updated_at": now_iso()}}, upsert=True)
    return {"ok": True, "mode": mode_of(key), "account_name": name}


@router.delete("/admin/stripe")
async def stripe_disconnect(user=Depends(require_admin)):
    await db.platform_settings.delete_one({"_id": "stripe"})
    return {"ok": True}


# ---------- Business: subscription ----------
class CheckoutIn(BaseModel):
    plan_id: str
    origin_url: str = Field(pattern=r"^https?://")


def amount_for(plan: dict, currency: str) -> int:
    return int(round(plan["price_clp"])) if currency == "clp" else int(round(plan["price_eur"] * 100))


async def activate(user_id: str, plan_id: str, customer: Optional[str], subscription: Optional[str]):
    res = await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {
        "plan_id": plan_id, "stripe_customer_id": customer, "stripe_subscription_id": subscription,
        "billing_status": "active", "cancel_at_period_end": False, "updated_at": now_iso()}})
    if res.modified_count:
        u = await db.users.find_one({"_id": ObjectId(user_id)})
        plan = await db.plans.find_one({"_id": ObjectId(plan_id)})
        if u and plan:
            await emailer.send(u["email"], f"Suscripción activa: plan {plan['name']}", "¡Tu plan ya está activo!",
                               [("Plan", plan["name"]), ("Minutos al mes", plan["minutes"])],
                               os.environ["APP_PUBLIC_URL"] + "/app/plan")


@router.get("/billing/me")
async def billing_me(user=CurrentUser):
    plan = await db.plans.find_one({"_id": ObjectId(user["plan_id"])}) if user.get("plan_id") else None
    cur = "CLP" if user.get("country") == "CL" else "EUR"
    return {"currency": cur, "plan_id": user.get("plan_id"), "plan_name": plan and plan["name"],
            "billing_status": user.get("billing_status"), "cancel_at_period_end": user.get("cancel_at_period_end", False),
            "has_subscription": bool(user.get("stripe_subscription_id"))}


@router.post("/billing/checkout")
async def checkout(body: CheckoutIn, user=CurrentUser):
    if not ObjectId.is_valid(body.plan_id):
        raise HTTPException(404, "Plan no encontrado")
    plan = await db.plans.find_one({"_id": ObjectId(body.plan_id), "public": True})
    if not plan:
        raise HTTPException(404, "Plan no encontrado")
    currency = "clp" if user.get("country") == "CL" else "eur"
    amount = amount_for(plan, currency)
    if amount <= 0:
        raise HTTPException(400, "Este plan no tiene precio configurado para tu país.")
    c, _, _ = await client()
    meta = {"user_id": user["id"], "plan_id": body.plan_id}
    params = {
        "mode": "subscription",
        "line_items": [{"quantity": 1, "price_data": {
            "currency": currency, "unit_amount": amount, "recurring": {"interval": "month"},
            "product_data": {"name": f"VozLeads · Plan {plan['name']}"}}}],
        "success_url": f"{body.origin_url.rstrip('/')}/app/plan?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{body.origin_url.rstrip('/')}/app/plan?cancelado=1",
        "metadata": meta, "subscription_data": {"metadata": meta}, "client_reference_id": user["id"],
    }
    if user.get("stripe_customer_id"):
        params["customer"] = user["stripe_customer_id"]
    else:
        params["customer_email"] = user["email"]
    try:
        session = await asyncio.to_thread(c.v1.checkout.sessions.create, params)
    except stripe.error.StripeError as e:
        raise HTTPException(400, f"No se pudo iniciar el pago: {e.user_message or str(e)[:200]}")
    await db.payment_transactions.insert_one({
        "session_id": session.id, "user_id": user["id"], "plan_id": body.plan_id, "amount": float(amount),
        "currency": currency, "status": "initiated", "payment_status": "pending", "created_at": now_iso()})
    return {"checkout_url": session.url, "session_id": session.id}


@router.get("/billing/status/{session_id}")
async def checkout_status(session_id: str, user=CurrentUser):
    tx = await db.payment_transactions.find_one({"session_id": session_id, "user_id": user["id"]})
    if not tx:
        raise HTTPException(404, "Pago no encontrado")
    if tx["payment_status"] != "paid":
        c, _, _ = await client()
        try:
            s = await asyncio.to_thread(c.v1.checkout.sessions.retrieve, session_id)
        except stripe.error.StripeError:
            s = None
        if s and (s.payment_status == "paid" or s.status == "complete"):
            await mark_paid(session_id, s.get("customer"), s.get("subscription"))
        elif s and s.status == "expired":
            await db.payment_transactions.update_one({"session_id": session_id}, {"$set": {"status": "expired",
                                                                                           "payment_status": "expired"}})
        tx = await db.payment_transactions.find_one({"session_id": session_id})
    return {"session_id": session_id, "status": tx["status"], "payment_status": tx["payment_status"]}


async def mark_paid(session_id: str, customer: Optional[str], subscription: Optional[str]):
    res = await db.payment_transactions.find_one_and_update(
        {"session_id": session_id, "payment_status": {"$ne": "paid"}},
        {"$set": {"status": "completed", "payment_status": "paid", "stripe_subscription_id": subscription,
                  "updated_at": now_iso()}})
    if res:
        await activate(res["user_id"], res["plan_id"], customer, subscription)


@router.post("/billing/cancel")
async def cancel(user=CurrentUser):
    sub = user.get("stripe_subscription_id")
    if not sub:
        raise HTTPException(400, "No tienes una suscripción activa.")
    c, _, shared_test = await client()
    if not shared_test:
        try:
            await asyncio.to_thread(c.v1.subscriptions.update, sub, {"cancel_at_period_end": True})
        except stripe.error.StripeError as e:
            raise HTTPException(400, f"Stripe respondió: {e.user_message or str(e)[:200]}")
    await db.users.update_one({"_id": ObjectId(user["id"])}, {"$set": {"cancel_at_period_end": True}})
    return {"ok": True}


@router.post("/billing/portal")
async def portal(body: dict, user=CurrentUser):
    c, _, shared_test = await client()
    if shared_test or not user.get("stripe_customer_id"):
        raise HTTPException(400, "El portal de facturación estará disponible cuando la cuenta de Stripe esté conectada.")
    origin = str(body.get("origin_url") or os.environ["APP_PUBLIC_URL"]).rstrip("/")
    try:
        s = await asyncio.to_thread(c.v1.billing_portal.sessions.create,
                                    {"customer": user["stripe_customer_id"], "return_url": f"{origin}/app/plan"})
    except stripe.error.StripeError as e:
        raise HTTPException(400, f"Stripe respondió: {e.user_message or str(e)[:200]}")
    return {"url": s.url}


@router.post("/billing/webhook")
async def webhook(request: Request):
    s = await settings()
    secret = s.get("webhook_secret")
    if not secret:
        return {"ok": True}
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(payload, request.headers.get("stripe-signature", ""), secret)
    except (stripe.error.SignatureVerificationError, ValueError):
        raise HTTPException(400, "Firma no válida")
    obj, t = event["data"]["object"], event["type"]
    if t == "checkout.session.completed":
        await mark_paid(obj["id"], obj.get("customer"), obj.get("subscription"))
    elif t in ("customer.subscription.updated", "customer.subscription.deleted"):
        u = await db.users.find_one({"stripe_subscription_id": obj["id"]})
        if u:
            ended = t.endswith("deleted") or obj.get("status") in ("canceled", "unpaid", "incomplete_expired")
            upd = {"billing_status": "canceled" if ended else obj.get("status"),
                   "cancel_at_period_end": bool(obj.get("cancel_at_period_end"))}
            await db.users.update_one({"_id": u["_id"]}, {"$set": upd})
    elif t == "invoice.payment_failed":
        u = await db.users.find_one({"stripe_customer_id": obj.get("customer")})
        if u:
            await db.users.update_one({"_id": u["_id"]}, {"$set": {"billing_status": "past_due"}})
            await emailer.send(u["email"], "No hemos podido cobrar tu plan", "Pago de la suscripción rechazado",
                               [("Qué hacer", "Actualiza tu tarjeta para que tus llamadas sigan activas.")],
                               os.environ["APP_PUBLIC_URL"] + "/app/plan")
    elif t == "invoice.paid":
        await db.users.update_one({"stripe_customer_id": obj.get("customer")}, {"$set": {"billing_status": "active"}})
    return {"ok": True}
