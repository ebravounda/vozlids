import asyncio
import json
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import DuplicateKeyError
from db import db
from models import Appointment, DncEntry, now_iso
import vapi

log = logging.getLogger("vozlead")
TZ = ZoneInfo("Europe/Madrid")
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
DEFAULT_DAYS = [{"enabled": i < 5, "start": "09:00", "end": "14:00"} for i in range(7)]
NO_ANSWER_HINTS = ("did-not-answer", "busy", "voicemail", "no-answer")


def madrid_now() -> datetime:
    return datetime.now(TZ)


def today_text() -> str:
    n = madrid_now()
    return f"Hoy es {DIAS[n.weekday()]}, {n.day} de {MESES[n.month - 1]} de {n.year}, y son las {n:%H:%M} (hora de Madrid)."


async def get_availability(tenant_id: str) -> dict:
    av = await db.availability.find_one({"tenant_id": tenant_id})
    if not av:
        av = {"tenant_id": tenant_id, "slot_minutes": 30, "days": DEFAULT_DAYS}
        await db.availability.update_one({"tenant_id": tenant_id}, {"$setOnInsert": av}, upsert=True)
    return av


async def free_slots(tenant_id: str, d: date) -> list:
    av = await get_availability(tenant_id)
    day = av["days"][d.weekday()]
    if not day.get("enabled"):
        return []
    step = timedelta(minutes=av["slot_minutes"])
    cur = datetime.combine(d, datetime.strptime(day["start"], "%H:%M").time(), TZ)
    end = datetime.combine(d, datetime.strptime(day["end"], "%H:%M").time(), TZ)
    min_start = madrid_now() + timedelta(minutes=60)
    booked = {a["start"] async for a in db.appointments.find(
        {"tenant_id": tenant_id, "start": {"$regex": f"^{d.isoformat()}"}}, {"start": 1})}
    slots = []
    while cur + step <= end:
        key = cur.strftime("%Y-%m-%dT%H:%M")
        if cur >= min_start and key not in booked:
            slots.append(cur.strftime("%H:%M"))
        cur += step
    return slots


def _day_label(d: date) -> str:
    return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]}"


async def tool_check_availability(lead: dict, args: dict) -> dict:
    tid = lead["tenant_id"]
    if args.get("date"):
        try:
            d = date.fromisoformat(args["date"])
        except ValueError:
            return {"error": "Fecha no válida, usa YYYY-MM-DD"}
        slots = await free_slots(tid, d)
        return {"fecha": d.isoformat(), "dia": _day_label(d), "huecos": slots[:10],
                "nota": "" if slots else "No hay huecos ese día; ofrece otro día."}
    days, d = [], madrid_now().date()
    for _ in range(21):
        slots = await free_slots(tid, d)
        if slots:
            days.append({"fecha": d.isoformat(), "dia": _day_label(d), "huecos": slots[:5]})
        if len(days) == 3:
            break
        d += timedelta(days=1)
    return {"proximos_dias": days} if days else {"nota": "No hay huecos disponibles en las próximas semanas."}


async def tool_book(lead: dict, args: dict) -> dict:
    try:
        d = date.fromisoformat(args.get("date", ""))
        t = datetime.strptime(args.get("time", ""), "%H:%M").strftime("%H:%M")
    except ValueError:
        return {"ok": False, "error": "Fecha u hora no válidas"}
    if t not in await free_slots(lead["tenant_id"], d):
        return {"ok": False, "error": "Ese hueco no está disponible. Vuelve a consultar check_availability."}
    appt = Appointment(tenant_id=lead["tenant_id"], lead_id=str(lead["_id"]), lead_name=lead["name"],
                       lead_phone=lead["phone"], agent_id=lead["agent_id"], start=f"{d.isoformat()}T{t}",
                       notes=str(args.get("notes", ""))[:500])
    try:
        res = await db.appointments.insert_one(appt.to_mongo())
    except DuplicateKeyError:
        return {"ok": False, "error": "Ese hueco se acaba de ocupar. Ofrece otro."}
    await db.leads.update_one({"_id": lead["_id"]}, {"$set": {
        "appointment_id": str(res.inserted_id), "status": "cita_agendada", "updated_at": now_iso()}})
    return {"ok": True, "cita": f"{_day_label(d)} a las {t}"}


async def add_dnc(tenant_id: str, phone: str, reason: str):
    entry = DncEntry(tenant_id=tenant_id, phone=phone, reason=reason)
    await db.dnc.update_one({"tenant_id": tenant_id, "phone": phone}, {"$setOnInsert": entry.to_mongo()}, upsert=True)


async def tool_dnc(lead: dict, args: dict) -> dict:
    await add_dnc(lead["tenant_id"], lead["phone"], "Lo pidió durante la llamada")
    await db.leads.update_one({"_id": lead["_id"]}, {"$set": {"status": "no_llamar", "updated_at": now_iso()}})
    return {"ok": True}


TOOLS = {"check_availability": tool_check_availability, "book_appointment": tool_book, "mark_do_not_call": tool_dnc}


async def dial(agent: dict, lead: dict):
    lid = lead["_id"]
    if not vapi.configured():
        await db.leads.update_one({"_id": lid}, {"$set": {
            "status": "fallida", "updated_at": now_iso(),
            "error": "Telefonía sin configurar: falta la clave de Vapi o el número de Zadarma (ver Telefonía)."}})
        return
    try:
        call_id = await vapi.create_call(agent, lead, today_text())
        await db.leads.update_one({"_id": lid}, {"$set": {"vapi_call_id": call_id, "call_phase": "queued",
                                                          "updated_at": now_iso()}})
    except vapi.VapiError as e:
        log.warning("Vapi call failed: %s", e)
        await db.leads.update_one({"_id": lid}, {"$set": {"status": "fallida", "error": str(e),
                                                          "updated_at": now_iso()}})


async def find_lead_for_call(call: dict):
    lid = (call.get("metadata") or {}).get("lead_id")
    if lid:
        try:
            lead = await db.leads.find_one({"_id": ObjectId(lid)})
            if lead:
                return lead
        except InvalidId:
            pass
    if call.get("id"):
        return await db.leads.find_one({"vapi_call_id": call["id"]})
    return None


async def handle_tool_calls(msg: dict, lead) -> dict:
    results = []
    for tc in msg.get("toolCallList") or msg.get("toolCalls") or []:
        fn = tc.get("function") or {}
        name = fn.get("name") or tc.get("name")
        args = fn.get("arguments") or tc.get("arguments") or tc.get("parameters") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args or "{}")
            except ValueError:
                args = {}
        if not lead:
            result = {"error": "Llamada no reconocida"}
        elif name in TOOLS:
            result = await TOOLS[name](lead, args)
        else:
            result = {"error": f"Herramienta desconocida: {name}"}
        results.append({"toolCallId": tc.get("id"), "name": name, "result": json.dumps(result, ensure_ascii=False)})
    return {"results": results}


def _messages(raw: list) -> list:
    out = []
    for m in raw or []:
        role = {"bot": "agente", "assistant": "agente", "user": "lead"}.get(m.get("role"))
        text = m.get("message") or m.get("content")
        if role and isinstance(text, str) and text.strip():
            out.append({"role": role, "text": text.strip(), "t": m.get("secondsFromStart")})
    return out


def _recording(msg: dict, artifact: dict) -> str:
    rec = artifact.get("recording") or {}
    mono = rec.get("mono") or {}
    return artifact.get("recordingUrl") or msg.get("recordingUrl") or mono.get("combinedUrl") or rec.get("url") or ""


async def finalize_call(msg: dict, lead: dict):
    call = msg.get("call") or {}
    artifact = msg.get("artifact") or {}
    analysis = msg.get("analysis") or call.get("analysis") or {}
    sd = analysis.get("structuredData") or {}
    ended = msg.get("endedReason") or call.get("endedReason") or ""
    messages = _messages(artifact.get("messages") or msg.get("messages"))
    fresh = await db.leads.find_one({"_id": lead["_id"]}) or lead
    if fresh.get("status") == "no_llamar":
        status = "no_llamar"
    elif fresh.get("appointment_id"):
        status = "cita_agendada"
    elif any(h in ended for h in NO_ANSWER_HINTS) or not any(m["role"] == "lead" for m in messages):
        status = "sin_respuesta" if "error" not in ended and "failed" not in ended else "fallida"
    else:
        status = sd.get("outcome") if sd.get("outcome") in vapi.AI_OUTCOMES else None
        if status in (None, "cita_agendada"):
            status = "calificado" if (sd.get("interest_score") or 0) >= 50 else "no_interesado"
    if status == "no_llamar":
        await add_dnc(lead["tenant_id"], lead["phone"], "Lo pidió durante la llamada")
    score = sd.get("interest_score")
    cost = msg.get("cost", call.get("cost"))
    await db.leads.update_one({"_id": lead["_id"]}, {"$set": {
        "status": status, "call_phase": "ended", "ended_reason": ended,
        "cost": cost, "cost_breakdown": msg.get("costBreakdown") or call.get("costBreakdown"),
        "transcript": artifact.get("transcript") or msg.get("transcript") or "",
        "messages": messages, "recording_url": _recording(msg, artifact),
        "summary": analysis.get("summary") or "", "answers": str(sd.get("answers") or ""),
        "interest_score": int(max(0, min(100, score))) if isinstance(score, (int, float)) else None,
        "duration_seconds": msg.get("durationSeconds"),
        "error": ended if status == "fallida" else "", "updated_at": now_iso()}})
    if cost is None and lead.get("vapi_call_id"):
        asyncio.create_task(sync_cost_later(lead["_id"]))


async def sync_call_cost(lead: dict) -> bool:
    try:
        call = await vapi.get_call(lead["vapi_call_id"])
    except vapi.VapiError:
        return False
    if call.get("cost") is None:
        return False
    upd = {"cost": call["cost"], "cost_breakdown": call.get("costBreakdown")}
    if not lead.get("duration_seconds") and call.get("startedAt") and call.get("endedAt"):
        start = datetime.fromisoformat(call["startedAt"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(call["endedAt"].replace("Z", "+00:00"))
        upd["duration_seconds"] = (end - start).total_seconds()
    await db.leads.update_one({"_id": lead["_id"]}, {"$set": upd})
    return True


async def sync_cost_later(lead_id, delay: int = 45):
    await asyncio.sleep(delay)
    lead = await db.leads.find_one({"_id": lead_id})
    if lead and lead.get("cost") is None:
        await sync_call_cost(lead)
