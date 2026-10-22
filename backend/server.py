from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os  # noqa: E402
import re  # noqa: E402
import logging  # noqa: E402
import secrets  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402
from typing import List, Literal, Optional  # noqa: E402
from bson import ObjectId  # noqa: E402
from bson.errors import InvalidId  # noqa: E402
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
from pymongo.errors import DuplicateKeyError  # noqa: E402
from starlette.middleware.cors import CORSMiddleware  # noqa: E402

import ambience  # noqa: E402
import auth as A  # noqa: E402
import services as S  # noqa: E402
import vapi  # noqa: E402
import extra_routes as X  # noqa: E402
import saas  # noqa: E402
import billing  # noqa: E402
import voice_preview  # noqa: E402
import landing  # noqa: E402
import phone_numbers  # noqa: E402
import monitor  # noqa: E402
import sector_demo  # noqa: E402
import widget  # noqa: E402
import onboarding  # noqa: E402
import api_core  # noqa: E402
import apiv1  # noqa: E402
import privacy  # noqa: E402
import gcal  # noqa: E402
import plan_limits as PL  # noqa: E402
import languages as L  # noqa: E402
import kyc  # noqa: E402
import connect_numbers  # noqa: E402
import lines  # noqa: E402
import linehealth  # noqa: E402
import payments  # noqa: E402
import webscan  # noqa: E402
import daily_jobs  # noqa: E402
import security_admin as SEC  # noqa: E402
import reminders  # noqa: E402
import callbacks  # noqa: E402
import extra_numbers  # noqa: E402
import asyncio  # noqa: E402
import emailer  # noqa: E402
import storage  # noqa: E402
import threading  # noqa: E402
from db import client, db  # noqa: E402
from models import Agent, Appointment, DncEntry, Lead, now_iso  # noqa: E402
from seed import seed  # noqa: E402
from countries import COUNTRIES, norm_any_phone, norm_phone  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
api = APIRouter(prefix="/api")
CurrentUser = Depends(A.get_current_user)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
LIST_PROJECTION = {"messages": 0, "transcript": 0}


def oid(v: str) -> ObjectId:
    try:
        return ObjectId(v)
    except (InvalidId, TypeError):
        raise HTTPException(404, "No encontrado")


def user_out(u: dict) -> dict:
    return {"id": str(u.get("id") or u.get("_id")), "email": u["email"], "name": u.get("name", ""),
            "business_name": u.get("business_name", ""), "role": u.get("role", "business"),
            "country": u.get("country", "ES"), "billing_status": u.get("billing_status"), "tour_pending": u.get("tour_done") is False,
            "admin_only": bool(u.get("admin_only")), "client_id": u.get("client_id", "")}


def ago(minutes: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


# ---------- Auth ----------
class AddressIn(BaseModel):
    line: str = Field(min_length=3, max_length=200)
    city: str = Field(min_length=2, max_length=80)
    postal_code: str = Field("", max_length=12)
    region: str = Field("", max_length=80)


class RegisterIn(BaseModel):
    name: str = Field("", max_length=80)
    first_name: str = Field("", max_length=60)
    last_name: str = Field("", max_length=80)
    business_name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=8, max_length=128)
    country: Literal["ES", "CL"] = "ES"
    website: str = Field("", max_length=200)
    doc_type: str = Field("", max_length=12)
    doc_number: str = Field("", max_length=20)
    billing_address: AddressIn | None = None


class LoginIn(BaseModel):
    email: str
    password: str


@api.post("/auth/register")
async def register(body: RegisterIn, response: Response, request: Request):
    email = body.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(422, "Email no válido")
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Ya existe una cuenta con ese email")
    if await SEC.blocked_ip(landing.client_ip(request)):
        raise HTTPException(403, SEC.BLOCKED_MSG)
    if msg := await SEC.blocked_email(email):
        raise HTTPException(403 if msg == SEC.BLOCKED_MSG else 422, msg)
    name = body.name.strip() or f"{body.first_name.strip()} {body.last_name.strip()}".strip()
    if not name:
        raise HTTPException(422, "Indica tu nombre")
    doc = {"email": email, "password_hash": A.hash_password(body.password), "name": name,
           "business_name": body.business_name.strip(), "role": "business", "country": body.country,
           "created_at": now_iso(), "tour_done": False}
    if body.doc_number:
        try:
            doc["doc_number"] = onboarding.valid_doc(body.country, body.doc_type, body.doc_number)
        except ValueError as e:
            raise HTTPException(422, str(e))
        web = body.website.strip()
        doc.update({"first_name": body.first_name.strip(), "last_name": body.last_name.strip(), "doc_type": body.doc_type,
                    "website": web if not web or web.startswith("http") else f"https://{web}",
                    "billing_address": body.billing_address.model_dump() if body.billing_address else None})
    res = await db.users.insert_one(doc)
    uid = str(res.inserted_id)
    await S.get_availability(uid)
    asyncio.create_task(welcome_email(doc))
    token = A.set_auth_cookies(response, uid, email)
    return {**user_out({**doc, "_id": uid}), "access_token": token}


async def welcome_email(u: dict) -> None:
    cl = u.get("country") == "CL"
    ids = "tu cédula de identidad (ambas caras) o pasaporte y tu RUT" if cl else "tu DNI o NIE (ambas caras) o pasaporte"
    await emailer.send(u["email"], "Bienvenido a VozLeads: tus primeros pasos", f"¡Bienvenido, {u.get('name') or u['business_name']}!", [
        ("1 · Sube tus documentos", f"Por ley, tu número va a tu nombre. En «Mi número» sube {ids}. Si eres empresa, también su certificado."),
        ("2 · Tu número", "Estamos a la espera de asignación de numeración: puede demorar de 2 a 24 horas. Tu suscripción comienza cuando tu numeración está activa. Te avisaremos por email."),
        ("3 · Crea tu agente IA", "Elige su voz y acento, cómo saluda y qué debe hacer: recepcionista, agendar citas o ventas. Escúchalo antes de activarlo."),
        ("4 · Mira tus llamadas", "En «Leads y llamadas» verás cada llamada con su resumen, grabación y resultado. Las citas llegan a tu agenda."),
        ("5 · ¿Dudas?", "Escríbenos desde «Asistencia técnica» o llámanos: Chile +56 2 3384 4477 · España +34 919 93 26 52."),
    ], os.environ["APP_PUBLIC_URL"].rstrip("/") + "/app/numero",
        f"Tu cuenta de {u['business_name']} ya está creada. Estos son los pasos para dejar tu asistente telefónico funcionando.",
        "Subir mis documentos")


@api.post("/auth/login")
async def login(body: LoginIn, request: Request, response: Response):
    email = body.email.strip().lower()
    ident = f"{request.client.host if request.client else '?'}:{email}"
    att = await db.login_attempts.find_one({"identifier": ident})
    if att and att.get("locked_until", "") > now_iso():
        raise HTTPException(429, "Demasiados intentos. Vuelve a probar en 15 minutos.")
    user = await db.users.find_one({"email": email})
    if not user or not A.verify_password(body.password, user["password_hash"]):
        count = (att or {}).get("count", 0) + 1
        upd = {"count": 0, "locked_until": ago(-15)} if count >= 5 else {"count": count}
        await db.login_attempts.update_one({"identifier": ident}, {"$set": upd}, upsert=True)
        raise HTTPException(401, "Email o contraseña incorrectos")
    await db.login_attempts.delete_one({"identifier": ident})
    token = A.set_auth_cookies(response, str(user["_id"]), email)
    return {**user_out(user), "access_token": token}


@api.post("/auth/refresh")
async def refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(401, "No autenticado")
    user = await A.get_user_by_id(A.decode(token, "refresh")["sub"])
    access = A.create_access_token(user["id"], user["email"])
    A.set_access_cookie(response, access)
    return {"ok": True, "access_token": access}


@api.post("/auth/logout")
async def logout(response: Response):
    A.clear_auth_cookies(response)
    return {"ok": True}


@api.get("/auth/me")
async def me(request: Request, user=CurrentUser):
    return {**user_out(user), "impersonating": bool(request.cookies.get("imp"))}


class CountryIn(BaseModel):
    country: Literal["ES", "CL"]


@api.put("/account/country")
async def set_country(body: CountryIn, user=CurrentUser):
    await db.users.update_one({"_id": ObjectId(user["id"])}, {"$set": {"country": body.country}})
    return user_out({**user, "country": body.country})


@api.post("/account/tour-done")
async def tour_done(user=CurrentUser):
    await db.users.update_one({"_id": ObjectId(user["id"])}, {"$set": {"tour_done": True}})
    return {"ok": True}


# ---------- Agents ----------
class Executive(BaseModel):
    voice: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=40)


class LangExec(BaseModel):
    lang: Literal["en", "pt", "fr", "ca", "it", "de"]
    voice: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=40)


class AgentIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    business_name: str = Field(min_length=1, max_length=120)
    product: str = Field(min_length=1, max_length=8000)
    objective: Literal["agendar", "calificar", "vender", "recepcion"]
    questions: List[str] = Field(default=[], max_length=10)
    country: Literal["ES", "CL"] = "ES"
    voice: str = Field(min_length=1, max_length=40)
    ambience: str = Field(pattern=r"^(oficina|teclados|call_center|oficina_real|teclado_real|vapi_office|none|custom:[0-9a-f]{32})$")
    ambience_volume: int = Field(35, ge=0, le=100)
    greeting: str = Field(min_length=1, max_length=600)
    extra_instructions: str = Field("", max_length=2000)
    executives: List[Executive] = Field(default=[], max_length=5)
    languages: List[LangExec] = Field(default=[], max_length=6)
    memory: bool = True
    website: str = Field("", max_length=300)
    web_summary: str = Field("", max_length=4000)
    active: bool = True


async def get_agent(tenant_id: str, agent_id: str) -> dict:
    agent = await db.agents.find_one({"_id": oid(agent_id), "tenant_id": tenant_id})
    if not agent:
        raise HTTPException(404, "Agente no encontrado")
    return agent


@api.get("/agents")
async def list_agents(user=CurrentUser):
    docs = await db.agents.find({"tenant_id": user["id"]}).sort("created_at", -1).to_list(100)
    return [Agent.from_mongo(d).out() for d in docs]


async def check_ambience(user: dict, body: AgentIn):
    for v in [body.voice] + [e.voice for e in body.executives]:
        if not vapi.voice_ok(v, "es"):
            raise HTTPException(422, "Esa voz no habla español.")
    for e in body.languages:
        if not vapi.voice_ok(e.voice, e.lang):
            raise HTTPException(422, f"La voz de {e.name} no habla {L.LANGS[e.lang]['name']}.")
    if len({e.lang for e in body.languages}) < len(body.languages):
        raise HTTPException(422, "Cada idioma solo puede tener un ejecutivo.")
    if body.languages and not await PL.has(user["id"], "multilang"):
        body.languages = []
    if len({e.voice for e in body.executives}) < len(body.executives):
        raise HTTPException(422, "Cada ejecutivo debe tener una voz distinta.")
    if body.ambience.startswith("custom:") and not await X.custom_ambience_allowed(user["id"], body.ambience[7:]):
        raise HTTPException(422, "Esa grabación de ambiente no existe.")


@api.post("/agents")
async def create_agent(body: AgentIn, user=CurrentUser):
    await check_ambience(user, body)
    await PL.check_agent(user["id"], body.voice, body.ambience, True)
    for e in body.executives:
        await PL.check_agent(user["id"], e.voice, "none", False)
    agent = Agent(tenant_id=user["id"], **body.model_dump())
    res = await db.agents.insert_one(agent.to_mongo())
    return Agent.from_mongo(await db.agents.find_one({"_id": res.inserted_id})).out()


@api.get("/agents/{agent_id}")
async def read_agent(agent_id: str, user=CurrentUser):
    return Agent.from_mongo(await get_agent(user["id"], agent_id)).out()


@api.put("/agents/{agent_id}")
async def update_agent(agent_id: str, body: AgentIn, user=CurrentUser):
    prev = await get_agent(user["id"], agent_id)
    await check_ambience(user, body)
    await PL.check_agent(user["id"], body.voice if body.voice != prev.get("voice") else "", body.ambience if body.ambience != prev.get("ambience") else "none", False)
    old_voices = {e.get("voice") for e in prev.get("executives") or []}
    for e in body.executives:
        if e.voice not in old_voices:
            await PL.check_agent(user["id"], e.voice, "none", False)
    await db.agents.update_one({"_id": oid(agent_id)}, {"$set": {**body.model_dump(), "updated_at": now_iso()}})
    return Agent.from_mongo(await get_agent(user["id"], agent_id)).out()


@api.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str, user=CurrentUser):
    await get_agent(user["id"], agent_id)
    await db.agents.delete_one({"_id": oid(agent_id)})
    await db.tenant_numbers.update_many({"tenant_id": user["id"], "extra": True, "agent_id": agent_id}, {"$set": {"agent_id": None}})
    return {"ok": True}


async def is_dnc(tenant_id: str, phone: str) -> bool:
    return bool(await db.dnc.find_one({"tenant_id": tenant_id, "phone": phone}))


async def create_and_dial(agent: dict, name: str, phone: str, email: str, is_test: bool, ip: str = "",
                          source: str = "form") -> dict:
    lead = Lead(tenant_id=agent["tenant_id"], agent_id=str(agent["_id"]), agent_name=agent["name"],
                name=name, phone=phone, email=email, is_test=is_test, source=source)
    doc = {**lead.to_mongo(), "source_ip": ip}
    res = await db.leads.insert_one(doc)
    doc["_id"] = res.inserted_id
    await S.dial(agent, doc)
    return Lead.from_mongo(await db.leads.find_one({"_id": res.inserted_id})).out()


class TestCallIn(BaseModel):
    phone: str


@api.post("/agents/{agent_id}/test-call")
async def test_call(agent_id: str, body: TestCallIn, user=CurrentUser):
    agent = await get_agent(user["id"], agent_id)
    phone = norm_phone(body.phone, agent.get("country", "ES"))
    if await is_dnc(user["id"], phone):
        raise HTTPException(400, "Ese número está en tu lista de no llamar.")
    return await create_and_dial(agent, user.get("name") or "Prueba", phone, user["email"], True)


# ---------- Public form ----------
class PublicLeadIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    phone: str = Field(min_length=9, max_length=20)
    email: str = Field("", max_length=200)
    consent: bool
    source: Literal["form", "widget"] = "form"


@api.get("/public/agents/{agent_id}")
async def public_agent(agent_id: str):
    agent = await db.agents.find_one({"_id": oid(agent_id)})
    if not agent:
        raise HTTPException(404, "Formulario no encontrado")
    country = agent.get("country", "ES")
    return {"id": agent_id, "name": agent["name"], "business_name": agent["business_name"], "active": agent["active"],
            "country": country, "phone_example": COUNTRIES[country]["example"]}


@api.post("/public/agents/{agent_id}/leads")
async def public_lead(agent_id: str, body: PublicLeadIn, request: Request):
    agent = await db.agents.find_one({"_id": oid(agent_id)})
    if not agent or not agent.get("active"):
        raise HTTPException(404, "Este formulario no está activo")
    if not body.consent:
        raise HTTPException(400, "Debes aceptar recibir la llamada para continuar.")
    email = body.email.strip().lower()
    if email and not EMAIL_RE.match(email):
        raise HTTPException(422, "Email no válido")
    phone = norm_phone(body.phone, agent.get("country", "ES"))
    ip = landing.client_ip(request)
    await SEC.guard_public(phone, email, ip, request.headers.get("cf-ipcountry", ""))
    if ip and await db.leads.count_documents({"source_ip": ip, "created_at": {"$gt": ago(60)}}) >= 10:
        raise HTTPException(429, "Demasiadas solicitudes. Inténtalo más tarde.")
    tid = agent["tenant_id"]
    if body.source == "widget" and not await PL.has(tid, "widget"):
        raise HTTPException(404, "Este formulario no está activo")
    recent = await db.leads.find_one({"tenant_id": tid, "phone": phone, "created_at": {"$gt": ago(10)}})
    if recent or await is_dnc(tid, phone):
        return {"ok": True}
    await create_and_dial(agent, body.name.strip(), phone, email, False, ip, body.source)
    return {"ok": True}


# ---------- Leads ----------
@api.get("/leads")
async def list_leads(status: Optional[str] = None, q: Optional[str] = None, agent_id: Optional[str] = None,
                     language: Optional[str] = None, user=CurrentUser):
    flt = {"tenant_id": user["id"]}
    if language:
        flt["language"] = {"$nin": list(L.LANGS)} if language == "es" else language
    if status:
        flt["status"] = status
    if agent_id:
        flt["agent_id"] = agent_id
    if q:
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        flt["$or"] = [{"name": rx}, {"phone": rx}, {"email": rx}]
    docs = await db.leads.find(flt, LIST_PROJECTION).sort("created_at", -1).to_list(300)
    return [Lead.from_mongo(d).out() for d in docs]


@api.get("/leads/{lead_id}")
async def read_lead(lead_id: str, user=CurrentUser):
    doc = await db.leads.find_one({"_id": oid(lead_id), "tenant_id": user["id"]})
    if not doc:
        raise HTTPException(404, "Lead no encontrado")
    out = Lead.from_mongo(doc).out()
    out["transcript_purged_at"] = doc.get("transcript_purged_at")
    if doc.get("appointment_id"):
        appt = await db.appointments.find_one({"_id": oid(doc["appointment_id"])})
        out["appointment"] = Appointment.from_mongo(appt).out() if appt else None
    return out


@api.get("/stats")
async def stats(user=CurrentUser):
    tid = user["id"]
    rows = await db.leads.aggregate([{"$match": {"tenant_id": tid}},
                                     {"$group": {"_id": "$status", "n": {"$sum": 1}}}]).to_list(20)
    by_status = {r["_id"]: r["n"] for r in rows}
    today = S.madrid_now().strftime("%Y-%m-%dT%H:%M")
    return {"total": sum(by_status.values()), "by_status": by_status,
            "upcoming_appointments": await db.appointments.count_documents({"tenant_id": tid, "start": {"$gte": today}})}


# ---------- Agenda ----------
class DayIn(BaseModel):
    enabled: bool
    start: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class AvailabilityIn(BaseModel):
    slot_minutes: Literal[15, 20, 30, 45, 60, 90]
    days: List[DayIn] = Field(min_length=7, max_length=7)


@api.get("/availability")
async def read_availability(user=CurrentUser):
    av = await S.get_availability(user["id"])
    return {"slot_minutes": av["slot_minutes"], "days": av["days"]}


@api.put("/availability")
async def save_availability(body: AvailabilityIn, user=CurrentUser):
    for d in body.days:
        if d.enabled and d.start >= d.end:
            raise HTTPException(422, "La hora de inicio debe ser anterior a la de fin.")
    data = body.model_dump()
    await db.availability.update_one({"tenant_id": user["id"]}, {"$set": data}, upsert=True)
    return data


@api.get("/appointments")
async def list_appointments(user=CurrentUser, start: Optional[str] = None, end: Optional[str] = None):
    lo = start or S.madrid_now().strftime("%Y-%m-%d")
    q = {"tenant_id": user["id"], "start": {"$gte": lo, **({"$lt": end} if end else {})}}
    docs = await db.appointments.find(q).sort("start", 1).to_list(1000)
    return [Appointment.from_mongo(d).out() for d in docs]


SLOT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T([01]\d|2[0-3]):[0-5]\d$")


class ApptIn(BaseModel):
    start: str = Field(max_length=16)
    lead_name: str = Field(min_length=1, max_length=80)
    lead_phone: str = Field("", max_length=25)
    lead_email: str = Field("", max_length=200)
    notes: str = Field("", max_length=500)
    duration_minutes: Optional[int] = Field(None, ge=5, le=480)


class ApptPatch(BaseModel):
    start: Optional[str] = Field(None, max_length=16)
    notes: Optional[str] = Field(None, max_length=500)
    duration_minutes: Optional[int] = Field(None, ge=5, le=480)


def _slot(v: str) -> str:
    if not SLOT_RE.match(v):
        raise HTTPException(422, "Fecha y hora no válidas (AAAA-MM-DDTHH:MM)")
    return v


@api.post("/appointments")
async def create_appointment(body: ApptIn, user=CurrentUser):
    country = (await db.users.find_one({"_id": oid(user["id"])}, {"country": 1}) or {}).get("country", "ES")
    try:
        phone = norm_phone(body.lead_phone, country) if body.lead_phone.strip() else ""
    except (ValueError, HTTPException):
        raise HTTPException(422, "Teléfono no válido")
    appt = Appointment(tenant_id=user["id"], lead_name=body.lead_name.strip(), lead_phone=phone, lead_email=body.lead_email.strip().lower(), start=_slot(body.start),
                       notes=body.notes.strip(), duration_minutes=body.duration_minutes, source="manual")
    try:
        res = await db.appointments.insert_one(appt.to_mongo())
    except DuplicateKeyError:
        raise HTTPException(409, "Ya hay una cita a esa hora")
    gcal.sync(res.inserted_id)
    return Appointment.from_mongo(await db.appointments.find_one({"_id": res.inserted_id})).out()


@api.patch("/appointments/{appt_id}")
async def update_appointment(appt_id: str, body: ApptPatch, user=CurrentUser):
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    if not upd:
        raise HTTPException(422, "Nada que cambiar")
    if "start" in upd:
        _slot(upd["start"])
        upd.update(reminder_sent_at=None, reminder_email_at=None, reminder_call_at=None, owner_hour_at=None, confirmed_at=None, reminder_channels=[])
    try:
        doc = await db.appointments.find_one_and_update({"_id": oid(appt_id), "tenant_id": user["id"]}, {"$set": upd},
                                                        return_document=True)
    except DuplicateKeyError:
        raise HTTPException(409, "Ya hay una cita a esa hora")
    if not doc:
        raise HTTPException(404, "Cita no encontrada")
    gcal.sync(doc["_id"])
    return Appointment.from_mongo(doc).out()


@api.delete("/appointments/{appt_id}")
async def cancel_appointment(appt_id: str, user=CurrentUser):
    doc = await db.appointments.find_one_and_delete({"_id": oid(appt_id), "tenant_id": user["id"]})
    if not doc:
        raise HTTPException(404, "Cita no encontrada")
    gcal.unsync(user["id"], doc.get("google_event_id"))
    await db.leads.update_one({"tenant_id": user["id"], "appointment_id": appt_id},
                              {"$set": {"appointment_id": None, "status": "calificado", "updated_at": now_iso()}})
    return {"ok": True}


# ---------- Do not call ----------
class DncIn(BaseModel):
    phone: str
    reason: str = Field("", max_length=200)


@api.get("/dnc")
async def list_dnc(user=CurrentUser):
    docs = await db.dnc.find({"tenant_id": user["id"]}).sort("created_at", -1).to_list(1000)
    return [DncEntry.from_mongo(d).out() for d in docs]


@api.post("/dnc")
async def add_dnc(body: DncIn, user=CurrentUser):
    phone = norm_any_phone(body.phone)
    entry = DncEntry(tenant_id=user["id"], phone=phone, reason=body.reason.strip() or "Añadido manualmente")
    try:
        await db.dnc.insert_one(entry.to_mongo())
    except DuplicateKeyError:
        raise HTTPException(400, "Ese número ya está en la lista.")
    return DncEntry.from_mongo(await db.dnc.find_one({"tenant_id": user["id"], "phone": phone})).out()


@api.delete("/dnc/{entry_id}")
async def delete_dnc(entry_id: str, user=CurrentUser):
    res = await db.dnc.delete_one({"_id": oid(entry_id), "tenant_id": user["id"]})
    if not res.deleted_count:
        raise HTTPException(404, "No encontrado")
    return {"ok": True}


# ---------- Telephony / ambience / webhook ----------
@api.get("/telephony/status")
async def telephony_status(user=CurrentUser):
    countries = {c: {"name": COUNTRIES[c]["name"], "prefix": COUNTRIES[c]["prefix"], "configured": vapi.configured(c),
                     "number": vapi.number_info(c).get("number")} for c in COUNTRIES}
    own = user.get("country", "ES")
    return {"configured": vapi.configured(own), "has_api_key": bool(os.environ.get("VAPI_API_KEY")),
            "has_phone_number": bool(vapi.phone_number_id(own)), "number": vapi.number_info(own).get("number"),
            "countries": countries, "country": own,
            "is_admin": user.get("role") == "admin", "webhook_url": vapi.webhook_url()}


class ZadarmaIn(BaseModel):
    sip_login: str = Field(min_length=2, max_length=80)
    sip_password: str = Field(min_length=1, max_length=200)
    number: str
    country: Literal["ES", "CL"] = "ES"


@api.post("/telephony/zadarma")
async def connect_zadarma(body: ZadarmaIn, user=CurrentUser):
    if user.get("role") != "admin":
        raise HTTPException(403, "Solo el administrador de la plataforma puede conectar la telefonía.")
    if not os.environ.get("VAPI_API_KEY"):
        raise HTTPException(400, "Falta la clave de Vapi.")
    number = norm_phone(body.number, body.country)
    try:
        res = await vapi.connect_zadarma(body.sip_login.strip(), body.sip_password, number, body.country)
    except vapi.VapiError as e:
        raise HTTPException(400, str(e))
    info = {"phone_number_id": res["phone_number_id"], "credential_id": res["credential_id"], "number": number,
            "updated_at": now_iso()}
    await db.platform_settings.update_one({"_id": "telephony"}, {"$set": {f"numbers.{body.country}": info}}, upsert=True)
    vapi.STATE["numbers"][body.country] = info
    return {"ok": True, "number": number}


@api.get("/ambience/{preset}/{volume}.wav")
async def ambience_wav(preset: str, volume: int):
    if preset not in ambience.PRESETS:
        raise HTTPException(404, "Ambiente no encontrado")
    vol = max(0, min(100, round(volume / 5) * 5))
    return Response(ambience.render(preset, vol), media_type="audio/wav",
                    headers={"Cache-Control": "public, max-age=86400"})


@api.post("/vapi/webhook")
async def vapi_webhook(request: Request):
    secret = os.environ["VAPI_WEBHOOK_SECRET"]
    header = request.headers.get("x-vapi-secret", "")
    if not secrets.compare_digest(header, secret):
        raise HTTPException(401, "Webhook no autorizado")
    msg = (await request.json()).get("message") or {}
    typ = msg.get("type")
    if typ == "assistant-request":
        return await phone_numbers.assistant_request(msg)
    lead = await S.find_lead_for_call(msg.get("call") or {})
    if typ == "tool-calls":
        return await S.handle_tool_calls(msg, lead)
    if typ == "handoff-destination-request":
        return await S.language_handoff(msg, lead)
    if not lead:
        return {"ok": True}
    if typ == "status-update" and lead.get("call_phase") != "ended":
        await db.leads.update_one({"_id": lead["_id"]}, {"$set": {"call_phase": msg.get("status", ""),
                                                                  "updated_at": now_iso()}})
        await api_core.on_lead_change(lead["_id"])
    elif typ == "end-of-call-report":
        await S.finalize_call(msg, lead)
        await api_core.on_lead_change(lead["_id"])
        await monitor.check_silent(msg, lead)
    return {"ok": True}


@api.get("/")
async def root():
    return {"app": "VozLead", "ok": True}


app.include_router(api)
app.include_router(X.router)
app.include_router(saas.router)
app.include_router(billing.router)
app.include_router(voice_preview.router)
app.include_router(landing.router)
app.include_router(phone_numbers.router)
app.include_router(monitor.router)
app.include_router(sector_demo.router)
app.include_router(widget.router)
app.include_router(onboarding.router)
app.include_router(apiv1.router)
app.include_router(privacy.router)
app.include_router(gcal.router)
app.include_router(SEC.router)
app.include_router(reminders.router)
app.include_router(callbacks.router)
app.include_router(extra_numbers.router)
app.include_router(kyc.router)
app.include_router(connect_numbers.router)
app.include_router(lines.router)
app.include_router(payments.router)
app.include_router(webscan.router)
app.include_router(daily_jobs.router)
app.mount("/api/v1", apiv1.app)
ORIGINS = [o.strip() for o in os.environ["CORS_ORIGINS"].split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_credentials="*" not in ORIGINS,
    allow_origins=ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    res = await call_next(request)
    res.headers.setdefault("X-Content-Type-Options", "nosniff")
    res.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    res.headers.setdefault("X-Frame-Options", "DENY")
    return res


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")
    await db.agents.create_index("tenant_id")
    await db.leads.create_index([("tenant_id", 1), ("created_at", -1)])
    await db.leads.create_index("vapi_call_id")
    await db.appointments.create_index([("tenant_id", 1), ("start", 1)], unique=True)
    await db.dnc.create_index([("tenant_id", 1), ("phone", 1)], unique=True)
    await db.availability.create_index("tenant_id", unique=True)
    await seed()
    threading.Thread(target=lambda: [ambience.render(p, 35) for p in ("oficina_real", "teclado_real")], daemon=True).start()
    try:
        storage.init_storage()
    except Exception as e:  # noqa: BLE001
        logging.getLogger("vozlead").error("Storage init failed: %s", e)
    tel = await db.platform_settings.find_one({"_id": "telephony"}) or {}
    if tel.get("phone_number_id") and "ES" not in (tel.get("numbers") or {}):
        legacy = {k: tel[k] for k in ("phone_number_id", "credential_id", "number") if k in tel}
        await db.platform_settings.update_one({"_id": "telephony"}, {"$set": {"numbers.ES": legacy}})
        tel.setdefault("numbers", {})["ES"] = legacy
    vapi.STATE["numbers"] = tel.get("numbers") or {}
    await X.load_custom_voices()
    await db.monitor_alerts.create_index("created_at")
    asyncio.create_task(monitor.loop())
    asyncio.create_task(linehealth.loop())
    asyncio.create_task(daily_jobs.loop())
    await api_core.ensure_indexes()
    await privacy.ensure_indexes()
    await gcal.ensure_indexes()
    await SEC.ensure_indexes()
    await db.webhook_deliveries.update_many({"status": "sending"}, {"$set": {"status": "pending"}})
    asyncio.create_task(api_core.worker())


@app.on_event("shutdown")
async def shutdown():
    client.close()
