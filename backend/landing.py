import logging
from datetime import datetime, timedelta, timezone
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
import emailer
import extra_routes as X
import services as S
from countries import COUNTRIES, norm_phone
from db import db
from models import Lead, now_iso

router = APIRouter(prefix="/api")
log = logging.getLogger("vozlead.landing")
MAX_SECONDS = 45
PURPOSE = ("Llamada de bienvenida MUY BREVE, de unos 40 segundos como máximo, porque {name} acaba de pedir información en la "
           "web de VozLeads. 1) Confirma en una frase que llamas de VozLeads, agentes de voz con inteligencia artificial que "
           "llaman a los clientes de una empresa en segundos, y que esta misma llamada es un ejemplo. 2) Pregunta qué tipo de "
           "negocio tiene. 3) Dile que un asesor le contactará muy pronto para enseñarle una demo y despídete con amabilidad. "
           "No des precios ni explicaciones largas: si pregunta algo, responde en una sola frase. Termina la llamada con endCall.")
GREETING = "Hola {nombre}, te llamo de VozLeads porque acabas de pedir información en nuestra web. ¿Tienes un momento?"


def _ago(minutes: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


async def settings() -> dict:
    return (await db.platform_settings.find_one({"_id": "landing"})) or {}


async def _agent(agent_id: str):
    try:
        return await db.agents.find_one({"_id": ObjectId(agent_id)}) if agent_id else None
    except InvalidId:
        return None


class InfoIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    phone: str = Field(min_length=8, max_length=20)
    country: str = Field(pattern="^(ES|CL)$")
    consent: bool
    page: str = Field("/", max_length=120)


async def _call(agent: dict, name: str, phone: str) -> str:
    if await db.dnc.find_one({"tenant_id": agent["tenant_id"], "phone": phone}):
        return "no_llamar"
    lead = Lead(tenant_id=agent["tenant_id"], agent_id=str(agent["_id"]), agent_name=agent["name"], name=name, phone=phone,
                purpose=PURPOSE.format(name=name), greeting=GREETING, source="web_vozleads", max_seconds=MAX_SECONDS)
    doc = lead.to_mongo()
    res = await db.leads.insert_one(doc)
    doc["_id"] = res.inserted_id
    await S.dial(agent, doc)
    return (await db.leads.find_one({"_id": res.inserted_id}))["status"]


async def _notify(cfg: dict, req: dict) -> None:
    to = cfg.get("notify_email") or ((await db.users.find_one({"role": "admin"}, {"email": 1})) or {}).get("email", "")
    await emailer.send(to, f"Nueva solicitud de información: {req['name']}", "Alguien ha pedido información en la web", [
        ("Nombre", req["name"]), ("Teléfono", req["phone"]), ("País", COUNTRIES[req["country"]]["name"]),
        ("Página", req["page"]), ("Llamada IA", "Sí, en curso" if req["call_status"] not in ("", "sin_agente", "fallida") else "No")])


@router.post("/public/info-request")
async def info_request(body: InfoIn, request: Request):
    if not body.consent:
        raise HTTPException(400, "Debes aceptar que te llamemos para continuar.")
    phone = norm_phone(body.phone, body.country)
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "").split(",")[0].strip()
    if ip and await db.info_requests.count_documents({"ip": ip, "created_at": {"$gt": _ago(10)}}) >= 3:
        raise HTTPException(429, "Ya hemos recibido tus datos. Inténtalo de nuevo en unos minutos.")
    name = " ".join(body.name.split())
    req = {"name": name, "phone": phone, "country": body.country, "page": body.page, "ip": ip, "created_at": now_iso(), "call_status": ""}
    repeated = await db.info_requests.find_one({"phone": phone, "created_at": {"$gt": _ago(24 * 60)}})
    cfg = await settings()
    agent = await _agent(cfg.get(f"agent_{body.country.lower()}", ""))
    if repeated:
        req["call_status"] = "repetida"
    elif agent and agent.get("active") and agent.get("country", "ES") == body.country:
        try:
            req["call_status"] = await _call(agent, name, phone)
        except Exception as e:  # noqa: BLE001
            log.warning("Landing call failed: %s", e)
            req["call_status"] = "fallida"
    else:
        req["call_status"] = "sin_agente"
    await db.info_requests.insert_one(req)
    if not repeated:
        await _notify(cfg, req)
    return {"ok": True, "calling": req["call_status"] in ("llamando", "en_curso")}


class LandingCfg(BaseModel):
    agent_es: str = ""
    agent_cl: str = ""
    notify_email: str = Field("", max_length=200)


@router.get("/admin/landing")
async def get_landing(user=Depends(X.require_admin)):
    cfg = await settings()
    return {k: cfg.get(k, "") for k in ("agent_es", "agent_cl", "notify_email")}


@router.put("/admin/landing")
async def put_landing(body: LandingCfg, user=Depends(X.require_admin)):
    for c in ("es", "cl"):
        aid = getattr(body, f"agent_{c}")
        if aid:
            a = await _agent(aid)
            if not a or a.get("country", "ES") != c.upper():
                raise HTTPException(422, f"El agente elegido para {COUNTRIES[c.upper()]['name']} no es de ese país.")
    await db.platform_settings.update_one({"_id": "landing"}, {"$set": {**body.model_dump(), "updated_at": now_iso()}}, upsert=True)
    return {"ok": True}


@router.get("/admin/info-requests")
async def list_requests(user=Depends(X.require_admin)):
    docs = await db.info_requests.find({}, {"ip": 0}).sort("created_at", -1).to_list(200)
    return [{**{k: v for k, v in d.items() if k != "_id"}, "id": str(d["_id"])} for d in docs]
