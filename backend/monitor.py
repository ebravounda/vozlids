import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
import httpx
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import billing
import emailer
import vapi
import zadarma
from db import db
from extra_routes import _parts, get_pricing, require_admin
from models import now_iso
from voice_preview import eleven_key

router = APIRouter(prefix="/api")
log = logging.getLogger("vozlead.monitor")
DEFAULT_ALERTS = {"email": "", "enabled": True, "sip_min": 2.0, "voice_min_pct": 20.0, "ai_min_usd": 10.0}
ACTIVE = ("queued", "ringing", "in-progress")
_cache: dict = {}


async def cached(key: str, ttl: int, fn):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    val = await fn()
    _cache[key] = (time.time(), val)
    return val


def month_start() -> datetime:
    return datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)


# ---------- Providers ----------
async def sip_status() -> dict:
    if not (await zadarma.creds()).get("key"):
        return {"connected": False}
    try:
        d = await zadarma.balance()
        return {"connected": True, "balance": float(d.get("balance", 0)), "currency": d.get("currency", "EUR")}
    except zadarma.ZadarmaError as e:
        return {"connected": True, "error": str(e)}


async def voice_status() -> dict:
    key = await eleven_key()
    if not key:
        return {"connected": False}
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get("https://api.elevenlabs.io/v1/user/subscription", headers={"xi-api-key": key})
        r.raise_for_status()
        d = r.json()
    except httpx.HTTPError as e:
        code = getattr(getattr(e, "response", None), "status_code", "")
        return {"connected": True, "error": f"No se pudo leer el consumo ({code or e.__class__.__name__}). "
                                            "La clave necesita el permiso «User» (lectura)."}
    used, limit = d.get("character_count", 0), d.get("character_limit", 0) or 0
    reset = d.get("next_character_count_reset_unix")
    reset_dt = datetime.fromtimestamp(reset, timezone.utc) if reset else None
    runs_out = None
    if reset_dt and limit and used:
        m = reset_dt.month - 1 or 12
        start = reset_dt.replace(year=reset_dt.year - (m == 12), month=m, day=min(reset_dt.day, 28))
        elapsed = (datetime.now(timezone.utc) - start).total_seconds() / 86400
        if elapsed >= 1:
            eta = datetime.now(timezone.utc) + timedelta(days=max(0, limit - used) / (used / elapsed))
            runs_out = eta.isoformat() if eta < reset_dt else None
    return {"connected": True, "tier": d.get("tier"), "used": used, "limit": limit,
            "pct_left": round(100 * (limit - used) / limit, 1) if limit else None,
            "reset_at": reset_dt.isoformat() if reset_dt else None, "runs_out_at": runs_out}


def provider_issues(b: dict, s: dict) -> list:
    sip, voice, ai = b["sip"], b["voice"], b["ai"]
    out = []
    if voice.get("pct_left") is not None and voice["pct_left"] < s["voice_min_pct"]:
        empty = voice["pct_left"] <= 0
        out.append({"kind": "voice", "level": "critical" if empty else "warning", "pct": max(0, voice["pct_left"]),
                    "title": "Voces · ElevenLabs agotado: se usa la voz de respaldo" if empty else f"Voces · ElevenLabs: queda un {voice['pct_left']}%",
                    "detail": f"{voice['used']:,} de {voice['limit']:,} caracteres · plan {voice.get('tier')}".replace(",", "."),
                    "runs_out_at": voice.get("runs_out_at"), "reset_at": voice.get("reset_at"),
                    "url": "https://elevenlabs.io/app/subscription", "action": "Recargar ElevenLabs"})
    if sip.get("balance") is not None and sip["balance"] < s["sip_min"]:
        out.append({"kind": "sip", "level": "critical" if sip["balance"] <= 0 else "warning",
                    "title": f"Línea · Zadarma: saldo {sip['balance']:.2f} {sip.get('currency', '')}",
                    "detail": f"Por debajo del mínimo de {s['sip_min']:g}. Sin saldo no salen ni entran llamadas.",
                    "url": "https://my.zadarma.com/pay/", "action": "Recargar Zadarma"})
    if ai.get("credit_left") is not None and ai["credit_left"] < s["ai_min_usd"]:
        out.append({"kind": "ai", "level": "critical" if ai["credit_left"] <= 0 else "warning",
                    "title": f"Motor IA · Vapi: quedan unos {ai['credit_left']:.2f} $",
                    "detail": f"Anotaste {ai['credit_set']:.2f} $ y se han gastado {ai['credit_spent']:.2f} $ desde entonces. Al recargar, anota el nuevo saldo en Monitor.",
                    "url": "https://dashboard.vapi.ai/org/billing/credits", "action": "Recargar Vapi"})
    if ai.get("active") is not None and ai["active"] >= ai.get("concurrency_limit", 10):
        out.append({"kind": "concurrency", "level": "warning", "title": "Todas las líneas simultáneas ocupadas",
                    "detail": f"{ai['active']}/{ai['concurrency_limit']} llamadas a la vez. Las nuevas esperan o fallan.",
                    "url": "https://dashboard.vapi.ai/org/billing", "action": "Ampliar en Vapi"})
    return out


@router.get("/admin/monitor/provider-alerts")
async def provider_alerts(user=Depends(require_admin)):
    b = await cached("balances", 300, all_balances)
    return {"issues": provider_issues(b, await alert_settings()), "checked_at": b["checked_at"]}


@router.get("/admin/monitor/voice-usage")
async def voice_usage(user=Depends(require_admin)):
    since = month_start().isoformat()
    rows = await db.leads.aggregate([
        {"$match": {"created_at": {"$gte": since}, "messages.0": {"$exists": True}}},
        {"$project": {"tenant_id": 1, "duration_seconds": 1, "chars": {"$sum": {"$map": {
            "input": {"$filter": {"input": "$messages", "cond": {"$eq": ["$$this.role", "agente"]}}},
            "in": {"$strLenCP": {"$ifNull": ["$$this.text", ""]}}}}}}},
        {"$group": {"_id": "$tenant_id", "chars": {"$sum": "$chars"}, "calls": {"$sum": 1},
                    "seconds": {"$sum": {"$ifNull": ["$duration_seconds", 0]}}}},
        {"$sort": {"chars": -1}}]).to_list(500)
    users = {str(u["_id"]): u async for u in db.users.find(
        {"_id": {"$in": [ObjectId(r["_id"]) for r in rows if ObjectId.is_valid(r["_id"])]}}, {"business_name": 1, "email": 1, "plan_id": 1})}
    plans = {str(p["_id"]): p["name"] async for p in db.plans.find({}, {"name": 1})}
    total = sum(r["chars"] for r in rows) or 1
    voice = (await cached("voice", 300, voice_status))
    return {"since": since, "total_chars": total if rows else 0, "plan_limit": voice.get("limit"), "plan_used": voice.get("used"),
            "rows": [{"tenant_id": r["_id"], "business": (users.get(r["_id"]) or {}).get("business_name") or (users.get(r["_id"]) or {}).get("email", "—"),
                      "email": (users.get(r["_id"]) or {}).get("email"), "plan": plans.get((users.get(r["_id"]) or {}).get("plan_id") or ""),
                      "calls": r["calls"], "minutes": round(r["seconds"] / 60, 1), "chars": r["chars"],
                      "share": round(100 * r["chars"] / total, 1),
                      "per_min": round(r["chars"] / (r["seconds"] / 60)) if r["seconds"] >= 30 else None} for r in rows]}


async def vapi_calls(since: datetime | None = None, limit: int = 100) -> list:
    params = {"limit": limit}
    if since:
        params["createdAtGe"] = since.isoformat()
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(f"{vapi.VAPI_URL}/call", params=params, headers=vapi._headers())
    r.raise_for_status()
    d = r.json()
    return d if isinstance(d, list) else d.get("results", [])


async def limits() -> dict:
    doc = await db.platform_settings.find_one({"_id": "vapi_limits"}) or {}
    return {k: doc.get(k) for k in ("concurrencyLimit", "remainingConcurrentCalls", "updated_at")}


async def ai_status() -> dict:
    try:
        calls = await vapi_calls(month_start(), 1000)
    except (httpx.HTTPError, KeyError) as e:
        return {"connected": True, "error": f"No se pudo leer el motor IA ({e.__class__.__name__})"}
    lim = await limits()
    out = {"connected": True, "month_spend": round(sum(c.get("cost") or 0 for c in calls), 4), "month_calls": len(calls),
           "active": sum(1 for c in calls if c.get("status") in ACTIVE),
           "concurrency_limit": lim.get("concurrencyLimit") or 10, "limits_seen_at": lim.get("updated_at")}
    credit = await db.platform_settings.find_one({"_id": "vapi_credit"})
    if credit:
        since = datetime.fromisoformat(credit["set_at"])
        spent = sum(c.get("cost") or 0 for c in (calls if since >= month_start() else await vapi_calls(since, 1000))
                    if (c.get("createdAt") or "") >= since.isoformat().replace("+00:00", "Z")[:19])
        out.update(credit_set=credit["amount"], credit_set_at=credit["set_at"], credit_spent=round(spent, 2),
                   credit_left=round(credit["amount"] - spent, 2))
    return out


class CreditIn(BaseModel):
    amount: float = Field(ge=0, le=1000000)


@router.put("/admin/monitor/vapi-credit")
async def set_vapi_credit(body: CreditIn, user=Depends(require_admin)):
    await db.platform_settings.update_one({"_id": "vapi_credit"}, {"$set": {"amount": body.amount, "set_at": now_iso()}}, upsert=True)
    _cache.pop("balances", None)
    await db.monitor_alerts.delete_many({"kind": "ai_low"})
    return {"ok": True}


async def stripe_status() -> dict:
    c, s, is_proxy = await billing.client()
    if is_proxy:
        return {"connected": False}
    try:
        b = await asyncio.to_thread(c.v1.balance.retrieve)
    except Exception as e:  # noqa: BLE001
        return {"connected": True, "error": f"Stripe: {str(e)[:150]}"}
    fmt = lambda rows: [{"amount": r.amount / 100, "currency": r.currency.upper()} for r in rows]  # noqa: E731
    return {"connected": True, "mode": billing.mode_of(s.get("secret_key", "")),
            "available": fmt(b.available), "pending": fmt(b.pending)}


async def all_balances() -> dict:
    sip, voice, ai, pay = await asyncio.gather(sip_status(), voice_status(), ai_status(), stripe_status())
    return {"sip": sip, "voice": voice, "ai": ai, "stripe": pay, "checked_at": now_iso()}


@router.get("/admin/monitor/balances")
async def balances(fresh: bool = False, user=Depends(require_admin)):
    if fresh:
        _cache.pop("balances", None)
    return await cached("balances", 60, all_balances)


@router.get("/admin/monitor/live")
async def live(user=Depends(require_admin)):
    calls = await cached("live", 5, lambda: vapi_calls(datetime.now(timezone.utc) - timedelta(hours=3), 200))
    active = [c for c in calls if c.get("status") in ACTIVE]
    leads = {ld["vapi_call_id"]: ld async for ld in db.leads.find({"vapi_call_id": {"$in": [c["id"] for c in active]}},
                                                                 {"name": 1, "tenant_id": 1, "vapi_call_id": 1, "phone": 1})}
    users = {str(u["_id"]): u.get("business_name") async for u in db.users.find(
        {"_id": {"$in": [ObjectId(ld["tenant_id"]) for ld in leads.values() if ObjectId.is_valid(ld["tenant_id"])]}},
        {"business_name": 1})}
    out = []
    for c in active:
        ld = leads.get(c["id"], {})
        out.append({"id": c["id"], "status": c["status"], "type": c.get("type"),
                    "number": (c.get("customer") or {}).get("number") or ld.get("phone"),
                    "lead": ld.get("name"), "business": users.get(ld.get("tenant_id"), "—"),
                    "can_listen": bool((c.get("monitor") or {}).get("listenUrl")), "can_hangup": bool((c.get("monitor") or {}).get("controlUrl")),
                    "started_at": c.get("startedAt") or c.get("createdAt")})
    lim = await limits()
    return {"active": out, "limit": lim.get("concurrencyLimit") or 10, "checked_at": now_iso()}


@router.get("/admin/monitor/sip-calls")
async def sip_calls(days: int = 7, user=Depends(require_admin)):
    days = max(1, min(days, 30))

    async def fetch():
        end = datetime.now(timezone.utc)
        d = await zadarma.call("GET", "/v1/statistics/", {
            "start": (end - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S"), "end": end.strftime("%Y-%m-%d %H:%M:%S")})
        return d.get("stats") or []
    try:
        stats = await cached(f"sip:{days}", 60, fetch)
    except zadarma.ZadarmaError as e:
        return {"calls": [], "total": 0, "count": 0, "currency": "EUR", "error": str(e)}
    rows = sorted(({"id": s.get("id"), "start": s.get("callstart"), "from": s.get("from"), "to": s.get("to"),
                    "seconds": s.get("billseconds"), "disposition": s.get("disposition"),
                    "destination": s.get("description"), "cost": float(s.get("billcost") or 0),
                    "currency": s.get("currency")} for s in stats), key=lambda r: r["start"] or "", reverse=True)
    return {"calls": rows[:500], "total": round(sum(r["cost"] for r in rows), 4), "count": len(rows),
            "currency": rows[0]["currency"] if rows else "EUR"}


@router.get("/admin/monitor/margins")
async def margins(user=Depends(require_admin)):
    pricing = await get_pricing()
    since = month_start().isoformat()
    plans = {str(p["_id"]): p async for p in db.plans.find({})}
    agent_country = {str(a["_id"]): a.get("country", "ES") async for a in db.agents.find({}, {"country": 1})}
    rates = {"ES": pricing["line_rate_usd_min"], "CL": pricing["line_rate_cl_usd_min"]}
    rows = []
    async for u in db.users.find({}, {"business_name": 1, "email": 1, "country": 1, "plan_id": 1,
                                      "stripe_subscription_id": 1, "allow_overage": 1, "billing_test": 1}):
        uid = str(u["_id"])
        cost, minutes, calls = 0.0, 0.0, 0
        async for ld in db.leads.find({"tenant_id": uid, "vapi_call_id": {"$ne": None}, "created_at": {"$gte": since}},
                                      {"messages": 0, "transcript": 0}):
            p = _parts(ld, rates.get(agent_country.get(ld["agent_id"], "ES"), rates["ES"]))
            cost += p["total"]
            minutes += p["minutes"]
            calls += 1
        plan = plans.get(u.get("plan_id") or "")
        if not calls and not (plan and u.get("stripe_subscription_id")):
            continue
        cl = u.get("country") == "CL"
        fx = pricing["usd_clp"] if cl else pricing["usd_eur"]
        revenue = 0.0
        if plan and u.get("stripe_subscription_id") and not u.get("billing_test"):
            revenue = plan["price_clp" if cl else "price_eur"]
            extra = max(0.0, minutes - plan["minutes"]) if u.get("allow_overage") else 0.0
            revenue += extra * plan["overage_clp" if cl else "overage_eur"]
        cost_local = cost * fx
        rows.append({"tenant_id": uid, "business": u.get("business_name") or u.get("email"), "email": u.get("email"),
                     "currency": "CLP" if cl else "EUR", "plan": plan["name"] if plan else None,
                     "paying": bool(plan and u.get("stripe_subscription_id") and not u.get("billing_test")), "calls": calls,
                     "minutes": round(minutes, 1), "cost": round(cost_local, 2), "revenue": round(revenue, 2),
                     "margin": round(revenue - cost_local, 2),
                     "margin_pct": round(100 * (revenue - cost_local) / revenue, 1) if revenue else None})
    return {"rows": sorted(rows, key=lambda r: -r["cost"]), "since": since}


# ---------- Alerts ----------
class AlertsIn(BaseModel):
    email: str = Field("", max_length=200)
    enabled: bool = True
    sip_min: float = Field(2.0, ge=0, le=10000)
    voice_min_pct: float = Field(20.0, ge=0, le=100)
    ai_min_usd: float = Field(10.0, ge=0, le=100000)


async def alert_settings() -> dict:
    doc = await db.platform_settings.find_one({"_id": "alerts"}) or {}
    s = {k: doc.get(k, v) for k, v in DEFAULT_ALERTS.items()}
    if not s["email"]:
        admin = await db.users.find_one({"role": "admin"}, {"email": 1})
        s["email"] = admin["email"] if admin else ""
    return s


@router.get("/admin/monitor/alerts")
async def get_alerts(user=Depends(require_admin)):
    recent = await db.monitor_alerts.find({}, {"_id": 0}).sort("created_at", -1).to_list(30)
    return {"settings": await alert_settings(), "recent": recent}


@router.put("/admin/monitor/alerts")
async def put_alerts(body: AlertsIn, user=Depends(require_admin)):
    if body.email and "@" not in body.email:
        raise HTTPException(422, "Email no válido")
    await db.platform_settings.update_one({"_id": "alerts"}, {"$set": body.model_dump()}, upsert=True)
    return await alert_settings()


async def notify(kind: str, title: str, rows: list, every_hours: int = 6, cta: str = "", cta_label: str = "") -> bool:
    s = await alert_settings()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=every_hours)).isoformat()
    if await db.monitor_alerts.find_one({"kind": kind, "created_at": {"$gte": cutoff}}):
        return False
    sent = bool(s["enabled"] and s["email"]) and await emailer.send(s["email"], f"Alerta VozLeads: {title}", title, rows,
                                                                       cta or f"{vapi.public_url()}/app/monitor",
                                                                       **({"cta_label": cta_label} if cta_label else {}))
    await db.monitor_alerts.insert_one({"kind": kind, "title": title, "rows": [list(r) for r in rows],
                                        "emailed": sent, "created_at": now_iso()})
    return True


async def check_once() -> None:
    s = await alert_settings()
    b = await all_balances()
    _cache["balances"] = (time.time(), b)
    sip, voice, ai = b["sip"], b["voice"], b["ai"]
    if sip.get("balance") is not None and sip["balance"] < s["sip_min"]:
        await notify("sip_low", "Saldo bajo en la línea SIP (Zadarma)",
                     [("Saldo actual", f"{sip['balance']:.2f} {sip['currency']}"), ("Mínimo", f"{s['sip_min']:.2f}"),
                      ("Qué hacer", "Recarga saldo en Zadarma o las llamadas dejarán de salir")])
    _cache["voice"] = (time.time(), voice)
    if voice.get("pct_left") is not None and voice["pct_left"] < s["voice_min_pct"]:
        fmt = lambda iso: datetime.fromisoformat(iso).strftime("%d/%m/%Y") if iso else "—"  # noqa: E731
        await notify("voice_low", f"Queda un {voice['pct_left']}% de saldo de voz (ElevenLabs)",
                     [("Caracteres usados", f"{voice['used']:,} de {voice['limit']:,}".replace(",", ".")),
                      ("Restante", f"{voice['pct_left']}% (aviso por debajo del {s['voice_min_pct']:g}%)"),
                      ("Se agota aprox.", fmt(voice.get("runs_out_at")) if voice.get("runs_out_at") else "No antes de la renovación"),
                      ("Se renueva", fmt(voice.get("reset_at"))),
                      ("Qué hacer", "Sube de plan o compra caracteres extra en elevenlabs.io → Subscription. Si se agota, se usa una voz de respaldo menos natural.")],
                     every_hours=24)
    if ai.get("credit_left") is not None and ai["credit_left"] < s["ai_min_usd"]:
        await notify("ai_low", f"Quedan unos {ai['credit_left']:.2f} $ de saldo en el motor IA (Vapi)",
                     [("Saldo anotado", f"{ai['credit_set']:.2f} $"), ("Gastado desde entonces", f"{ai['credit_spent']:.2f} $"),
                      ("Restante estimado", f"{ai['credit_left']:.2f} $ (aviso por debajo de {s['ai_min_usd']:g} $)"),
                      ("Qué hacer", "Recarga en dashboard.vapi.ai → Billing y anota el nuevo saldo en Monitor. Activa la recarga automática para no quedarte sin llamadas.")],
                     every_hours=24)
    if ai.get("active") is not None and ai["active"] >= ai["concurrency_limit"]:
        await notify("concurrency", "Límite de llamadas simultáneas alcanzado",
                     [("Llamadas en curso", ai["active"]), ("Límite", ai["concurrency_limit"]),
                      ("Qué hacer", "Compra más líneas en Vapi → Billing → Reserved Concurrency")], every_hours=1)
    for k, label in (("sip", "línea SIP (Zadarma)"), ("voice", "voces (ElevenLabs)"), ("ai", "motor IA (Vapi)")):
        if b[k].get("error"):
            await notify(f"{k}_error", f"No se puede leer el saldo de {label}", [("Error", b[k]["error"])], every_hours=24)


async def call_failed(error: str) -> None:
    low = error.lower()
    if "concurren" in low:
        await notify("concurrency", "Llamada rechazada: límite de llamadas simultáneas",
                     [("Detalle", error[:300]), ("Qué hacer", "Compra más líneas en Vapi → Billing → Reserved Concurrency")],
                     every_hours=1)
    elif any(w in low for w in ("credit", "wallet", "balance", "insufficient", "fund")):
        await notify("ai_funds", "El motor IA se ha quedado sin saldo (Vapi)",
                     [("Detalle", error[:300]), ("Qué hacer", "Recarga créditos en Vapi → Billing")], every_hours=1)


async def save_limits(lim: dict | None) -> None:
    if lim:
        await db.platform_settings.update_one({"_id": "vapi_limits"}, {"$set": {**lim, "updated_at": now_iso()}},
                                              upsert=True)


async def loop() -> None:
    await db.platform_settings.update_one({"_id": "alerts", "voice_min_pct": 2.0}, {"$set": {"voice_min_pct": 20.0, "ai_min_usd": 10.0}})
    await asyncio.sleep(60)
    while True:
        try:
            await check_once()
        except Exception as e:  # noqa: BLE001
            log.warning("Monitor check failed: %s", e)
        await asyncio.sleep(600)


@router.post("/admin/monitor/check")
async def run_check(user=Depends(require_admin)):
    await check_once()
    return await get_alerts(user)


# ---------- Resend ----------
class ResendIn(BaseModel):
    api_key: str = Field("", max_length=200)
    from_email: str = Field(min_length=3, max_length=200)
    reply_to: str = Field("", max_length=200)


@router.get("/admin/resend")
async def resend_status(user=Depends(require_admin)):
    cfg = await emailer.resend_cfg()
    return {"connected": bool(cfg.get("api_key")), "key_last4": cfg.get("api_key", "")[-4:],
            "from_email": cfg.get("from_email", ""), "reply_to": cfg.get("reply_to", "")}


@router.put("/admin/resend")
async def resend_save(body: ResendIn, user=Depends(require_admin)):
    if not body.api_key:
        body.api_key = (await emailer.resend_cfg()).get("api_key", "")
    if not body.api_key.startswith("re_"):
        raise HTTPException(422, "La clave de Resend empieza por «re_»")
    if "@" not in body.from_email:
        raise HTTPException(422, "Indica el remitente, por ejemplo avisos@vozleads.com")
    await db.platform_settings.update_one({"_id": "resend"}, {"$set": {**body.model_dump(), "updated_at": now_iso()}},
                                          upsert=True)
    return await resend_status(user)


@router.delete("/admin/resend")
async def resend_delete(user=Depends(require_admin)):
    await db.platform_settings.delete_one({"_id": "resend"})
    return {"ok": True}


@router.post("/admin/resend/test")
async def resend_test(user=Depends(require_admin)):
    to = (await alert_settings())["email"] or user["email"]
    err = await emailer.deliver(to, "Prueba de email de VozLeads", emailer._wrap(
        "Tus emails ya salen por Resend", [("Enviado a", to), ("Fecha", now_iso()[:16].replace("T", " "))]))
    if err:
        raise HTTPException(502, err)
    return {"ok": True, "to": to, "via": "resend" if (await emailer.resend_cfg()).get("api_key") else "emergent"}
