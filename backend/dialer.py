"""Browser phone: tenants call from their own number through a dedicated Zadarma SIP (WebRTC widget)."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from pydantic import BaseModel, Field

import auth as A
import costs_real as CR
import plan_limits as PL
import zadarma as Z
from db import db

log = logging.getLogger("vozlead.dialer")
router = APIRouter(prefix="/api")
CurrentUser = Depends(A.get_current_user)
KEY_TTL = timedelta(hours=48)
HISTORY_TTL = timedelta(minutes=2)


async def _lines(tid: str) -> list:
    return await db.tenant_numbers.find({"tenant_id": tid, "status": "activo"}, {"number": 1, "dialer_sip_id": 1, "agent_id": 1, "extra": 1}) \
        .sort("extra", 1).to_list(20)


async def dialer_sips() -> set:
    return {d["dialer_sip_id"] async for d in db.tenant_numbers.find({"dialer_sip_id": {"$nin": [None, ""]}}, {"dialer_sip_id": 1})}


@router.get("/dialer")
async def dialer_info(user=CurrentUser):
    return {"enabled": await PL.has(user["id"], "dialer"), "numbers": [ln["number"] for ln in await _lines(user["id"])]}


class SessionIn(BaseModel):
    number: str = ""


@router.post("/dialer/session")
async def dialer_session(body: SessionIn, user=CurrentUser):
    await PL.require(user["id"], "dialer")
    import saas
    if err := await saas._quota_error(user["id"]):
        raise HTTPException(400, err)
    lines = await _lines(user["id"])
    line = next((ln for ln in lines if ln["number"] == body.number), lines[0] if lines else None)
    if not line:
        raise HTTPException(400, "Aún no tienes un número activo. Pide uno en «Mi número».")
    try:
        sip = line.get("dialer_sip_id")
        if not sip:
            sip = await Z.create_sip(f"Teclado {line['number']}", Z.new_password(), line["number"])
            await db.tenant_numbers.update_one({"_id": line["_id"]}, {"$set": {"dialer_sip_id": sip}})
        cached = await db.dialer_keys.find_one({"_id": sip}) or {}
        at = CR._parse(cached.get("at", ""))
        if cached.get("key") and at and datetime.now(timezone.utc) - at < KEY_TTL:
            key = cached["key"]
        else:
            key = (await Z.call("GET", "/v1/webrtc/get_key/", {"sip": sip}))["key"]
            await db.dialer_keys.update_one({"_id": sip}, {"$set": {"key": key, "at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
    except Z.ZadarmaError as e:
        raise HTTPException(400, f"No se pudo preparar el teléfono: {e}")
    return {"key": key, "sip": sip, "number": line["number"]}


async def sync_calls(force: bool = False) -> str:
    """Copy this month's keypad calls from Zadarma into dialer_calls so they count towards plan minutes."""
    st = await db.platform_settings.find_one({"_id": "dialer_sync"}) or {}
    at = CR._parse(st.get("tried_at", ""))
    if not force and at and datetime.now(timezone.utc) - at < HISTORY_TTL:
        return st.get("error", "")
    owners = {d["dialer_sip_id"]: d async for d in db.tenant_numbers.find({"dialer_sip_id": {"$nin": [None, ""]}},
                                                                         {"dialer_sip_id": 1, "tenant_id": 1, "number": 1})}
    error = ""
    if owners:
        start = datetime.now(CR.MADRID).replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        try:
            rows = await CR._stats(start)
        except Z.ZadarmaError as e:
            rows, error = [], ("Zadarma está ocupado, el historial se actualizará en un minuto." if "limit" in str(e).lower() else str(e))
        for r in rows:
            line = owners.get(str(r.get("sip")))
            when = CR._row_time(r)
            if not line or not when:
                continue
            await db.dialer_calls.update_one({"_id": str(r.get("id"))}, {"$set": {
                "tenant_id": line["tenant_id"], "from_number": line["number"], "sip": str(r.get("sip")),
                "created_at": when.astimezone(timezone.utc).isoformat(), "start": r.get("callstart"), "to": r.get("to"),
                "destination": r.get("description"), "status": r.get("disposition"),
                "duration_seconds": int(CR._num(r.get("billseconds"))), "cost": round(CR._num(r.get("billcost")), 4),
                "currency": r.get("currency")}}, upsert=True)
    now = datetime.now(timezone.utc).isoformat()
    if not error:
        await db.dialer_pending.delete_many({"created_at": {"$lt": now}})
    await db.platform_settings.update_one({"_id": "dialer_sync"}, {"$set": {"at": now if not error else st.get("at", ""), "error": error,
                                                                            "tried_at": now}}, upsert=True)
    return error


async def _pending_seconds(tid: str) -> int:
    st = await db.platform_settings.find_one({"_id": "dialer_sync"}) or {}
    q = {"tenant_id": tid, "created_at": {"$gte": st.get("at", "")}}
    return sum([d.get("seconds", 0) async for d in db.dialer_pending.find(q)])


@router.get("/dialer/remaining")
async def dialer_remaining(user=CurrentUser):
    """Seconds of plan left for keypad calls (null = no limit)."""
    import saas
    u = await db.users.find_one({"_id": ObjectId(user["id"])}, {"plan_id": 1, "allow_overage": 1})
    plan = await db.plans.find_one({"_id": ObjectId(u["plan_id"])}, {"minutes": 1}) if u and u.get("plan_id") else None
    if not plan or u.get("allow_overage"):
        return {"seconds": None}
    left = plan["minutes"] * 60 - await saas.minutes_used(user["id"]) * 60 - await _pending_seconds(user["id"])
    return {"seconds": max(0, int(left))}


class PendingIn(BaseModel):
    seconds: int = Field(ge=0, le=36000)


@router.post("/dialer/pending")
async def dialer_pending(body: PendingIn, user=CurrentUser):
    """Talk time the browser measured, counted until Zadarma's real record arrives."""
    if body.seconds:
        await db.dialer_pending.insert_one({"tenant_id": user["id"], "seconds": body.seconds, "created_at": datetime.now(timezone.utc).isoformat()})
    return {"ok": True}


@router.get("/dialer/history")
async def dialer_history(user=CurrentUser):
    await PL.require(user["id"], "dialer")
    import saas
    error = await sync_calls()
    admin = user.get("role") == "admin"
    docs = await db.dialer_calls.find({"tenant_id": user["id"], "created_at": {"$gte": saas.month_start()}}).sort("created_at", -1).to_list(2000)
    calls = [{"id": d["_id"], **{k: d.get(k) for k in ("start", "to", "destination", "status", "from_number")},
              "seconds": d.get("duration_seconds", 0), **({"cost": d.get("cost"), "currency": d.get("currency")} if admin else {})}
             for d in docs]
    return {"calls": calls, "minutes": round(sum(c["seconds"] for c in calls) / 60, 1), "error": error}


async def loop() -> None:
    while True:
        await asyncio.sleep(600)
        try:
            await sync_calls(force=True)
        except Exception as e:  # noqa: BLE001
            log.warning("Dialer sync failed: %s", e)
