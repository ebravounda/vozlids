"""Appointment reminders (AI call and/or email) configured per tenant."""
import asyncio
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import api_core as C
import emailer
import gcal
import saas
import services as S
from auth import get_current_user
from db import db
from models import Lead, now_iso

log = logging.getLogger("vozlead.reminders")
router = APIRouter(prefix="/api")
DEFAULT = {"call": False, "email": False, "hours_before": 24, "call_from": "09:00", "call_to": "21:00"}


class ReminderIn(BaseModel):
    call: bool
    email: bool
    hours_before: Literal[24, 3, 1]
    call_from: str = "09:00"
    call_to: str = "21:00"


async def settings_for(tid: str) -> dict:
    u = await db.users.find_one({"_id": ObjectId(tid)}, {"reminders": 1}) or {}
    return {**DEFAULT, **(u.get("reminders") or {})}


@router.get("/reminders")
async def get_settings(user=Depends(get_current_user)):
    sent = await db.appointments.count_documents({"tenant_id": user["id"], "reminder_sent_at": {"$ne": None}})
    return {**await settings_for(user["id"]), "sent_total": sent}


@router.put("/reminders")
async def put_settings(body: ReminderIn, user=Depends(get_current_user)):
    import plan_limits as PL
    if body.call or body.email:
        await PL.require(user["id"], "agenda_pro")
    import re
    if not all(re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", t) for t in (body.call_from, body.call_to)) or body.call_from >= body.call_to:
        raise HTTPException(422, "Horario de llamada no válido")
    await db.users.update_one({"_id": ObjectId(user["id"])}, {"$set": {"reminders": body.model_dump()}})
    return await settings_for(user["id"])


def _label(start: str) -> str:
    d = datetime.fromisoformat(start)
    return f"{S.DIAS[d.weekday()]} {d.day} de {S.MESES[d.month - 1]} a las {start[11:16]}"


async def _email(a: dict, owner: dict, token: str) -> bool:
    to = a.get("lead_email") or ""
    if not to and a.get("lead_id") and ObjectId.is_valid(a["lead_id"]):
        to = ((await db.leads.find_one({"_id": ObjectId(a["lead_id"])}, {"email": 1})) or {}).get("email", "")
    if not to:
        return False
    biz = owner.get("business_name", "")
    site = os.environ["APP_PUBLIC_URL"].rstrip("/")
    return await emailer.send(to, f"Recordatorio: tu cita con {biz}", f"Te esperamos el {_label(a['start'])}",
                              [("Empresa", biz), ("Fecha y hora", _label(a["start"]))], f"{site}/cita/{token}",
                              "Pulsa el botón para confirmar tu asistencia o anular la cita si no puedes venir.", "Confirmar o anular")


async def _call(a: dict, owner: dict, cfg: dict) -> str:
    if not a.get("lead_phone"):
        return "sin teléfono"
    country = owner.get("country", "ES")
    now_hm = datetime.now(S.tz_of(country)).strftime("%H:%M")
    if not (cfg["call_from"] <= now_hm < cfg["call_to"]):
        return "fuera de horario"
    if err := await saas.quota_error(a["tenant_id"]):
        return err
    agent = None
    if a.get("agent_id") and ObjectId.is_valid(a["agent_id"]):
        agent = await db.agents.find_one({"_id": ObjectId(a["agent_id"]), "tenant_id": a["tenant_id"]})
    agent = agent or await db.agents.find_one({"tenant_id": a["tenant_id"], "active": {"$ne": False}})
    if not agent:
        return "sin agente"
    biz = owner.get("business_name", "")
    when = _label(a["start"])
    purpose = (f"Recordatorio de cita. El cliente tiene una cita con {biz} el {when}. Recuérdasela y pregunta si podrá asistir. "
               "Si confirma, agradécelo y despídete. Si no puede venir o quiere cambiarla, dile que lo anotas y que el equipo le contactará "
               "para buscar otra hora; no reserves una cita nueva. Sé breve.")
    lead = Lead(tenant_id=a["tenant_id"], agent_id=str(agent["_id"]), agent_name=agent["name"], name=a["lead_name"], phone=a["lead_phone"],
                purpose=purpose, source="recordatorio",
                greeting=f"Hola {{nombre}}, soy {agent['name']}, de {biz}. Te llamo para recordarte tu cita del {when}. La llamada se graba. ¿Tienes un momento?")
    res = await db.leads.insert_one({**lead.to_mongo(), "status": "en_cola", "reminder_for": str(a["_id"]), "updated_at": now_iso()})
    asyncio.create_task(C.run_call(res.inserted_id))
    return ""


async def run_due() -> int:
    n = 0
    async for owner in db.users.find({"$or": [{"reminders.call": True}, {"reminders.email": True}]}, {"reminders": 1, "country": 1, "business_name": 1}):
        tid, cfg = str(owner["_id"]), {**DEFAULT, **owner["reminders"]}
        import plan_limits as PL
        if not await PL.has(tid, "agenda_pro"):
            continue
        now = datetime.now(S.tz_of(owner.get("country", "ES")))
        lo, hi = now.strftime("%Y-%m-%dT%H:%M"), (now + timedelta(hours=cfg["hours_before"])).strftime("%Y-%m-%dT%H:%M")
        pending = ([{"reminder_email_at": None}] if cfg["email"] else []) + ([{"reminder_call_at": None}] if cfg["call"] else [])
        q = {"tenant_id": tid, "start": {"$gt": lo, "$lte": hi}, "is_sample": {"$ne": True}, "$or": pending,
             "created_at": {"$lt": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()}}
        for a in await db.appointments.find(q).to_list(200):
            token = a.get("reminder_token") or secrets.token_urlsafe(18)
            upd, notes = {"reminder_token": token}, list(a.get("reminder_channels") or [])
            if cfg["email"] and not a.get("reminder_email_at"):
                upd["reminder_email_at"] = now_iso()
                notes.append("email" if await _email(a, owner, token) else "email no enviado (sin dirección)")
            if cfg["call"] and not a.get("reminder_call_at"):
                err = await _call(a, owner, cfg)
                if err != "fuera de horario":
                    upd["reminder_call_at"] = now_iso()
                    notes.append("llamada" if not err else f"llamada no realizada ({err})")
            if len(upd) > 1:
                upd.update(reminder_channels=notes, reminder_sent_at=a.get("reminder_sent_at") or now_iso())
                await db.appointments.update_one({"_id": a["_id"]}, {"$set": upd})
                n += 1
    return n


# ---------- Owner reminders: morning agenda + 1 h before each appointment ----------
DIGEST_HOUR, DIGEST_UNTIL = 8, 12


def _row(a: dict) -> tuple:
    who = " · ".join(x for x in (a.get("lead_name"), a.get("lead_phone")) if x)
    return (a["start"][11:16], who + (f" — {a['notes']}" if a.get("notes") else ""))


async def owner_reminders() -> int:
    """Remind the business owner to attend: daily summary at 8:00 and one email 1 h before each appointment."""
    n, url = 0, os.environ["APP_PUBLIC_URL"] + "/app/agenda"
    async for owner in db.users.find({"suspended": {"$ne": True}, "email": {"$nin": ["", None]}},
                                     {"email": 1, "country": 1, "business_name": 1, "agenda_digest_day": 1}):
        tid, now = str(owner["_id"]), datetime.now(S.tz_of(owner.get("country", "ES")))
        base = {"tenant_id": tid, "is_sample": {"$ne": True}}
        hi = (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
        recent = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        q = {**base, "start": {"$gt": now.strftime("%Y-%m-%dT%H:%M"), "$lte": hi}, "owner_hour_at": None, "created_at": {"$lt": recent}}
        for a in await db.appointments.find(q).to_list(50):
            if (await db.appointments.update_one({"_id": a["_id"], "owner_hour_at": None}, {"$set": {"owner_hour_at": now_iso()}})).modified_count:
                ok = await emailer.send(owner["email"], f"En 1 hora: cita con {a.get('lead_name') or 'un cliente'} a las {a['start'][11:16]}",
                                   "Tienes una cita dentro de una hora", [("Hora", a["start"][11:16]), ("Cliente", a.get("lead_name") or "—"),
                                   ("Teléfono", a.get("lead_phone") or "—"), ("Notas", a.get("notes") or "—")], url,
                                   intro="Recuerda atender a tu cliente. Si no puedes, cambia la cita desde tu agenda.", cta_label="Abrir mi agenda")
                if not ok:
                    await db.appointments.update_one({"_id": a["_id"]}, {"$set": {"owner_hour_at": None}})
                n += ok
        today = now.strftime("%Y-%m-%d")
        if DIGEST_HOUR <= now.hour < DIGEST_UNTIL and owner.get("agenda_digest_day") != today:
            await db.users.update_one({"_id": owner["_id"]}, {"$set": {"agenda_digest_day": today}})
            day = await db.appointments.find({**base, "start": {"$gte": f"{today}T00:00", "$lte": f"{today}T23:59"}}).sort("start", 1).to_list(100)
            if day:
                ok = await emailer.send(owner["email"], f"Tu agenda de hoy: {len(day)} {'cita' if len(day) == 1 else 'citas'}",
                                   "Estas son tus citas de hoy", [_row(a) for a in day], url,
                                   intro="Que no se te pase ningún cliente: aquí tienes todas las citas del día.", cta_label="Abrir mi agenda")
                if not ok:
                    await db.users.update_one({"_id": owner["_id"]}, {"$unset": {"agenda_digest_day": ""}})
                n += ok
    return n


# ---------- Public confirm / cancel page ----------
async def _by_token(token: str) -> dict:
    a = await db.appointments.find_one({"reminder_token": token}) if len(token) > 10 else None
    if not a:
        raise HTTPException(404, "Cita no encontrada o ya anulada")
    country = ((await db.users.find_one({"_id": ObjectId(a["tenant_id"])}, {"country": 1})) or {}).get("country", "ES")
    if a["start"] < datetime.now(S.tz_of(country)).strftime("%Y-%m-%dT%H:%M"):
        raise HTTPException(410, "Esta cita ya ha pasado")
    return a


@router.get("/public/appointment/{token}")
async def public_view(token: str):
    a = await _by_token(token)
    biz = ((await db.users.find_one({"_id": ObjectId(a["tenant_id"])}, {"business_name": 1})) or {}).get("business_name", "")
    return {"business": biz, "when": _label(a["start"]), "name": a["lead_name"].split(" ")[0], "confirmed": bool(a.get("confirmed_at"))}


@router.post("/public/appointment/{token}/confirm")
async def public_confirm(token: str):
    a = await _by_token(token)
    await db.appointments.update_one({"_id": a["_id"]}, {"$set": {"confirmed_at": now_iso()}})
    return {"ok": True}


@router.post("/public/appointment/{token}/cancel")
async def public_cancel(token: str):
    a = await _by_token(token)
    await db.appointments.delete_one({"_id": a["_id"]})
    gcal.unsync(a["tenant_id"], a.get("google_event_id"))
    if a.get("lead_id"):
        await db.leads.update_one({"_id": ObjectId(a["lead_id"])} if ObjectId.is_valid(a["lead_id"]) else {"_id": None},
                                  {"$set": {"appointment_id": None, "status": "calificado", "updated_at": now_iso()}})
    owner = await db.users.find_one({"_id": ObjectId(a["tenant_id"])}, {"email": 1})
    if owner:
        await emailer.send(owner["email"], f"{a['lead_name']} ha anulado su cita", "Una cita se ha anulado",
                           [("Cliente", a["lead_name"]), ("Teléfono", a.get("lead_phone") or "—"), ("Cita", _label(a["start"]))],
                           os.environ["APP_PUBLIC_URL"].rstrip("/") + "/app/agenda", "El hueco ya está libre en tu agenda.")
    return {"ok": True}
