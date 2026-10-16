"""Platform-wide blocklist (phones, emails, domains) + live call control for the super admin."""
import re
from datetime import datetime, timedelta, timezone
from typing import Literal
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import vapi
from db import db
from extra_routes import require_admin
from models import now_iso

router = APIRouter(prefix="/api")
DISPOSABLE = {
    "mailinator.com", "10minutemail.com", "guerrillamail.com", "guerrillamail.info", "sharklasers.com", "yopmail.com", "yopmail.fr",
    "tempmail.com", "temp-mail.org", "throwawaymail.com", "trashmail.com", "getnada.com", "nada.email", "maildrop.cc", "dispostable.com",
    "fakeinbox.com", "mintemail.com", "mohmal.com", "emailondeck.com", "tempr.email", "moakt.com", "mailnesia.com", "spamgourmet.com",
    "mytemp.email", "tempmailo.com", "burnermail.io", "inboxkitten.com", "1secmail.com", "emailfake.com", "tmpmail.org", "tmail.ws",
}
ABUSE_PER_HOUR = 5
BLOCKED_MSG = "No podemos procesar esta solicitud."


def _digits(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def blocked_phone(phone: str) -> dict | None:
    d = _digits(phone)
    if len(d) < 6:
        return None
    return await db.blocklist.find_one({"kind": "phone", "value": d, "$or": [{"expires_at": None}, {"expires_at": {"$gt": _now()}}]})


async def blocked_email(email: str) -> str | None:
    e = (email or "").strip().lower()
    if "@" not in e:
        return None
    dom = e.rsplit("@", 1)[1]
    if dom in DISPOSABLE:
        return "Usa un email permanente (no se admiten emails temporales)."
    if await db.blocklist.find_one({"$or": [{"kind": "email", "value": e}, {"kind": "domain", "value": dom}],
                                    "$and": [{"$or": [{"expires_at": None}, {"expires_at": {"$gt": _now()}}]}]}):
        return BLOCKED_MSG
    return None


async def guard_public(phone: str = "", email: str = "") -> None:
    """For demos/forms/widget: raise if blocked; auto-block a phone that floods requests."""
    if phone and await blocked_phone(phone):
        raise HTTPException(403, BLOCKED_MSG)
    if email and (msg := await blocked_email(email)):
        raise HTTPException(403 if msg == BLOCKED_MSG else 422, msg)
    d = _digits(phone)
    if len(d) < 6:
        return
    hour = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    tail = d[-9:]
    n = await db.leads.count_documents({"phone": {"$regex": f"{tail}$"}, "direction": {"$ne": "entrante"}, "created_at": {"$gt": hour}})
    n += await db.info_requests.count_documents({"phone": {"$regex": f"{tail}$"}, "created_at": {"$gt": hour}})
    if n >= ABUSE_PER_HOUR:
        await db.blocklist.update_one({"kind": "phone", "value": d}, {"$setOnInsert": {
            "kind": "phone", "value": d, "reason": f"Automático: más de {ABUSE_PER_HOUR} solicitudes en 1 hora", "source": "auto",
            "created_at": now_iso(), "expires_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()}}, upsert=True)
        raise HTTPException(429, "Demasiadas solicitudes desde este número. Inténtalo mañana.")


# ---------- Admin: blocklist ----------
class BlockIn(BaseModel):
    kind: Literal["phone", "email", "domain"]
    value: str = Field(min_length=3, max_length=200)
    reason: str = Field("", max_length=200)


def _norm(kind: str, value: str) -> str:
    v = value.strip().lower()
    if kind == "phone":
        d = _digits(v)
        if len(d) < 6:
            raise HTTPException(422, "Número no válido")
        return d
    if kind == "email" and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
        raise HTTPException(422, "Email no válido")
    if kind == "domain":
        v = v.lstrip("@")
        if "." not in v or "@" in v:
            raise HTTPException(422, "Dominio no válido (ej. ejemplo.com)")
    return v


@router.get("/admin/blocklist")
async def list_blocks(user=Depends(require_admin)):
    rows = await db.blocklist.find({"$or": [{"expires_at": None}, {"expires_at": {"$gt": _now()}}]}).sort("created_at", -1).to_list(500)
    return [{"id": str(r["_id"]), "kind": r["kind"], "value": ("+" + r["value"]) if r["kind"] == "phone" else r["value"],
             "reason": r.get("reason", ""), "source": r.get("source", "manual"), "created_at": r["created_at"], "expires_at": r.get("expires_at")}
            for r in rows]


@router.post("/admin/blocklist")
async def add_block(body: BlockIn, user=Depends(require_admin)):
    v = _norm(body.kind, body.value)
    await db.blocklist.update_one({"kind": body.kind, "value": v}, {"$set": {
        "kind": body.kind, "value": v, "reason": body.reason.strip(), "source": "manual", "created_at": now_iso(), "expires_at": None}}, upsert=True)
    return {"ok": True}


@router.delete("/admin/blocklist/{bid}")
async def del_block(bid: str, user=Depends(require_admin)):
    from bson import ObjectId
    if not ObjectId.is_valid(bid) or not (await db.blocklist.delete_one({"_id": ObjectId(bid)})).deleted_count:
        raise HTTPException(404, "Bloqueo no encontrado")
    return {"ok": True}


# ---------- Admin: live call control ----------
async def _vapi_call(cid: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{vapi.VAPI_URL}/call/{cid}", headers=vapi._headers())
    if r.status_code >= 400:
        raise HTTPException(404, "Llamada no encontrada")
    return r.json()


@router.post("/admin/monitor/calls/{cid}/hangup")
async def hangup(cid: str, user=Depends(require_admin)):
    call = await _vapi_call(cid)
    if call.get("status") == "ended":
        return {"ok": True, "already_ended": True}
    url = (call.get("monitor") or {}).get("controlUrl")
    if not url:
        raise HTTPException(409, "Esta llamada no permite control en directo.")
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(url, json={"type": "end-call"}, headers=vapi._headers())
    if r.status_code >= 400:
        raise HTTPException(502, f"Vapi no pudo colgar la llamada ({r.status_code}).")
    await db.leads.update_one({"vapi_call_id": cid}, {"$set": {"ended_by_admin": True, "updated_at": now_iso()}})
    return {"ok": True}


@router.get("/admin/monitor/calls/{cid}/listen")
async def listen_url(cid: str, user=Depends(require_admin)):
    call = await _vapi_call(cid)
    url = (call.get("monitor") or {}).get("listenUrl")
    if not url or call.get("status") == "ended":
        raise HTTPException(409, "No se puede escuchar esta llamada (ya terminó o no tiene escucha activa).")
    return {"url": url}


async def ensure_indexes() -> None:
    await db.blocklist.create_index([("kind", 1), ("value", 1)], unique=True)
