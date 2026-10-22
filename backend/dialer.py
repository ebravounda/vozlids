"""Browser phone: tenants call from their own number through a dedicated Zadarma SIP (WebRTC widget)."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import auth as A
import costs_real as CR
import plan_limits as PL
import zadarma as Z
from db import db

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


@router.get("/dialer/history")
async def dialer_history(user=CurrentUser):
    await PL.require(user["id"], "dialer")
    sips = {ln["dialer_sip_id"]: ln["number"] for ln in await _lines(user["id"]) if ln.get("dialer_sip_id")}
    if not sips:
        return {"calls": [], "minutes": 0, "error": ""}
    cache = await db.dialer_history.find_one({"_id": user["id"]}) or {}
    at = CR._parse(cache.get("at", ""))
    rows, error = cache.get("rows") or [], ""
    if not at or datetime.now(timezone.utc) - at > HISTORY_TTL:
        start = datetime.now(CR.MADRID).replace(day=1, hour=0, minute=0, second=0)
        try:
            rows = []
            for sip in sips:
                rows += (await Z.call("GET", "/v1/statistics/", {"start": start.strftime("%Y-%m-%d %H:%M:%S"),
                                                                 "end": datetime.now(CR.MADRID).strftime("%Y-%m-%d %H:%M:%S"),
                                                                 "sip": sip, "limit": 1000})).get("stats") or []
            await db.dialer_history.update_one({"_id": user["id"]}, {"$set": {"rows": rows, "at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
        except Z.ZadarmaError as e:
            error = "Zadarma está ocupado, el historial se actualizará en un minuto." if "limit" in str(e).lower() else str(e)
    admin = user.get("role") == "admin"
    calls = [{"id": str(r.get("id")), "start": r.get("callstart"), "to": r.get("to"), "destination": r.get("description"),
              "status": r.get("disposition"), "seconds": int(CR._num(r.get("billseconds"))),
              "from_number": sips.get(str(r.get("sip")), ""),
              **({"cost": round(CR._num(r.get("billcost")), 4), "currency": r.get("currency")} if admin else {})}
             for r in sorted(rows, key=lambda x: x.get("callstart") or "", reverse=True)]
    return {"calls": calls, "minutes": round(sum(c["seconds"] for c in calls) / 60, 1), "error": error}
