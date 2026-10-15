"""GDPR tools: contact data export/erasure, transcript retention purge and API request log."""
import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
import vapi
from auth import get_current_user
from countries import norm_phone
from db import db
from models import now_iso

log = logging.getLogger("vozlead.privacy")
RETENTION_CHOICES = (0, 30, 90, 180, 365)
LOG_DAYS = 30
router = APIRouter(prefix="/api/privacy")


class SubjectIn(BaseModel):
    phone: str = Field("", max_length=25)
    email: str = Field("", max_length=200)
    country: Optional[Literal["ES", "CL"]] = None


# ---------- Contact lookup ----------
async def _subject(tid: str, body: SubjectIn) -> tuple[str, str]:
    if not body.phone.strip() and not body.email.strip():
        raise HTTPException(422, {"code": "subject_required", "detail": "Indica el teléfono o el email del contacto."})
    phone = ""
    if body.phone.strip():
        country = body.country or (await db.users.find_one({"_id": ObjectId(tid)}, {"country": 1}) or {}).get("country", "ES")
        try:
            phone = norm_phone(body.phone, country)
        except (ValueError, HTTPException):
            raise HTTPException(422, {"code": "invalid_phone", "detail": "Número no válido."})
    return phone, body.email.strip().lower()


def _match(tid: str, phone: str, email: str, phone_f: str = "phone") -> dict:
    ors = ([{phone_f: phone}] if phone else []) + ([{"email": re.compile(f"^{re.escape(email)}$", re.I)}] if email else [])
    return {"tenant_id": tid, "$or": ors}


def _clean(d: dict) -> dict:
    return {("id" if k == "_id" else k): (str(v) if isinstance(v, ObjectId) else v.isoformat() if isinstance(v, datetime) else v)
            for k, v in d.items() if k not in ("tenant_id", "key_hash")}


async def export_subject(tid: str, phone: str, email: str) -> dict:
    leads = await db.leads.find(_match(tid, phone, email)).sort("created_at", -1).to_list(2000)
    ids = [str(x["_id"]) for x in leads]
    appts = await db.appointments.find({"tenant_id": tid, "$or": [{"lead_id": {"$in": ids}}] + ([{"lead_phone": phone}] if phone else [])}).to_list(500)
    sched = await db.scheduled_calls.find(_match(tid, phone, email)).to_list(500)
    tickets = await db.support_tickets.find({"tenant_id": tid, "lead_id": {"$in": ids}}).to_list(500)
    dnc = await db.dnc.find({"tenant_id": tid, "phone": phone}).to_list(5) if phone else []
    await _audit(tid, "export", phone, email, {"calls": len(leads)})
    return {"object": "subject_export", "generated_at": now_iso(), "subject": {"phone": phone or None, "email": email or None},
            "calls": [_clean(x) for x in leads], "appointments": [_clean(x) for x in appts], "scheduled_calls": [_clean(x) for x in sched],
            "support_tickets": [_clean(x) for x in tickets], "do_not_call": [_clean(x) for x in dnc],
            "recordings_note": "Las grabaciones se descargan desde el panel mientras sigan disponibles."}


async def _drop_vapi(call_id: str) -> None:
    try:
        await vapi.delete(f"/call/{call_id}")
    except Exception as e:  # noqa: BLE001
        log.warning("No se pudo borrar la llamada %s del proveedor: %s", call_id, e)


async def erase_subject(tid: str, phone: str, email: str) -> dict:
    leads = await db.leads.find(_match(tid, phone, email), {"_id": 1, "vapi_call_id": 1, "created_at": 1, "duration_seconds": 1,
                                                            "agent_id": 1, "source": 1, "sandbox": 1, "cost": 1}).to_list(5000)
    ids = [str(x["_id"]) for x in leads]
    usage = [{"tenant_id": tid, **{k: x.get(k) for k in ("created_at", "duration_seconds", "agent_id", "source", "sandbox", "cost")},
              "archived_at": now_iso(), "reason": "rgpd_erase"} for x in leads if x.get("duration_seconds")]
    if usage:
        await db.usage_archive.insert_many(usage)
    for x in leads:
        if x.get("vapi_call_id"):
            await _drop_vapi(x["vapi_call_id"])
    appt_q = {"tenant_id": tid, "$or": [{"lead_id": {"$in": ids}}] + ([{"lead_phone": phone}] if phone else [])}
    import gcal
    async for ap in db.appointments.find(appt_q, {"google_event_id": 1}):
        await gcal.remove(tid, ap.get("google_event_id"))
    counts = {
        "calls": (await db.leads.delete_many({"_id": {"$in": [x["_id"] for x in leads]}})).deleted_count,
        "appointments": (await db.appointments.delete_many(appt_q)).deleted_count,
        "scheduled_calls": (await db.scheduled_calls.delete_many(_match(tid, phone, email))).deleted_count,
        "support_tickets": (await db.support_tickets.delete_many({"tenant_id": tid, "lead_id": {"$in": ids}})).deleted_count,
        "webhook_deliveries": (await db.webhook_deliveries.delete_many({"tenant_id": tid, "payload.data.id": {"$in": ids}})).deleted_count,
        "idempotency_cache": (await db.api_idem.delete_many({"_id": {"$regex": f"^{re.escape(tid)}:"}, "response.id": {"$in": ids}})).deleted_count,
        "recordings": sum(1 for x in leads if x.get("vapi_call_id"))}
    await _audit(tid, "erase", phone, email, counts)
    return {"object": "subject_erasure", "erased": True, "deleted": counts, "completed_at": now_iso(),
            "kept": "Si el número está en tu lista de exclusión se conserva para no volver a llamarle."}


async def _audit(tid: str, action: str, phone: str, email: str, counts: dict) -> None:
    ref = hashlib.sha256(f"{phone}|{email}".encode()).hexdigest()[:16]
    await db.privacy_log.insert_one({"tenant_id": tid, "action": action, "subject_ref": ref, "counts": counts, "created_at": now_iso()})


# ---------- Retention ----------
async def get_retention(tid: str) -> int:
    return int((await db.users.find_one({"_id": ObjectId(tid)}, {"transcript_retention_days": 1}) or {}).get("transcript_retention_days") or 0)


async def set_retention(tid: str, days: int) -> int:
    if days not in RETENTION_CHOICES:
        raise HTTPException(422, {"code": "invalid_retention", "detail": f"Valores permitidos: {', '.join(map(str, RETENTION_CHOICES))} (0 = nunca)."})
    await db.users.update_one({"_id": ObjectId(tid)}, {"$set": {"transcript_retention_days": days}})
    return days


async def purge_expired() -> int:
    """Delete transcripts and recordings older than each tenant's retention; keep the lead and its stats."""
    total = 0
    async for u in db.users.find({"transcript_retention_days": {"$gt": 0}}, {"transcript_retention_days": 1}):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=u["transcript_retention_days"])).isoformat()
        q = {"tenant_id": str(u["_id"]), "created_at": {"$lt": cutoff}, "transcript_purged_at": None,
             "status": {"$nin": ["programada", "en_cola", "llamando", "en_curso"]}}
        async for ld in db.leads.find(q, {"vapi_call_id": 1}).limit(2000):
            if ld.get("vapi_call_id"):
                await _drop_vapi(ld["vapi_call_id"])
            await db.leads.update_one({"_id": ld["_id"]}, {"$set": {"messages": [], "transcript": "", "recording_url": "",
                                                                    "transcript_purged_at": now_iso()}})
            total += 1
    if total:
        log.info("Retención: %s transcripciones y grabaciones eliminadas", total)
    return total


# ---------- API request log ----------
_PHONE = re.compile(r"(?<=/)\+?\d{6,15}(?=/|$)")


async def log_request(tid: str, key_id: str, method: str, path: str, status: int, ms: int, ip: str, rid: str) -> None:
    await db.api_request_logs.insert_one({"tenant_id": tid, "key_id": key_id, "method": method, "path": _PHONE.sub("***", path)[:200],
                                          "status": status, "duration_ms": ms, "ip": ip, "request_id": rid,
                                          "at": datetime.now(timezone.utc)})


async def ensure_indexes() -> None:
    await db.api_request_logs.create_index("at", expireAfterSeconds=LOG_DAYS * 86400)
    await db.api_request_logs.create_index([("key_id", 1), ("at", -1)])
    await db.privacy_log.create_index([("tenant_id", 1), ("created_at", -1)])
    await db.leads.create_index([("tenant_id", 1), ("phone", 1)])
    await db.usage_archive.create_index([("tenant_id", 1), ("created_at", 1)])


async def key_requests(tid: str, kid: str, limit: int, errors_only: bool) -> dict:
    q = {"tenant_id": tid, "key_id": kid, **({"status": {"$gte": 400}} if errors_only else {})}
    rows = await db.api_request_logs.find(q, {"_id": 0, "tenant_id": 0}).sort("at", -1).limit(limit).to_list(limit)
    agg = await db.api_request_logs.aggregate([{"$match": {"tenant_id": tid, "key_id": kid}}, {"$group": {
        "_id": None, "total": {"$sum": 1}, "errors": {"$sum": {"$cond": [{"$gte": ["$status", 400]}, 1, 0]}},
        "avg_ms": {"$avg": "$duration_ms"}}}]).to_list(1)
    s = agg[0] if agg else {"total": 0, "errors": 0, "avg_ms": 0}
    return {"summary": {"total": s["total"], "errors": s["errors"], "avg_ms": round(s["avg_ms"] or 0), "days": LOG_DAYS},
            "data": [{**r, "at": r["at"].replace(tzinfo=timezone.utc).isoformat()} for r in rows]}


# ---------- Dashboard (session auth) ----------
class RetentionIn(BaseModel):
    days: int


@router.get("/settings")
async def settings(user=Depends(get_current_user)):
    hist = await db.privacy_log.find({"tenant_id": user["id"]}, {"_id": 0, "tenant_id": 0}).sort("created_at", -1).to_list(20)
    purged = await db.leads.count_documents({"tenant_id": user["id"], "transcript_purged_at": {"$ne": None}})
    return {"retention_days": await get_retention(user["id"]), "choices": RETENTION_CHOICES, "history": hist, "purged_calls": purged}


@router.put("/retention")
async def dash_retention(body: RetentionIn, user=Depends(get_current_user)):
    return {"retention_days": await set_retention(user["id"], body.days)}


@router.post("/export")
async def dash_export(body: SubjectIn, user=Depends(get_current_user)):
    return await export_subject(user["id"], *await _subject(user["id"], body))


@router.post("/erase")
async def dash_erase(body: SubjectIn, user=Depends(get_current_user)):
    return await erase_subject(user["id"], *await _subject(user["id"], body))


@router.get("/keys/{kid}/requests")
async def dash_key_requests(kid: str, user=Depends(get_current_user), limit: int = Query(100, ge=1, le=500), errors_only: bool = False):
    return await key_requests(user["id"], kid, limit, errors_only)
