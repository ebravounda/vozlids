import logging
from datetime import datetime, timedelta, timezone
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
import emailer
import extra_routes as X
import services as S
from countries import COUNTRIES, DEMO_DIALS, norm_demo_phone
from db import db
from models import Lead, now_iso

router = APIRouter(prefix="/api")
log = logging.getLogger("vozlead.landing")
MAX_SECONDS = 20
INTL_DAILY_CAP = 40
DAILY_CALL_CAP = 20
CALL_LABELS = {"llamando": "Sí, llamando ahora", "en_curso": "Sí, en curso", "sin_agente": "No: no hay agente de demo configurado",
               "fallida": "No: la llamada falló (revisa Leads)", "no_llamar": "No: el número pidió no ser llamado",
               "limite_diario": "No: tope diario de demos alcanzado", "limite_internacional": "No: tope internacional alcanzado"}
NO_CALL = ["", "sin_agente", "fallida", "repetida", "limite_internacional", "limite_diario"]
PURPOSE = ("MUESTRA de 10 a 15 segundos como máximo: {name} pidió escuchar un ejemplo en la web de VozLeads. Ya has dicho el "
           "saludo con todo lo necesario. Si responde algo, contesta en UNA frase muy corta, despídete con \"¡hasta luego!\" y "
           "termina la llamada con endCall de inmediato. No hagas preguntas ni des precios.")
GREETING = ("Hola {nombre}, soy {agente}, de VozLeads. Esta es tu muestra: así de rápido llamaríamos a tus clientes. "
            "Un asesor te escribirá muy pronto. ¡Hasta luego!")


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
    country: str = Field(min_length=2, max_length=2)
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
    await S.dial({**agent, "business_name": "VozLeads"}, doc)
    return (await db.leads.find_one({"_id": res.inserted_id}))["status"]


async def _notify(cfg: dict, req: dict) -> None:
    to = cfg.get("notify_email") or ((await db.users.find_one({"role": "admin"}, {"email": 1})) or {}).get("email", "")
    await emailer.send(to, f"Nueva solicitud de información: {req['name']}", "Alguien ha pedido información en la web", [
        ("Nombre", req["name"]), ("Teléfono", req["phone"]), ("País", (COUNTRIES.get(req["country"]) or {}).get("name", req["country"])),
        ("Página", req["page"]), ("Llamada IA", CALL_LABELS.get(req["call_status"], req["call_status"] or "No"))])


def client_ip(request: Request) -> str:
    h = request.headers
    xff = [x.strip() for x in h.get("x-forwarded-for", "").split(",") if x.strip()]
    return (h.get("cf-connecting-ip") or h.get("x-real-ip") or (xff[-1] if xff else "")
            or (request.client.host if request.client else "")).strip()


async def daily_cap_reached() -> bool:
    n = await db.info_requests.count_documents({"created_at": {"$gt": _ago(24 * 60)}, "call_status": {"$nin": NO_CALL}})
    return n >= DAILY_CALL_CAP


@router.get("/public/geo")
async def geo(request: Request):
    return {"country": (request.headers.get("cf-ipcountry") or "").upper()[:2]}


@router.post("/public/info-request")
async def info_request(body: InfoIn, request: Request):
    if not body.consent:
        raise HTTPException(400, "Debes aceptar que te llamemos para continuar.")
    if body.country not in DEMO_DIALS:
        raise HTTPException(422, "Por ahora solo hacemos llamadas de muestra a España y a países de Latinoamérica.")
    try:
        phone = norm_demo_phone(body.phone, body.country)
    except ValueError as e:
        raise HTTPException(422, str(e))
    import security_admin as SEC
    ip = client_ip(request)
    await SEC.guard_public(phone, ip=ip, cf_country=request.headers.get("cf-ipcountry", ""))
    if ip and await db.info_requests.count_documents({"ip": ip, "created_at": {"$gt": _ago(10)}}) >= 3:
        raise HTTPException(429, "Ya hemos recibido tus datos. Inténtalo de nuevo en unos minutos.")
    name = " ".join(body.name.split())
    req = {"name": name, "phone": phone, "country": body.country, "page": body.page, "ip": ip, "created_at": now_iso(), "call_status": "",
           "intl": body.country not in COUNTRIES}
    repeated = await db.info_requests.find_one({"phone": phone, "created_at": {"$gt": _ago(24 * 60)}})
    cfg = await settings()
    market = body.country if body.country in COUNTRIES else "ES"
    agent = await _agent(cfg.get(f"agent_{market.lower()}", ""))
    intl = market != body.country
    if repeated:
        req["call_status"] = "repetida"
    elif await daily_cap_reached():
        req["call_status"] = "limite_diario"
        import monitor
        await monitor.notify("demo_cap", f"Tope diario de {DAILY_CALL_CAP} llamadas de prueba alcanzado",
                             [("Qué pasa", "Las nuevas solicitudes de la web se guardan pero no se llama"),
                              ("Se reanuda", "Automáticamente cuando pasen 24 h desde las primeras llamadas")], every_hours=24)
    elif intl and await db.info_requests.count_documents({"intl": True, "created_at": {"$gt": _ago(24 * 60)}}) >= INTL_DAILY_CAP:
        req["call_status"] = "limite_internacional"
    elif agent and agent.get("active") and agent.get("country", "ES") == market:
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
    return {"ok": True, "calling": req["call_status"] in ("llamando", "en_curso"), "repeated": bool(repeated)}


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
