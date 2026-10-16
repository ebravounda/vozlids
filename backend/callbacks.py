"""'Llámame más tarde': the agent schedules a new call itself (max 2 per contact, Mon–Fri 09:00–21:00 local time)."""
import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import services as S
import vapi
from auth import get_current_user
from db import db
from models import Lead, now_iso

router = APIRouter(prefix="/api")
MAX_CALLBACKS = 2
OPEN_H, CLOSE_H = 9, 21
DEFAULT_DELAY = timedelta(hours=2)
SLOT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T([01]\d|2[0-3]):[0-5]\d$")


def in_window(dt: datetime) -> bool:
    return dt.weekday() < 5 and OPEN_H <= dt.hour < CLOSE_H


def fit_window(dt: datetime) -> datetime:
    dt = dt.replace(second=0, microsecond=0)
    while not in_window(dt):
        if dt.weekday() < 5 and dt.hour < OPEN_H:
            dt = dt.replace(hour=OPEN_H, minute=0)
        else:
            dt = (dt + timedelta(days=1)).replace(hour=OPEN_H, minute=0)
    return dt


def target(args: dict, now: datetime) -> datetime:
    t = str(args.get("time") or "").strip()
    try:
        hm = datetime.strptime(t, "%H:%M").time() if t else None
        d = date.fromisoformat(str(args.get("date") or "").strip()) if args.get("date") else None
    except ValueError:
        hm, d = None, None
    if not hm:
        return fit_window(now + DEFAULT_DELAY)
    dt = datetime.combine(d or now.date(), hm, now.tzinfo)
    if dt <= now + timedelta(minutes=5):
        dt = dt + timedelta(days=1) if not d else now + DEFAULT_DELAY
    return fit_window(dt)


def label(dt: datetime) -> str:
    return f"{S._day_label(dt.date())} a las {dt:%H:%M}"


async def schedule(lead: dict, args: dict) -> dict:
    count = lead.get("callback_count") or 0
    if count >= MAX_CALLBACKS:
        return {"ok": False, "error": "Ya se ha reprogramado el máximo de veces. No prometas otra llamada automática: "
                                      "dile que el equipo le contactará y despídete."}
    agent = await db.agents.find_one({"_id": ObjectId(lead["agent_id"])}) if ObjectId.is_valid(lead["agent_id"]) else None
    if not agent:
        return {"ok": False, "error": "No se puede programar ahora. Dile que el equipo le llamará y despídete."}
    tz = S.tz_of(agent.get("country", "ES"))
    now = datetime.now(tz)
    when = target(args, now)
    asked = str(args.get("time") or "").strip()
    moved = bool(asked) and when.strftime("%H:%M") != asked
    run_at, local = when.astimezone(timezone.utc).isoformat(), when.strftime("%Y-%m-%dT%H:%M")
    cid = lead.get("callback_id")
    moved_existing = cid and ObjectId.is_valid(cid) and (await db.leads.update_one(
        {"_id": ObjectId(cid), "status": "programada"}, {"$set": {"run_at": run_at, "callback_at": local, "updated_at": now_iso()}})).matched_count
    if not moved_existing:
        base = lead.get("purpose") or vapi.OBJECTIVES.get(agent["objective"], "")
        new = Lead(tenant_id=lead["tenant_id"], agent_id=lead["agent_id"], agent_name=lead.get("agent_name") or agent["name"],
                   name=lead["name"], phone=lead["phone"], email=lead.get("email") or "", consent=lead.get("consent", True),
                   is_test=lead.get("is_test", False), source=lead.get("source") or "form", max_seconds=lead.get("max_seconds") or 0,
                   purpose=("Le vuelves a llamar porque en la llamada anterior te pidió que le llamaras más tarde. "
                            "Recuérdaselo con naturalidad al empezar. " + base)[:2000],
                   greeting="Hola {nombre}, soy {agente}, de {empresa}. Te llamo como quedamos. ¿Te viene bien ahora?",
                   status="programada", callback_of=str(lead["_id"]), callback_count=count + 1, callback_at=local)
        res = await db.leads.insert_one({**new.to_mongo(), "run_at": run_at})
        lead["callback_id"] = str(res.inserted_id)
    await db.leads.update_one({"_id": lead["_id"]}, {"$set": {"callback_id": lead["callback_id"], "callback_at": local,
                                                              "updated_at": now_iso()}})
    tip = " La hora que pidió está fuera del horario de llamadas (lunes a viernes de 9 a 21), díselo y confírmale esta." if moved else ""
    return {"ok": True, "rellamada": label(when), "nota": "Confírmale esta hora y despídete." + tip}


async def cancel_for(lead: dict) -> None:
    if lead.get("callback_id") and ObjectId.is_valid(lead["callback_id"]):
        await db.leads.update_one({"_id": ObjectId(lead["callback_id"]), "status": "programada"},
                                  {"$set": {"status": "cancelada", "updated_at": now_iso()}})
        await db.leads.update_one({"_id": lead["_id"]}, {"$set": {"callback_id": None, "callback_at": ""}})


def _out(d: dict) -> dict:
    return {"id": str(d["_id"]), "kind": "callback", "start": d["callback_at"], "lead_name": d["name"], "lead_phone": d["phone"],
            "lead_id": d.get("callback_of"), "callback_count": d.get("callback_count", 1), "duration_minutes": 15,
            "agent_name": d.get("agent_name", "")}


@router.get("/callbacks")
async def list_callbacks(start: Optional[str] = None, end: Optional[str] = None, user=Depends(get_current_user)):
    q = {"tenant_id": user["id"], "status": "programada", "callback_of": {"$ne": None},
         "callback_at": {"$gte": start or "", **({"$lt": end} if end else {})}}
    return [_out(d) for d in await db.leads.find(q).sort("callback_at", 1).to_list(500)]


class CallbackPatch(BaseModel):
    start: str = Field(max_length=16)


async def _own(cb_id: str, tid: str) -> dict:
    doc = await db.leads.find_one({"_id": ObjectId(cb_id), "tenant_id": tid, "status": "programada",
                                   "callback_of": {"$ne": None}}) if ObjectId.is_valid(cb_id) else None
    if not doc:
        raise HTTPException(404, "Rellamada no encontrada o ya realizada")
    return doc


@router.patch("/callbacks/{cb_id}")
async def move_callback(cb_id: str, body: CallbackPatch, user=Depends(get_current_user)):
    doc = await _own(cb_id, user["id"])
    if not SLOT_RE.match(body.start):
        raise HTTPException(422, "Fecha y hora no válidas (AAAA-MM-DDTHH:MM)")
    agent = await db.agents.find_one({"_id": ObjectId(doc["agent_id"])}, {"country": 1}) if ObjectId.is_valid(doc["agent_id"]) else None
    tz = S.tz_of((agent or {}).get("country", "ES"))
    when = datetime.strptime(body.start, "%Y-%m-%dT%H:%M").replace(tzinfo=tz)
    if when <= datetime.now(tz):
        raise HTTPException(422, "Elige una hora futura")
    if not in_window(when):
        raise HTTPException(422, "Las rellamadas solo pueden ser de lunes a viernes, de 9:00 a 21:00")
    await db.leads.update_one({"_id": doc["_id"]}, {"$set": {"run_at": when.astimezone(timezone.utc).isoformat(),
                                                             "callback_at": body.start, "updated_at": now_iso()}})
    if doc.get("callback_of") and ObjectId.is_valid(doc["callback_of"]):
        await db.leads.update_one({"_id": ObjectId(doc["callback_of"])}, {"$set": {"callback_at": body.start}})
    return _out({**doc, "callback_at": body.start})


@router.delete("/callbacks/{cb_id}")
async def cancel_callback(cb_id: str, user=Depends(get_current_user)):
    doc = await _own(cb_id, user["id"])
    await db.leads.update_one({"_id": doc["_id"]}, {"$set": {"status": "cancelada", "updated_at": now_iso()}})
    if doc.get("callback_of") and ObjectId.is_valid(doc["callback_of"]):
        await db.leads.update_one({"_id": ObjectId(doc["callback_of"])}, {"$set": {"callback_id": None, "callback_at": ""}})
    return {"ok": True}
