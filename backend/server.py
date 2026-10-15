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
import asyncio  # noqa: E402
import storage  # noqa: E402
import threading  # noqa: E402
from db import client, db  # noqa: E402
from models import Agent, Appointment, DncEntry, Lead, now_iso  # noqa: E402
from seed import seed  # noqa: E402
from countries import COUNTRIES, norm_any_phone, norm_phone  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
app = FastAPI()
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
            "country": u.get("country", "ES")}


def ago(minutes: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


# ---------- Auth ----------
class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    business_name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=8, max_length=128)
    country: Literal["ES", "CL"] = "ES"


class LoginIn(BaseModel):
    email: str
    password: str


@api.post("/auth/register")
async def register(body: RegisterIn, response: Response):
    email = body.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(422, "Email no válido")
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Ya existe una cuenta con ese email")
    doc = {"email": email, "password_hash": A.hash_password(body.password), "name": body.name.strip(),
           "business_name": body.business_name.strip(), "role": "business", "country": body.country,
           "created_at": now_iso()}
    res = await db.users.insert_one(doc)
    uid = str(res.inserted_id)
    await S.get_availability(uid)
    token = A.set_auth_cookies(response, uid, email)
    return {**user_out({**doc, "_id": uid}), "access_token": token}


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


# ---------- Agents ----------
class AgentIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    business_name: str = Field(min_length=1, max_length=120)
    product: str = Field(min_length=1, max_length=3000)
    objective: Literal["agendar", "calificar", "vender", "recepcion"]
    questions: List[str] = Field(default=[], max_length=10)
    country: Literal["ES", "CL"] = "ES"
    voice: str = Field(min_length=1, max_length=40)
    ambience: str = Field(pattern=r"^(oficina|teclados|call_center|oficina_real|teclado_real|vapi_office|none|custom:[0-9a-f]{32})$")
    ambience_volume: int = Field(35, ge=0, le=100)
    greeting: str = Field(min_length=1, max_length=600)
    extra_instructions: str = Field("", max_length=2000)
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
    if not vapi.voice_allowed(body.voice, body.country):
        raise HTTPException(422, f"Esa voz no está disponible para {COUNTRIES[body.country]['name']}.")
    if body.ambience.startswith("custom:") and not await X.custom_ambience_allowed(user["id"], body.ambience[7:]):
        raise HTTPException(422, "Esa grabación de ambiente no existe.")


@api.post("/agents")
async def create_agent(body: AgentIn, user=CurrentUser):
    await check_ambience(user, body)
    agent = Agent(tenant_id=user["id"], **body.model_dump())
    res = await db.agents.insert_one(agent.to_mongo())
    return Agent.from_mongo(await db.agents.find_one({"_id": res.inserted_id})).out()


@api.get("/agents/{agent_id}")
async def read_agent(agent_id: str, user=CurrentUser):
    return Agent.from_mongo(await get_agent(user["id"], agent_id)).out()


@api.put("/agents/{agent_id}")
async def update_agent(agent_id: str, body: AgentIn, user=CurrentUser):
    await get_agent(user["id"], agent_id)
    await check_ambience(user, body)
    await db.agents.update_one({"_id": oid(agent_id)}, {"$set": {**body.model_dump(), "updated_at": now_iso()}})
    return Agent.from_mongo(await get_agent(user["id"], agent_id)).out()


@api.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str, user=CurrentUser):
    await get_agent(user["id"], agent_id)
    await db.agents.delete_one({"_id": oid(agent_id)})
    return {"ok": True}


async def is_dnc(tenant_id: str, phone: str) -> bool:
    return bool(await db.dnc.find_one({"tenant_id": tenant_id, "phone": phone}))


async def create_and_dial(agent: dict, name: str, phone: str, email: str, is_test: bool, ip: str = "") -> dict:
    lead = Lead(tenant_id=agent["tenant_id"], agent_id=str(agent["_id"]), agent_name=agent["name"],
                name=name, phone=phone, email=email, is_test=is_test)
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
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "").split(",")[0].strip()
    if ip and await db.leads.count_documents({"source_ip": ip, "created_at": {"$gt": ago(60)}}) >= 10:
        raise HTTPException(429, "Demasiadas solicitudes. Inténtalo más tarde.")
    tid = agent["tenant_id"]
    recent = await db.leads.find_one({"tenant_id": tid, "phone": phone, "created_at": {"$gt": ago(10)}})
    if recent or await is_dnc(tid, phone):
        return {"ok": True}
    await create_and_dial(agent, body.name.strip(), phone, email, False, ip)
    return {"ok": True}


# ---------- Leads ----------
@api.get("/leads")
async def list_leads(status: Optional[str] = None, q: Optional[str] = None, agent_id: Optional[str] = None,
                     user=CurrentUser):
    flt = {"tenant_id": user["id"]}
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
async def list_appointments(user=CurrentUser):
    today = S.madrid_now().strftime("%Y-%m-%d")
    docs = await db.appointments.find({"tenant_id": user["id"], "start": {"$gte": today}}).sort("start", 1).to_list(300)
    return [Appointment.from_mongo(d).out() for d in docs]


@api.delete("/appointments/{appt_id}")
async def cancel_appointment(appt_id: str, user=CurrentUser):
    res = await db.appointments.delete_one({"_id": oid(appt_id), "tenant_id": user["id"]})
    if not res.deleted_count:
        raise HTTPException(404, "Cita no encontrada")
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
async def vapi_webhook(request: Request, token: str = ""):
    secret = os.environ["VAPI_WEBHOOK_SECRET"]
    header = request.headers.get("x-vapi-secret", "")
    if not (secrets.compare_digest(header, secret) or secrets.compare_digest(token, secret)):
        raise HTTPException(401, "Webhook no autorizado")
    msg = (await request.json()).get("message") or {}
    typ = msg.get("type")
    if typ == "assistant-request":
        return await phone_numbers.assistant_request(msg)
    lead = await S.find_lead_for_call(msg.get("call") or {})
    if typ == "tool-calls":
        return await S.handle_tool_calls(msg, lead)
    if not lead:
        return {"ok": True}
    if typ == "status-update" and lead.get("call_phase") != "ended":
        await db.leads.update_one({"_id": lead["_id"]}, {"$set": {"call_phase": msg.get("status", ""),
                                                                  "updated_at": now_iso()}})
    elif typ == "end-of-call-report":
        await S.finalize_call(msg, lead)
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
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ["CORS_ORIGINS"].split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.on_event("shutdown")
async def shutdown():
    client.close()
