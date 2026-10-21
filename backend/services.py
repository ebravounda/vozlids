import asyncio
from pymongo import ReturnDocument
import json
import re
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import DuplicateKeyError
from db import db
from models import Appointment, DncEntry, now_iso
import vapi
from countries import COUNTRIES

log = logging.getLogger("vozlead")
TZ = ZoneInfo("Europe/Madrid")
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
DEFAULT_DAYS = [{"enabled": i < 5, "start": "09:00", "end": "14:00"} for i in range(7)]
NO_ANSWER_HINTS = ("did-not-answer", "busy", "voicemail", "no-answer")


def madrid_now() -> datetime:
    return datetime.now(TZ)


def tz_of(country: str) -> ZoneInfo:
    return ZoneInfo(COUNTRIES[country or "ES"]["tz"])


def today_text(country: str = "ES") -> str:
    n = datetime.now(tz_of(country))
    return (f"Hoy es {DIAS[n.weekday()]}, {n.day} de {MESES[n.month - 1]} de {n.year}, y son las {n:%H:%M} "
            f"(hora de {COUNTRIES[country]['city']}). Todas las horas de la agenda son hora local de {COUNTRIES[country]['city']}.")


async def lead_country(lead: dict) -> str:
    agent = await db.agents.find_one({"_id": ObjectId(lead["agent_id"])}, {"country": 1}) if ObjectId.is_valid(lead["agent_id"]) else None
    return (agent or {}).get("country", "ES")


async def get_availability(tenant_id: str) -> dict:
    av = await db.availability.find_one({"tenant_id": tenant_id})
    if not av:
        av = {"tenant_id": tenant_id, "slot_minutes": 30, "days": DEFAULT_DAYS}
        await db.availability.update_one({"tenant_id": tenant_id}, {"$setOnInsert": av}, upsert=True)
    return av


async def free_slots(tenant_id: str, d: date, country: str = "ES") -> list:
    av = await get_availability(tenant_id)
    day = av["days"][d.weekday()]
    if not day.get("enabled"):
        return []
    step = timedelta(minutes=av["slot_minutes"])
    tz = tz_of(country)
    cur = datetime.combine(d, datetime.strptime(day["start"], "%H:%M").time(), tz)
    end = datetime.combine(d, datetime.strptime(day["end"], "%H:%M").time(), tz)
    min_start = datetime.now(tz) + timedelta(minutes=60)
    booked = {a["start"] async for a in db.appointments.find(
        {"tenant_id": tenant_id, "start": {"$regex": f"^{d.isoformat()}"}}, {"start": 1})}
    import gcal
    taken = await gcal.busy(tenant_id, d.isoformat(), (d + timedelta(days=1)).isoformat())
    slots = []
    while cur + step <= end:
        key = cur.strftime("%Y-%m-%dT%H:%M")
        stop = (cur + step).strftime("%Y-%m-%dT%H:%M")
        if cur >= min_start and key not in booked and not any(a < stop and b > key for a, b, _ in taken):
            slots.append(cur.strftime("%H:%M"))
        cur += step
    return slots


def _day_label(d: date) -> str:
    return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]}"


async def tool_check_availability(lead: dict, args: dict) -> dict:
    tid = lead["tenant_id"]
    country = await lead_country(lead)
    if args.get("date"):
        try:
            d = date.fromisoformat(args["date"])
        except ValueError:
            return {"error": "Fecha no válida, usa YYYY-MM-DD"}
        slots = await free_slots(tid, d, country)
        return {"fecha": d.isoformat(), "dia": _day_label(d), "huecos": slots[:10],
                "nota": "" if slots else "No hay huecos ese día; ofrece otro día."}
    days, d = [], datetime.now(tz_of(country)).date()
    for _ in range(21):
        slots = await free_slots(tid, d, country)
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
    if t not in await free_slots(lead["tenant_id"], d, await lead_country(lead)):
        return {"ok": False, "error": "Ese hueco no está disponible. Vuelve a consultar check_availability."}
    appt = Appointment(tenant_id=lead["tenant_id"], lead_id=str(lead["_id"]), lead_name=lead["name"],
                       lead_phone=lead["phone"], lead_email=lead.get("email") or "", agent_id=lead["agent_id"], start=f"{d.isoformat()}T{t}",
                       notes=str(args.get("notes", ""))[:500])
    try:
        res = await db.appointments.insert_one(appt.to_mongo())
    except DuplicateKeyError:
        return {"ok": False, "error": "Ese hueco se acaba de ocupar. Ofrece otro."}
    import gcal
    gcal.sync(res.inserted_id)
    await db.leads.update_one({"_id": lead["_id"]}, {"$set": {
        "appointment_id": str(res.inserted_id), "status": "cita_agendada", "updated_at": now_iso()}})
    import saas
    asyncio.create_task(saas.notify_appointment(lead, f"{_day_label(d)} a las {t} (hora de {COUNTRIES[await lead_country(lead)]['city']})"))
    return {"ok": True, "cita": f"{_day_label(d)} a las {t}"}


async def add_dnc(tenant_id: str, phone: str, reason: str):
    entry = DncEntry(tenant_id=tenant_id, phone=phone, reason=reason)
    await db.dnc.update_one({"tenant_id": tenant_id, "phone": phone}, {"$setOnInsert": entry.to_mongo()}, upsert=True)


async def tool_dnc(lead: dict, args: dict) -> dict:
    await add_dnc(lead["tenant_id"], lead["phone"], "Lo pidió durante la llamada")
    await db.leads.update_one({"_id": lead["_id"]}, {"$set": {"status": "no_llamar", "updated_at": now_iso()}})
    return {"ok": True}


async def tool_callback(lead: dict, args: dict) -> dict:
    import callbacks
    return await callbacks.schedule(lead, args)


TOOLS = {"check_availability": tool_check_availability, "book_appointment": tool_book, "mark_do_not_call": tool_dnc,
         "schedule_callback": tool_callback}


async def pick_executive(agent: dict) -> dict:
    """Rotate the agent's executives in turn (Marta, Pablo, Lucía, Marta…): each call gets the next voice and name."""
    team = [e for e in agent.get("executives") or [] if e.get("voice") and e.get("name")]
    if not team:
        return agent
    doc = await db.agents.find_one_and_update({"_id": agent["_id"]}, {"$inc": {"exec_turn": 1}},
                                              projection={"exec_turn": 1}, return_document=ReturnDocument.AFTER)
    e = team[((doc or {}).get("exec_turn") or 1) % len(team) - 1]
    return {**agent, "voice": e["voice"], "name": e["name"], "base_name": agent["name"], "executive": e["name"],
            "other_names": [agent["name"]] + [x["name"] for x in team if x["name"] != e["name"]]}


async def dial(agent: dict, lead: dict):
    lid = lead["_id"]
    country = agent.get("country", "ES")
    import saas
    import security_admin as SEC
    err = "Número bloqueado en la plataforma" if await SEC.blocked_phone(lead.get("phone", "")) else await saas.quota_error(agent["tenant_id"])
    if not err and lead.get("callback_of") and await db.dnc.find_one({"tenant_id": lead["tenant_id"], "phone": lead["phone"]}):
        err = "Rellamada anulada: el contacto está en la lista de no llamar"
    if err:
        await db.leads.update_one({"_id": lid}, {"$set": {"status": "fallida", "error": err, "updated_at": now_iso()}})
        return
    import phone_numbers as N
    own = await N.phone_id_for(agent["tenant_id"], country, str(agent["_id"]))
    if not own and not vapi.configured(country):
        await db.leads.update_one({"_id": lid}, {"$set": {
            "status": "fallida", "updated_at": now_iso(),
            "error": f"Telefonía sin configurar para {COUNTRIES[country]['name']}: falta conectar el número "
                     f"{COUNTRIES[country]['prefix']} en Telefonía."}})
        return
    import plan_limits as PL
    agent = await PL.effective_agent(await pick_executive(agent))
    try:
        call_id = await vapi.create_call(agent, lead, today_text(country), own)
        await db.leads.update_one({"_id": lid}, {"$set": {"vapi_call_id": call_id, "call_phase": "queued",
                                                          "voice_provider": vapi.voice_provider(agent["voice"]),
                                                          "executive": agent.get("executive", ""),
                                                          "updated_at": now_iso()}})
    except vapi.VapiError as e:
        log.warning("Vapi call failed: %s", e)
        import monitor
        await monitor.call_failed(str(e))
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


async def language_handoff(msg: dict, lead) -> dict:
    lang = (msg.get("parameters") or {}).get("language", "")
    agent = await db.agents.find_one({"_id": ObjectId(lead["agent_id"])}) if lead and ObjectId.is_valid(lead.get("agent_id", "")) else None
    if not agent:
        return {"error": "No se pudo cambiar de idioma. Sigue atendiendo en español."}
    import plan_limits as PL
    agent = await PL.effective_agent(agent)
    a = vapi.build_language_assistant(agent, lead, today_text(agent.get("country", "ES")), lang)
    if not a:
        return {"error": "Ese idioma no está disponible. Sigue atendiendo en español."}
    voice = next(e["voice"] for e in agent["languages"] if e["lang"] == lang)
    await db.leads.update_one({"_id": lead["_id"]}, {"$set": {"language": lang, "voice_provider": vapi.voice_provider(voice)}})
    return {"destination": {"type": "assistant", "assistant": a, "contextEngineeringPlan": {"type": "all"}}}


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
        text = re.sub(r"<break[^>]*>", "", text).strip() if isinstance(text, str) else text
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
    is_in = fresh.get("direction") == "entrante"
    if fresh.get("status") == "no_llamar":
        status = "no_llamar"
    elif "voicemail" in ended:
        status = "buzon"
    elif fresh.get("appointment_id"):
        status = "cita_agendada"
    elif is_in:
        status = "atendida"
    elif any(h in ended for h in NO_ANSWER_HINTS) or not any(m["role"] == "lead" for m in messages):
        status = "sin_respuesta" if "error" not in ended and "failed" not in ended else "fallida"
    else:
        status = sd.get("outcome") if sd.get("outcome") in vapi.AI_OUTCOMES else None
        if status in (None, "cita_agendada"):
            status = "calificado" if (sd.get("interest_score") or 0) >= 50 else "no_interesado"
    if fresh.get("callback_id") and status not in ("no_llamar", "cita_agendada", "venta", "buzon"):
        status = "rellamada"
    if status == "no_llamar":
        await add_dnc(lead["tenant_id"], lead["phone"], "Lo pidió durante la llamada")
        import callbacks
        await callbacks.cancel_for(fresh)
    score = sd.get("interest_score")
    cost = msg.get("cost", call.get("cost"))
    named = {"name": str(sd["caller_name"])[:80]} if is_in and str(sd.get("caller_name") or "").strip() else {}
    await db.leads.update_one({"_id": lead["_id"]}, {"$set": {**named,
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
    upd = {"cost": call["cost"], "cost_breakdown": call.get("costBreakdown"), "started_at": call.get("startedAt")}
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
