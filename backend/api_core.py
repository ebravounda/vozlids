"""Core of the public API v1: keys, limits, idempotency, call lifecycle and outgoing webhooks."""
import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import secrets
import socket
import time
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
import httpx
from bson import ObjectId
from fastapi import HTTPException
import services as S
from db import db
from models import now_iso

log = logging.getLogger("vozlead.api")
SCOPES = {"agents:read": "Ver agentes", "calls:read": "Ver llamadas y resultados", "calls:write": "Crear y cancelar llamadas",
          "account:read": "Ver consumo y límites", "webhooks:manage": "Gestionar webhooks", "dnc:manage": "Gestionar lista de exclusión",
          "privacy:manage": "Exportar y borrar datos (RGPD)"}
EVENTS = ["call.created", "call.started", "call.completed", "call.no_answer", "call.failed", "call.cancelled"]
DEFAULT_LIMITS = {"requests_per_minute": 120, "calls_per_minute": 30, "max_concurrent_calls": 5, "max_daily_calls": 300}
DEFAULT_HOURS = {"ES": {"weekdays": ["09:00", "21:00"], "saturday": ["10:00", "14:00"], "sunday": None},
                 "CL": {"weekdays": ["09:00", "21:00"], "saturday": ["10:00", "14:00"], "sunday": None}}
PURPOSE = {"info": "commercial", "encuesta": "informative", "seguimiento": "contractual", "cobro": "contractual",
           "recordatorio": "reminder"}
HOURS_APPLY = {"commercial", "contractual"}
LEGAL_BASES = ("consent", "contract", "legitimate_interest", "legal_obligation")
ACTIVE = ("programada", "en_cola", "llamando", "en_curso")
SCHEMA_VERSION = "2026-06-01"


def khash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def new_key(env: str) -> str:
    return f"vl_{env}_" + secrets.token_urlsafe(32)


# ---------- Standard call status ----------
def std_status(ld: dict) -> str:
    st, phase = ld.get("status"), ld.get("call_phase") or ""
    if st == "programada":
        return "scheduled"
    if st == "en_cola":
        return "queued"
    if st == "cancelada":
        return "cancelled"
    if st in ("llamando", "en_curso"):
        return "in_progress" if phase == "in-progress" or st == "en_curso" else "ringing" if phase == "ringing" else "queued"
    if st in ("sin_respuesta", "buzon"):
        return "busy" if "busy" in (ld.get("ended_reason") or "") else "no_answer"
    if st in ("fallida", "no_llamar"):
        return "failed"
    return "completed"


def call_out(ld: dict, full: bool = True) -> dict:
    st = std_status(ld)
    out = {"id": str(ld["_id"]), "call_id": str(ld["_id"]), "object": "call", "status": st, "status_detail": ld.get("status"),
           "agent_id": ld.get("agent_id"), "direction": "inbound" if ld.get("direction") == "entrante" else "outbound",
           "to": ld.get("phone"), "name": ld.get("name"), "source": ld.get("source"), "sandbox": bool(ld.get("sandbox")),
           "purpose_category": ld.get("purpose_category"), "legal_basis": ld.get("legal_basis"),
           "scheduled_at": ld.get("run_at"), "created_at": ld.get("created_at"), "updated_at": ld.get("updated_at"),
           "duration_seconds": ld.get("duration_seconds"), "ended_reason": ld.get("ended_reason") or None,
           "error": ld.get("error") or None, "metadata": ld.get("metadata") or {}}
    if full and st in ("completed", "no_answer", "busy", "failed"):
        score = ld.get("interest_score")
        out["result"] = {
            "summary": ld.get("summary") or None, "answers": ld.get("answers") or None,
            "outcome": ld.get("status"), "appointment_booked": ld.get("status") == "cita_agendada",
            "do_not_call_requested": ld.get("status") == "no_llamar",
            "interest_score": score,
            "interest_score_note": "0-100 estimado por la IA a partir de la conversación; null si no hubo datos suficientes",
            "billed_minutes": round((ld.get("duration_seconds") or 0) / 60, 2)}
        out["transcript"] = ld.get("messages") or []
    return out


# ---------- Limits ----------
async def limits_for(tenant_id: str) -> dict:
    u = await db.users.find_one({"_id": ObjectId(tenant_id)}, {"api_limits": 1, "calling_hours": 1}) or {}
    return {**DEFAULT_LIMITS, **(u.get("api_limits") or {}), "calling_hours": u.get("calling_hours") or DEFAULT_HOURS}


async def hit(bucket: str, limit: int) -> None:
    """Fixed-window counter per minute, atomic in MongoDB. Raises 429 when exceeded."""
    now = int(time.time())
    win = now - now % 60
    doc = await db.api_rate.find_one_and_update({"_id": f"{bucket}:{win}"}, {"$inc": {"n": 1}, "$setOnInsert": {
        "exp": datetime.fromtimestamp(win + 120, timezone.utc)}}, upsert=True, return_document=True)
    if doc["n"] > limit:
        raise HTTPException(429, {"code": "rate_limited", "detail": f"Límite de {limit} peticiones por minuto superado.",
                                  "retry_after": win + 60 - now}, headers={"Retry-After": str(win + 60 - now)})


_locks: dict = {}


def tenant_lock(tid: str) -> asyncio.Lock:
    return _locks.setdefault(tid, asyncio.Lock())


def window_ok(country: str, hours: dict, at: datetime) -> tuple[bool, str]:
    cfg = hours.get(country) or DEFAULT_HOURS.get(country) or DEFAULT_HOURS["ES"]
    loc = at.astimezone(S.tz_of(country))
    for i in range(8):
        day = loc + timedelta(days=i)
        span = cfg["weekdays"] if day.weekday() < 5 else cfg["saturday"] if day.weekday() == 5 else cfg["sunday"]
        if not span:
            continue
        start = day.replace(hour=int(span[0][:2]), minute=int(span[0][3:]), second=0, microsecond=0)
        end = day.replace(hour=int(span[1][:2]), minute=int(span[1][3:]), second=0, microsecond=0)
        if i == 0 and start <= loc < end:
            return True, ""
        if (i == 0 and loc < start) or i > 0:
            return False, start.isoformat()
    return False, ""


# ---------- Idempotency ----------
async def idem_begin(tid: str, key: str, body: dict) -> dict | None:
    if not key:
        return None
    if len(key) > 100:
        raise HTTPException(422, {"code": "invalid_idempotency_key", "detail": "Idempotency-Key admite hasta 100 caracteres."})
    h = hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()
    _id = f"{tid}:{key}"
    try:
        await db.api_idem.insert_one({"_id": _id, "hash": h, "created_at": datetime.now(timezone.utc)})
        return None
    except Exception:  # noqa: BLE001  duplicate key
        doc = await db.api_idem.find_one({"_id": _id}) or {}
    if doc.get("hash") != h:
        raise HTTPException(422, {"code": "idempotency_mismatch", "detail": "Esta Idempotency-Key ya se usó con otro contenido."})
    if "response" not in doc:
        raise HTTPException(409, {"code": "idempotency_in_progress", "detail": "Hay una petición igual en curso. Reintenta en unos segundos."})
    return doc


async def idem_save(tid: str, key: str, status: int, response: dict) -> None:
    if key:
        await db.api_idem.update_one({"_id": f"{tid}:{key}"}, {"$set": {"status": status, "response": response}})


# ---------- Webhooks ----------
def check_url(url: str) -> None:
    """SSRF protection: https only, public hostnames resolving to public IPs."""
    u = urlparse(url)
    if u.scheme != "https" or not u.hostname or u.username or u.password:
        raise ValueError("La URL debe ser https:// pública y sin credenciales")
    if u.port not in (None, 443, 8443):
        raise ValueError("Solo se permiten los puertos 443 u 8443")
    try:
        infos = socket.getaddrinfo(u.hostname, u.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise ValueError("No se puede resolver el dominio de la URL")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global or ip.is_multicast:
            raise ValueError("La URL apunta a una dirección privada o interna")


def sign(secret: str, ts: int, body: bytes) -> str:
    return hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()


async def emit(tenant_id: str, event: str, ld: dict) -> None:
    subs = await db.webhooks.find({"tenant_id": tenant_id, "active": True, "events": event}).to_list(20)
    if not subs:
        return
    data = call_out(ld, full=event in ("call.completed", "call.no_answer", "call.failed"))
    for s in subs:
        if bool(s.get("sandbox")) != bool(ld.get("sandbox")):
            continue
        payload = {"id": f"evt_{uuid.uuid4().hex}", "type": event, "schema_version": SCHEMA_VERSION,
                   "created_at": now_iso(), "data": data}
        await db.webhook_deliveries.insert_one({"webhook_id": str(s["_id"]), "tenant_id": tenant_id, "event_id": payload["id"],
                                                "event": event, "payload": payload, "status": "pending", "attempts": 0,
                                                "next_at": now_iso(), "created_at": now_iso()})


async def on_lead_change(lead_id) -> None:
    """Emit the lifecycle event for a call whenever its standard status changes."""
    ld = await db.leads.find_one({"_id": ObjectId(lead_id) if isinstance(lead_id, str) else lead_id})
    if not ld:
        return
    st = std_status(ld)
    event = {"in_progress": "call.started", "completed": "call.completed", "no_answer": "call.no_answer",
             "busy": "call.no_answer", "failed": "call.failed", "cancelled": "call.cancelled"}.get(st)
    if not event or ld.get("api_last_event") == event:
        return
    res = await db.leads.update_one({"_id": ld["_id"], "api_last_event": ld.get("api_last_event")}, {"$set": {"api_last_event": event}})
    if res.modified_count:
        await emit(ld["tenant_id"], event, ld)


async def deliver_one(d: dict) -> None:
    sub = await db.webhooks.find_one({"_id": ObjectId(d["webhook_id"])})
    if not sub or not sub.get("active"):
        await db.webhook_deliveries.update_one({"_id": d["_id"]}, {"$set": {"status": "skipped"}})
        return
    body = json.dumps(d["payload"], ensure_ascii=False, separators=(",", ":")).encode()
    ts = int(time.time())
    code, err = None, ""
    try:
        check_url(sub["url"])
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as c:
            r = await c.post(sub["url"], content=body, headers={
                "Content-Type": "application/json", "User-Agent": "VozLeads-Webhooks/1.0", "VozLeads-Event-Id": d["event_id"],
                "VozLeads-Event-Type": d["event"], "VozLeads-Timestamp": str(ts),
                "VozLeads-Signature": f"t={ts},v1={sign(sub['secret'], ts, body)}"})
        code = r.status_code
        ok = 200 <= code < 300
    except (ValueError, httpx.HTTPError) as e:
        ok, err = False, str(e)[:200] or e.__class__.__name__
    attempts = d["attempts"] + 1
    upd = {"attempts": attempts, "last_status": code, "last_error": err, "last_attempt_at": now_iso()}
    if ok:
        upd["status"] = "delivered"
    elif attempts >= 8:
        upd["status"] = "failed"
    else:
        upd.update(status="pending", next_at=(datetime.now(timezone.utc) + timedelta(seconds=30 * 2 ** (attempts - 1))).isoformat())
    await db.webhook_deliveries.update_one({"_id": d["_id"]}, {"$set": upd})
    await db.webhooks.update_one({"_id": sub["_id"]}, {"$set": {"last_delivery_at": now_iso(), "last_status": code, "last_error": err}})


# ---------- Workers ----------
async def run_call(lead_id: ObjectId) -> None:
    ld = await db.leads.find_one({"_id": lead_id})
    if not ld or ld["status"] != "en_cola":
        return
    if ld.get("sandbox"):
        await simulate(ld)
        return
    agent = await db.agents.find_one({"_id": ObjectId(ld["agent_id"])})
    if not agent:
        await db.leads.update_one({"_id": lead_id}, {"$set": {"status": "fallida", "error": "Agente eliminado", "updated_at": now_iso()}})
    else:
        await db.leads.update_one({"_id": lead_id}, {"$set": {"status": "llamando", "updated_at": now_iso()}})
        await S.dial(agent, {**ld, "status": "llamando"})
    await on_lead_change(lead_id)


async def simulate(ld: dict) -> None:
    lid = ld["_id"]
    for phase in ("ringing", "in-progress"):
        await db.leads.update_one({"_id": lid}, {"$set": {"status": "llamando", "call_phase": phase, "updated_at": now_iso()}})
        await on_lead_change(lid)
        await asyncio.sleep(2)
    await db.leads.update_one({"_id": lid}, {"$set": {
        "status": "atendida", "call_phase": "ended", "ended_reason": "sandbox", "simulated_duration": 42,
        "summary": "Llamada simulada (sandbox): no se realizó ninguna llamada real.", "answers": "",
        "messages": [{"role": "assistant", "message": "Hola, esto es una llamada simulada."}], "updated_at": now_iso()}})
    await on_lead_change(lid)


async def worker() -> None:
    import saas
    await asyncio.sleep(20)
    stale = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    await db.leads.update_many({"status": "en_cola", "vapi_call_id": None, "updated_at": {"$lt": stale}},
                               {"$set": {"status": "fallida", "error": "Interrumpida por un reinicio del servicio (no se llamó)"}})
    tick = 0
    while True:
        try:
            while job := await db.leads.find_one_and_update({"status": "programada", "run_at": {"$lte": now_iso()}},
                                                            {"$set": {"status": "en_cola", "updated_at": now_iso()}}):
                asyncio.create_task(run_call(job["_id"]))
            while d := await db.webhook_deliveries.find_one_and_update({"status": "pending", "next_at": {"$lte": now_iso()}},
                                                                     {"$set": {"status": "sending"}}):
                asyncio.create_task(deliver_one(d))
            tick += 1
            if tick % 6 == 0:
                await saas.dispatch_due()
            if tick % 12 == 3:
                import reminders
                await reminders.run_due()
            if tick % 120 == 7:
                import saas
                import billing
                await saas.usage_alerts()
                await billing.apply_pending_downgrades()
            if tick % 720 == 1:
                import privacy
                await privacy.purge_expired()
        except Exception as e:  # noqa: BLE001
            log.warning("API worker error: %s", e)
        await asyncio.sleep(5)


async def ensure_indexes() -> None:
    await db.api_keys.create_index("key_hash")
    await db.api_keys.create_index("tenant_id")
    await db.leads.create_index([("status", 1), ("run_at", 1)])
    await db.leads.create_index([("tenant_id", 1), ("status", 1)])
    await db.scheduled_calls.create_index([("status", 1), ("run_at", 1)])
    await db.webhooks.create_index("tenant_id")
    await db.webhook_deliveries.create_index([("status", 1), ("next_at", 1)])
    await db.webhook_deliveries.create_index([("webhook_id", 1), ("created_at", -1)])
    await db.api_idem.create_index("created_at", expireAfterSeconds=86400)
    await db.api_rate.create_index("exp", expireAfterSeconds=0)
