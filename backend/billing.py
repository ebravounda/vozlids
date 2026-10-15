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


async def client(mode: str = "live") -> tuple:
    s = await settings()
    key = (s.get("test_key") if mode == "test" else s.get("secret_key")) or os.environ["STRIPE_API_KEY"]
    return make_client(key), s, "sk_test_emergent" in key


async def mode_for(email: str) -> str:
    s = await settings()
    scope = s.get("test_scope", "off")
    return "test" if scope == "all" or (scope == "emails" and email.lower() in s.get("test_emails", [])) else "live"


def mode_of(key: str) -> str:
    return "live" if key.startswith(("sk_live_", "rk_live_")) else "test"


# ---------- Super admin: Stripe account ----------
class StripeIn(BaseModel):
    secret_key: str = Field(min_length=10, max_length=300)


@router.get("/admin/stripe")
async def stripe_status(user=Depends(require_admin)):
    s = await settings()
    key, tkey = s.get("secret_key"), s.get("test_key")
    return {"connected": bool(key), "mode": mode_of(key) if key else "test", "key_last4": key[-4:] if key else None,
            "account_name": s.get("account_name"), "webhook": bool(s.get("webhook_secret")), "updated_at": s.get("updated_at"),
            "test_connected": bool(tkey), "test_key_last4": tkey[-4:] if tkey else None, "test_account_name": s.get("test_account_name"),
            "test_scope": s.get("test_scope", "off"), "test_emails": s.get("test_emails", []),
            "uses_shared_test_key": not (tkey if s.get("test_scope", "off") != "off" else key)}


async def connect_key(key: str, prefix: str) -> dict:
    c = make_client(key)
    try:
        acct = await asyncio.to_thread(c.v1.accounts.retrieve_current)
        url = f"{os.environ['PUBLIC_BACKEND_URL'].rstrip('/')}/api/billing/webhook"
        old = await settings()
        if old.get(f"{prefix}webhook_id") and old.get("test_key" if prefix else "secret_key") == key:
            await asyncio.to_thread(c.v1.webhook_endpoints.delete, old[f"{prefix}webhook_id"])
        wh = await asyncio.to_thread(c.v1.webhook_endpoints.create, {"url": url, "enabled_events": EVENTS,
                                                                     "description": "VozLeads suscripciones"})
    except stripe.error.AuthenticationError:
        raise HTTPException(400, "Stripe rechazó la clave. Revisa que sea la clave secreta correcta.")
    except stripe.error.StripeError as e:
        raise HTTPException(400, f"Stripe respondió: {e.user_message or str(e)[:200]}")
    name = (acct.get("business_profile") or {}).get("name") or acct.get("email") or acct.get("id")
    return {f"{prefix}webhook_id": wh.id, f"{prefix}webhook_secret": wh.secret, f"{prefix}account_name": name}


@router.put("/admin/stripe")
async def stripe_connect(body: StripeIn, user=Depends(require_admin)):
    key = body.secret_key.strip()
    if not key.startswith(("sk_test_", "sk_live_", "rk_test_", "rk_live_")):
        raise HTTPException(422, "La clave debe empezar por sk_live_ o sk_test_ (clave secreta de Stripe).")
    extra = await connect_key(key, "")
    await db.platform_settings.update_one({"_id": "stripe"}, {"$set": {"secret_key": key, **extra, "updated_at": now_iso()}},
                                          upsert=True)
    return {"ok": True, "mode": mode_of(key), "account_name": extra["account_name"]}


@router.delete("/admin/stripe")
async def stripe_disconnect(user=Depends(require_admin)):
    await db.platform_settings.update_one({"_id": "stripe"}, {"$unset": {k: "" for k in (
        "secret_key", "webhook_id", "webhook_secret", "account_name")}})
    return {"ok": True}


@router.put("/admin/stripe/test-key")
async def stripe_test_connect(body: StripeIn, user=Depends(require_admin)):
    key = body.secret_key.strip()
    if not key.startswith(("sk_test_", "rk_test_")):
        raise HTTPException(422, "La clave de pruebas empieza por sk_test_ (Stripe → modo prueba → Desarrolladores → Claves API).")
    extra = await connect_key(key, "test_")
    await db.platform_settings.update_one({"_id": "stripe"}, {"$set": {"test_key": key, **extra}}, upsert=True)
    return {"ok": True, "account_name": extra["test_account_name"]}


@router.delete("/admin/stripe/test-key")
async def stripe_test_disconnect(user=Depends(require_admin)):
    await db.platform_settings.update_one({"_id": "stripe"}, {"$unset": {k: "" for k in (
        "test_key", "test_webhook_id", "test_webhook_secret", "test_account_name")}})
    return {"ok": True}


class TestModeIn(BaseModel):
    scope: str = Field(pattern="^(off|all|emails)$")
    emails: list[str] = Field(default_factory=list, max_length=20)


@router.put("/admin/stripe/test-mode")
async def stripe_test_mode(body: TestModeIn, user=Depends(require_admin)):
    emails = sorted({e.strip().lower() for e in body.emails if "@" in e})
    if body.scope == "emails" and not emails:
        raise HTTPException(422, "Añade al menos un email de pruebas")
    await db.platform_settings.update_one({"_id": "stripe"}, {"$set": {"test_scope": body.scope, "test_emails": emails}},
                                          upsert=True)
    return await stripe_status(user)


# ---------- Business: subscription ----------
class CheckoutIn(BaseModel):
    plan_id: str
    origin_url: str = Field(pattern=r"^https?://")
    signup: bool = False


def amount_for(plan: dict, currency: str) -> int:
    return int(round(plan["price_clp"])) if currency == "clp" else int(round(plan["price_eur"] * 100))


def promo_for(plan: dict, currency: str) -> int:
    """Promo price in Stripe units, or 0 when the plan has no active promotion for this currency."""
    if not plan.get("promo_active"):
        return 0
    v = plan.get("promo_price_clp" if currency == "clp" else "promo_price_eur") or 0
    amt = int(round(v)) if currency == "clp" else int(round(v * 100))
    return amt if 0 < amt < amount_for(plan, currency) else 0


async def activate(user_id: str, plan_id: str, customer: Optional[str], subscription: Optional[str], test: bool = False):
    res = await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {
        "plan_id": plan_id, "stripe_customer_id": customer, "stripe_subscription_id": subscription, "billing_test": test,
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
            "has_subscription": bool(user.get("stripe_subscription_id")),
            "pending_plan_id": user.get("pending_plan_id"), "pending_plan_at": user.get("pending_plan_at")}


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
    mode = await mode_for(user["email"])
    c, _, proxy = await client(mode)
    mode = "test" if proxy else mode
    meta = {"user_id": user["id"], "plan_id": body.plan_id}
    params = {
        "mode": "subscription",
        "line_items": [{"quantity": 1, "price_data": {
            "currency": currency, "unit_amount": amount, "recurring": {"interval": "month"},
            "product_data": {"name": f"VozLeads · Plan {plan['name']}"}}}],
        "success_url": f"{body.origin_url.rstrip('/')}/app/{'bienvenida' if body.signup else 'plan'}?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{body.origin_url.rstrip('/')}/app/plan?cancelado=1",
        "metadata": meta, "subscription_data": {"metadata": meta}, "client_reference_id": user["id"],
    }
    promo = promo_for(plan, currency)
    if promo and proxy:
        params["line_items"][0]["price_data"]["unit_amount"] = promo
        meta.update(promo_amount=str(promo), promo_months=str(plan.get("promo_months") or 3))
    elif promo:
        months = int(plan.get("promo_months") or 3)
        try:
            coupon = await asyncio.to_thread(c.v1.coupons.create, {
                "amount_off": amount - promo, "currency": currency, "duration": "repeating", "duration_in_months": months,
                "name": f"{plan.get('promo_label') or 'Promoción'} · {months} {'mes' if months == 1 else 'meses'}"[:40],
                "metadata": {"plan_id": body.plan_id}})
        except stripe.error.StripeError as e:
            raise HTTPException(400, f"No se pudo aplicar la promoción: {e.user_message or str(e)[:200]}")
        params["discounts"] = [{"coupon": coupon.id}]
        meta.update(promo_amount=str(promo), promo_months=str(months))
    if user.get("stripe_customer_id") and user.get("stripe_mode", "live") == mode:
        params["customer"] = user["stripe_customer_id"]
    else:
        params["customer_email"] = user["email"]
    try:
        session = await asyncio.to_thread(c.v1.checkout.sessions.create, params)
    except stripe.error.StripeError as e:
        if proxy:
            log.warning("shared Stripe test key rejected: %s", str(e)[:200])
            raise HTTPException(400, "Los pagos no están configurados en este servidor: conecta tu cuenta de Stripe en Super Admin → Stripe "
                                     "(clave sk_test_… para el modo de prueba o sk_live_… para cobros reales).")
        raise HTTPException(400, f"No se pudo iniciar el pago: {e.user_message or str(e)[:200]}")
    await db.payment_transactions.insert_one({
        "session_id": session.id, "user_id": user["id"], "plan_id": body.plan_id, "amount": float(amount),
        "currency": currency, "status": "initiated", "payment_status": "pending", "stripe_mode": mode, "created_at": now_iso()})
    return {"checkout_url": session.url, "session_id": session.id}


@router.get("/billing/status/{session_id}")
async def checkout_status(session_id: str, user=CurrentUser):
    tx = await db.payment_transactions.find_one({"session_id": session_id, "user_id": user["id"]})
    if not tx:
        raise HTTPException(404, "Pago no encontrado")
    if tx["payment_status"] != "paid":
        c, _, _ = await client(tx.get("stripe_mode", "live"))
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
        mode = res.get("stripe_mode", "live")
        _, s, proxy = await client(mode)
        test = proxy or mode == "test" or mode_of(s.get("secret_key", "")) != "live"
        await db.users.update_one({"_id": ObjectId(res["user_id"])}, {"$set": {"stripe_mode": mode}})
        await activate(res["user_id"], res["plan_id"], customer, subscription, test)
        import phone_numbers as N
        asyncio.create_task(N.auto_provision(res["user_id"], test))


@router.post("/billing/cancel")
async def cancel(user=CurrentUser):
    sub = user.get("stripe_subscription_id")
    if not sub:
        raise HTTPException(400, "No tienes una suscripción activa.")
    c, _, shared_test = await client(user.get("stripe_mode", "live"))
    if not shared_test:
        try:
            await asyncio.to_thread(c.v1.subscriptions.update, sub, {"cancel_at_period_end": True})
        except stripe.error.StripeError as e:
            raise HTTPException(400, f"Stripe respondió: {e.user_message or str(e)[:200]}")
    await db.users.update_one({"_id": ObjectId(user["id"])}, {"$set": {"cancel_at_period_end": True}})
    return {"ok": True}


@router.post("/billing/portal")
async def portal(body: dict, user=CurrentUser):
    c, _, shared_test = await client(user.get("stripe_mode", "live"))
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
    secrets_ = [x for x in (s.get("webhook_secret"), s.get("test_webhook_secret")) if x]
    if not secrets_:
        return {"ok": True}
    payload = await request.body()
    event = None
    for secret in secrets_:
        try:
            event = stripe.Webhook.construct_event(payload, request.headers.get("stripe-signature", ""), secret)
            break
        except (stripe.error.SignatureVerificationError, ValueError):
            continue
    if event is None:
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
            if ended:
                import phone_numbers as N
                await N.release(str(u["_id"]))
    elif t == "invoice.payment_failed":
        u = await db.users.find_one({"stripe_customer_id": obj.get("customer")})
        if u:
            await db.users.update_one({"_id": u["_id"]}, {"$set": {"billing_status": "past_due"}})
            await emailer.send(u["email"], "No hemos podido cobrar tu plan", "Pago de la suscripción rechazado",
                               [("Qué hacer", "Actualiza tu tarjeta para que tus llamadas sigan activas.")],
                               os.environ["APP_PUBLIC_URL"] + "/app/plan")
    elif t == "invoice.paid":
        await db.users.update_one({"stripe_customer_id": obj.get("customer")}, {"$set": {"billing_status": "active"}})
        if obj.get("billing_reason") == "subscription_cycle":
            u = await db.users.find_one({"stripe_customer_id": obj.get("customer"), "pending_plan_id": {"$exists": True}})
            if u:
                await db.users.update_one({"_id": u["_id"]}, {"$set": {"plan_id": u["pending_plan_id"], "plan_changed_at": now_iso()},
                                                             "$unset": {"pending_plan_id": "", "pending_plan_at": ""}})
    return {"ok": True}


# ---------- Change plan from the panel (upgrade now with proration, downgrade at renewal) ----------
class ChangeIn(BaseModel):
    plan_id: str = Field(min_length=24, max_length=24)


async def _change_ctx(user: dict, plan_id: str) -> dict:
    if not user.get("stripe_subscription_id") or user.get("billing_status") != "active":
        raise HTTPException(409, "No tienes una suscripción activa que cambiar. Contrata el plan desde «Mi plan».")
    if plan_id == user.get("plan_id"):
        raise HTTPException(409, "Ya estás en este plan.")
    if (await client(user.get("stripe_mode", "live")))[2]:
        raise HTTPException(409, "El cambio de plan en un clic necesita la cuenta de Stripe propia conectada en Super Admin (el modo de prueba compartido no lo permite).")
    new = await db.plans.find_one({"_id": ObjectId(plan_id), "public": True}) if ObjectId.is_valid(plan_id) else None
    old = await db.plans.find_one({"_id": ObjectId(user["plan_id"])}) if ObjectId.is_valid(user.get("plan_id") or "") else None
    if not new:
        raise HTTPException(404, "Plan no encontrado")
    currency = "clp" if user.get("country") == "CL" else "eur"
    amount = amount_for(new, currency)
    if amount <= 0:
        raise HTTPException(400, "Este plan no tiene precio para tu país.")
    c, _, proxy = await client(user.get("stripe_mode", "live"))
    try:
        sub = await asyncio.to_thread(c.v1.subscriptions.retrieve, user["stripe_subscription_id"])
    except stripe.error.StripeError as e:
        raise HTTPException(400, f"No se pudo leer tu suscripción: {e.user_message or str(e)[:160]}")
    item = sub["items"]["data"][0]
    current = int(item["price"]["unit_amount"] or 0)
    end = item.get("current_period_end") or sub.get("current_period_end")
    return {"c": c, "sub": sub, "item": item, "new": new, "old": old, "currency": currency, "amount": amount,
            "up": amount > current, "current": current, "period_end": end, "proxy": proxy}


def _items(ctx: dict) -> list:
    return [{"id": ctx["item"]["id"], "price_data": {"currency": ctx["currency"], "unit_amount": ctx["amount"],
             "recurring": {"interval": "month"}, "product": ctx["item"]["price"]["product"]}}]


def _human(amount: int, currency: str) -> float:
    return amount if currency == "clp" else round(amount / 100, 2)


@router.post("/billing/change-plan/preview")
async def change_preview(body: ChangeIn, user=CurrentUser):
    ctx = await _change_ctx(user, body.plan_id)
    due = 0
    if ctx["up"]:
        try:
            inv = await asyncio.to_thread(ctx["c"].v1.invoices.create_preview, {
                "customer": user["stripe_customer_id"], "subscription": ctx["sub"]["id"],
                "subscription_details": {"items": _items(ctx), "proration_behavior": "always_invoice"}})
            due = int(inv["amount_due"] or 0)
        except stripe.error.StripeError as e:
            log.warning("preview failed: %s", e)
            due = max(0, ctx["amount"] - ctx["current"])
    from datetime import datetime, timezone
    return {"direction": "up" if ctx["up"] else "down", "plan": ctx["new"]["name"], "minutes": ctx["new"]["minutes"],
            "currency": ctx["currency"].upper(), "new_price": _human(ctx["amount"], ctx["currency"]),
            "due_now": _human(due, ctx["currency"]),
            "effective_at": None if ctx["up"] else datetime.fromtimestamp(ctx["period_end"], timezone.utc).isoformat() if ctx["period_end"] else None}


@router.post("/billing/change-plan")
async def change_plan(body: ChangeIn, user=CurrentUser):
    ctx = await _change_ctx(user, body.plan_id)
    params = {"items": _items(ctx), "metadata": {"user_id": user["id"], "plan_id": body.plan_id}}
    if ctx["up"]:
        params.update(proration_behavior="always_invoice", payment_behavior="error_if_incomplete")
    else:
        params.update(proration_behavior="none")
    try:
        await asyncio.to_thread(ctx["c"].v1.subscriptions.update, ctx["sub"]["id"], params)
    except stripe.error.CardError as e:
        raise HTTPException(402, f"Tu tarjeta ha rechazado el pago: {e.user_message or 'revisa tu método de pago'}.")
    except stripe.error.StripeError as e:
        raise HTTPException(400, f"No se pudo cambiar el plan: {e.user_message or str(e)[:200]}")
    from datetime import datetime, timezone
    if ctx["up"]:
        await db.users.update_one({"_id": ObjectId(user["id"])}, {"$set": {"plan_id": body.plan_id, "plan_changed_at": now_iso()},
                                                                  "$unset": {"pending_plan_id": "", "pending_plan_at": ""}})
        return {"ok": True, "applied": True, "plan": ctx["new"]["name"]}
    at = datetime.fromtimestamp(ctx["period_end"], timezone.utc).isoformat() if ctx["period_end"] else now_iso()
    await db.users.update_one({"_id": ObjectId(user["id"])}, {"$set": {"pending_plan_id": body.plan_id, "pending_plan_at": at}})
    return {"ok": True, "applied": False, "plan": ctx["new"]["name"], "effective_at": at}


@router.delete("/billing/change-plan")
async def cancel_downgrade(user=CurrentUser):
    u = await db.users.find_one({"_id": ObjectId(user["id"])})
    if not u.get("pending_plan_id"):
        return {"ok": True}
    old = await db.plans.find_one({"_id": ObjectId(u["plan_id"])}) if ObjectId.is_valid(u.get("plan_id") or "") else None
    if old:
        ctx = await _change_ctx({**u, "id": user["id"], "plan_id": u["pending_plan_id"]}, u["plan_id"])
        await asyncio.to_thread(ctx["c"].v1.subscriptions.update, ctx["sub"]["id"], {"items": _items(ctx), "proration_behavior": "none"})
    await db.users.update_one({"_id": u["_id"]}, {"$unset": {"pending_plan_id": "", "pending_plan_at": ""}})
    return {"ok": True}


async def apply_pending_downgrades() -> int:
    n = 0
    async for u in db.users.find({"pending_plan_id": {"$exists": True}, "pending_plan_at": {"$lte": now_iso()}}, {"pending_plan_id": 1}):
        await db.users.update_one({"_id": u["_id"]}, {"$set": {"plan_id": u["pending_plan_id"], "plan_changed_at": now_iso()},
                                                     "$unset": {"pending_plan_id": "", "pending_plan_at": ""}})
        n += 1
    return n
