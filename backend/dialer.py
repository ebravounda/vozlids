"""Browser phone: tenants call from their own number through the line's Zadarma SIP (WebRTC widget)."""
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
    return await db.tenant_numbers.find({"tenant_id": tid, "status": "activo"}, {"number": 1, "sip_id": 1, "agent_id": 1, "extra": 1}) \
        .sort("extra", 1).to_list(20)


async def manual_ids() -> set:
    """Zadarma records that are keypad calls (excluded from AI-call cost matching)."""
    return {d["_id"] async for d in db.dialer_calls.find({}, {"_id": 1})}


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
    sip = line.get("sip_id")
    if not sip:
        raise HTTPException(400, "Tu número aún no tiene línea conectada. Escríbenos y la activamos.")
    try:
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
    """Pair the calls the browser reported with Zadarma's records and store them in dialer_calls (they count as plan minutes)."""
    st = await db.platform_settings.find_one({"_id": "dialer_sync"}) or {}
    at = CR._parse(st.get("tried_at", ""))
    if not force and at and datetime.now(timezone.utc) - at < HISTORY_TTL:
        return st.get("error", "")
    pending = await db.dialer_pending.find({"zadarma_id": None}).to_list(2000)
    error = ""
    if pending:
        since = min(CR._parse(p["created_at"]) for p in pending) - timedelta(minutes=10)
        try:
            rows = await CR._stats(since)
        except Z.ZadarmaError as e:
            rows, error = [], ("Zadarma está ocupado, el historial se actualizará en un minuto." if "limit" in str(e).lower() else str(e))
        taken = await manual_ids()
        sips: dict = {}
        for p in pending:
            if p["tenant_id"] not in sips:
                sips[p["tenant_id"]] = {ln["sip_id"]: ln["number"] for ln in await _lines(p["tenant_id"]) if ln.get("sip_id")}
            start, best = CR._parse(p["created_at"]), None
            for r in rows:
                when, rid = CR._row_time(r), str(r.get("id"))
                if rid in taken or str(r.get("sip")) not in sips[p["tenant_id"]] or not when or \
                        CR._digits(str(r.get("to") or ""))[-9:] != CR._digits(p.get("to") or "")[-9:]:
                    continue
                gap = abs((when - start).total_seconds())
                if gap <= 180 and (best is None or gap < best[0]):
                    best = (gap, r)
            if not best:
                continue
            r = best[1]
            rid = str(r.get("id"))
            taken.add(rid)
            await db.dialer_calls.update_one({"_id": rid}, {"$set": {
                "tenant_id": p["tenant_id"], "from_number": sips[p["tenant_id"]].get(str(r.get("sip")), ""), "sip": str(r.get("sip")),
                "created_at": CR._row_time(r).astimezone(timezone.utc).isoformat(), "start": r.get("callstart"), "to": r.get("to"),
                "destination": r.get("description"), "status": r.get("disposition"),
                "duration_seconds": int(CR._num(r.get("billseconds"))), "cost": round(CR._num(r.get("billcost")), 4),
                "currency": r.get("currency")}}, upsert=True)
            await db.dialer_pending.update_one({"_id": p["_id"]}, {"$set": {"zadarma_id": rid}})
    now = datetime.now(timezone.utc).isoformat()
    await db.platform_settings.update_one({"_id": "dialer_sync"}, {"$set": {"error": error, "tried_at": now}}, upsert=True)
    return error


async def _pending_seconds(tid: str) -> int:
    import saas
    q = {"tenant_id": tid, "zadarma_id": None, "created_at": {"$gte": saas.month_start()}}
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
    to: str = Field("", max_length=30)


class PendingEnd(BaseModel):
    seconds: int = Field(ge=0, le=36000)


@router.post("/dialer/pending")
async def dialer_pending(body: PendingIn, user=CurrentUser):
    """The browser reports a keypad call as soon as it is answered; Zadarma's real record replaces it later."""
    r = await db.dialer_pending.insert_one({"tenant_id": user["id"], "to": body.to, "seconds": 0, "zadarma_id": None,
                                            "created_at": datetime.now(timezone.utc).isoformat()})
    return {"id": str(r.inserted_id)}


@router.post("/dialer/pending/{pid}/end")
async def dialer_pending_end(pid: str, body: PendingEnd, user=CurrentUser):
    if ObjectId.is_valid(pid):
        await db.dialer_pending.update_one({"_id": ObjectId(pid), "tenant_id": user["id"]}, {"$set": {"seconds": body.seconds}})
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
