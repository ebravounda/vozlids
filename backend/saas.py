import asyncio
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Literal, Optional
from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, Response  # noqa: F401
from pydantic import BaseModel, model_validator, Field
import auth as A
import emailer
import services as S
from countries import norm_phone
from db import db
from extra_routes import require_admin
from models import Lead, now_iso

router = APIRouter(prefix="/api")
CurrentUser = Depends(A.get_current_user)
CALL_TYPES = {
    "seguimiento": ("Seguimiento de producto", "Llamas para preguntar cómo le va con el producto o servicio que contrató, si está "
                    "satisfecho y si necesita ayuda. Si tiene un problema técnico, ofrécele asistencia y usa request_support."),
    "cobro": ("Cobro de pago pendiente", "Llamas para recordar con amabilidad un pago pendiente. Indica concepto, importe y fecha de "
              "vencimiento si los tienes, pregunta cuándo podrá pagarlo y anota el compromiso. Nunca pidas datos de tarjeta."),
    "info": ("Información sobre producto", "Llamas para dar información sobre el producto indicado, resolver dudas y detectar interés."),
    "recordatorio": ("Recordatorio de cita o evento", "Llamas para recordar una cita o evento, confirmar asistencia o reprogramar."),
    "encuesta": ("Encuesta de satisfacción", "Llamas para hacer una breve encuesta de satisfacción: pide una nota del 1 al 10, qué le "
                 "gustó y qué mejorarías. Máximo 3 preguntas."),
}


def oid(v: str) -> ObjectId:
    if not ObjectId.is_valid(v):
        raise HTTPException(404, "No encontrado")
    return ObjectId(v)


def month_start() -> str:
    n = datetime.now(timezone.utc)
    return n.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


async def minutes_used(tenant_id: str) -> float:
    q = [{"$match": {"tenant_id": tenant_id, "created_at": {"$gte": month_start()}, "source": {"$ne": "web_vozleads"}}},
         {"$group": {"_id": None, "s": {"$sum": {"$ifNull": ["$duration_seconds", 0]}}}}]
    secs = 0
    for col in (db.leads, db.usage_archive):
        rows = await col.aggregate(q).to_list(1)
        secs += rows[0]["s"] if rows else 0
    return round(secs / 60, 1)


async def _quota_error(tenant_id: str) -> Optional[str]:
    user = await db.users.find_one({"_id": ObjectId(tenant_id)})
    if not user:
        return "Cuenta no encontrada"
    if user.get("suspended"):
        return "Cuenta suspendida por el administrador."
    if user.get("billing_status") == "canceled":
        return "Tu suscripción está cancelada. Contrata un plan para volver a llamar."
    plan = await db.plans.find_one({"_id": ObjectId(user["plan_id"])}) if user.get("plan_id") else None
    if not plan or user.get("allow_overage"):
        return None
    if await minutes_used(tenant_id) < plan["minutes"]:
        return None
    month = month_start()[:7]
    if user.get("quota_alert_month") != month:
        await db.users.update_one({"_id": user["_id"]}, {"$set": {"quota_alert_month": month}})
        await emailer.send(user["email"], "Has agotado los minutos de tu plan", "Minutos del plan agotados",
                           [("Plan", plan["name"]), ("Minutos incluidos", plan["minutes"]),
                            ("Qué pasa ahora", "Las llamadas están en pausa hasta el próximo mes. Puedes pedir minutos extra.")],
                           os.environ["APP_PUBLIC_URL"] + "/app")
    return f"Minutos del plan «{plan['name']}» agotados este mes. Llamadas en pausa."


# ---------- Notifications ----------
async def notify_appointment(lead: dict, when: str):
    owner = await db.users.find_one({"_id": ObjectId(lead["tenant_id"])})
    rows = [("Cliente", lead["name"]), ("Teléfono", lead["phone"]), ("Fecha y hora", when)]
    if owner:
        await emailer.send(owner["email"], f"Nueva cita: {lead['name']}", "Tu agente ha agendado una cita", rows,
                           os.environ["APP_PUBLIC_URL"] + "/app/agenda")
    if lead.get("email"):
        biz = (owner or {}).get("business_name", "")
        await emailer.send(lead["email"], f"Cita confirmada con {biz}", "Tu cita está confirmada",
                           [("Empresa", biz), ("Fecha y hora", when)])


async def tool_support(lead: dict, args: dict) -> dict:
    issue = str(args.get("issue", ""))[:1000] or "El cliente necesita asistencia técnica"
    await db.support_tickets.insert_one({"tenant_id": lead["tenant_id"], "lead_id": str(lead["_id"]), "lead_name": lead["name"],
                                         "lead_phone": lead["phone"], "issue": issue, "status": "abierta", "created_at": now_iso()})
    owner = await db.users.find_one({"_id": ObjectId(lead["tenant_id"])})
    if owner:
        await emailer.send(owner["email"], f"{lead['name']} necesita asistencia técnica", "Un cliente necesita asistencia",
                           [("Cliente", lead["name"]), ("Teléfono", lead["phone"]), ("Problema", issue)],
                           os.environ["APP_PUBLIC_URL"] + "/app/asistencia")
    return {"ok": True, "mensaje": "Solicitud registrada; el equipo técnico contactará pronto."}


async def tool_human(lead: dict, args: dict) -> dict:
    reason = str(args.get("reason", ""))[:1000] or "Quiere hablar con una persona"
    best = str(args.get("best_time", ""))[:200]
    await db.support_tickets.insert_one({"tenant_id": lead["tenant_id"], "lead_id": str(lead["_id"]), "lead_name": lead["name"],
                                         "lead_phone": lead["phone"], "issue": reason, "best_time": best, "kind": "humano",
                                         "status": "abierta", "created_at": now_iso()})
    await db.leads.update_one({"_id": lead["_id"]}, {"$set": {"wants_human": True, "updated_at": now_iso()}})
    owner = await db.users.find_one({"_id": ObjectId(lead["tenant_id"])})
    if owner:
        rows = [("Cliente", lead["name"]), ("Teléfono", lead["phone"]), ("Motivo", reason)]
        if best:
            rows.append(("Mejor momento para llamar", best))
        await emailer.send(owner["email"], f"{lead['name']} quiere hablar con una persona",
                           "Uno de tus clientes necesita asistencia", rows, os.environ["APP_PUBLIC_URL"] + "/app/asistencia")
    return {"ok": True, "mensaje": "Aviso enviado; una persona del equipo le llamará lo antes posible."}


S.TOOLS["request_support"] = tool_support
S.TOOLS["request_human"] = tool_human


@router.get("/support-tickets/open-count")
async def open_tickets(user=CurrentUser):
    flt = {"tenant_id": user["id"], "status": "abierta"}
    return {"open": await db.support_tickets.count_documents(flt),
            "human": await db.support_tickets.count_documents({**flt, "kind": "humano"})}


@router.get("/support-tickets")
async def list_tickets(user=CurrentUser):
    docs = await db.support_tickets.find({"tenant_id": user["id"]}).sort("created_at", -1).to_list(300)
    return [{**{k: v for k, v in d.items() if k != "_id"}, "id": str(d["_id"])} for d in docs]


@router.put("/support-tickets/{tid}/resolve")
async def resolve_ticket(tid: str, user=CurrentUser):
    await db.support_tickets.update_one({"_id": oid(tid), "tenant_id": user["id"]}, {"$set": {"status": "resuelta"}})
    return {"ok": True}


# ---------- Super admin: plans & users ----------
class PlanIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    minutes: int = Field(ge=1, le=1000000)
    price_eur: float = Field(ge=0)
    price_clp: float = Field(ge=0)
    overage_eur: float = Field(0, ge=0)
    overage_clp: float = Field(0, ge=0)
    features: List[str] = Field(default=[], max_length=8)
    public: bool = True
    recommended: bool = False
    promo_active: bool = False
    promo_label: str = Field("PROMOCIÓN", max_length=30)
    promo_price_eur: float = Field(0, ge=0)
    promo_price_clp: float = Field(0, ge=0)
    promo_months: int = Field(3, ge=1, le=24)
    limits: dict = {}

    @model_validator(mode="after")
    def _limits(self):
        import plan_limits as PL
        self.limits = PL.LimitsIn(**(self.limits or {})).model_dump()
        return self

    @model_validator(mode="after")
    def _promo(self):
        if self.promo_active:
            if not (0 < self.promo_price_eur < self.price_eur or 0 < self.promo_price_clp < self.price_clp):
                raise ValueError("El precio de promoción debe ser mayor que 0 y menor que el precio normal (al menos en un país)")
            for promo, normal in ((self.promo_price_eur, self.price_eur), (self.promo_price_clp, self.price_clp)):
                if promo >= normal > 0 and promo:
                    raise ValueError("El precio de promoción debe ser menor que el precio normal")
            self.promo_label = self.promo_label.strip() or "PROMOCIÓN"
        return self


async def _one_recommended(body: PlanIn, pid=None) -> None:
    if body.recommended:
        await db.plans.update_many({"_id": {"$ne": pid}} if pid else {}, {"$set": {"recommended": False}})


def plan_out(p: dict) -> dict:
    return {**{k: v for k, v in p.items() if k != "_id"}, "id": str(p["_id"])}


@router.get("/public/plans")
async def public_plans():
    return [plan_out(p) async for p in db.plans.find({"public": True}).sort("minutes", 1)]


@router.get("/admin/plans")
async def list_plans(user=Depends(require_admin)):
    return [plan_out(p) async for p in db.plans.find().sort("minutes", 1)]


@router.post("/admin/plans")
async def create_plan(body: PlanIn, user=Depends(require_admin)):
    await _one_recommended(body)
    res = await db.plans.insert_one({**body.model_dump(), "created_at": now_iso()})
    return {**body.model_dump(), "id": str(res.inserted_id)}


@router.put("/admin/plans/{pid}")
async def update_plan(pid: str, body: PlanIn, user=Depends(require_admin)):
    if not await db.plans.find_one({"_id": oid(pid)}, {"_id": 1}):
        raise HTTPException(404, "Plan no encontrado")
    await _one_recommended(body, oid(pid))
    await db.plans.update_one({"_id": oid(pid)}, {"$set": body.model_dump()})
    return {**body.model_dump(), "id": pid}


@router.delete("/admin/plans/{pid}")
async def delete_plan(pid: str, user=Depends(require_admin)):
    if await db.users.count_documents({"plan_id": pid}):
        raise HTTPException(400, "Hay cuentas usando este plan.")
    await db.plans.delete_one({"_id": oid(pid)})
    return {"ok": True}


@router.get("/admin/users")
async def admin_users(user=Depends(require_admin)):
    out = []
    async for u in db.users.find({}, {"password_hash": 0}).sort("created_at", -1):
        uid = str(u["_id"])
        out.append({"id": uid, "email": u["email"], "name": u.get("name"), "business_name": u.get("business_name"),
                    "country": u.get("country", "ES"), "role": u.get("role", "business"), "plan_id": u.get("plan_id"),
                    "allow_overage": u.get("allow_overage", False), "suspended": u.get("suspended", False),
                    "minutes_used": await minutes_used(uid), "calls": await db.leads.count_documents({"tenant_id": uid, "vapi_call_id": {"$ne": None}}),
                    "agents": await db.agents.count_documents({"tenant_id": uid}), "created_at": u.get("created_at"),
                    "split_from_admin": bool(u.get("split_from_admin")), "admin_only": bool(u.get("admin_only"))})
    return out


class UserUpdate(BaseModel):
    plan_id: Optional[str] = None
    allow_overage: bool = False
    suspended: bool = False


@router.put("/admin/users/{uid}")
async def admin_update_user(uid: str, body: UserUpdate, user=Depends(require_admin)):
    if body.plan_id and not await db.plans.find_one({"_id": oid(body.plan_id)}):
        raise HTTPException(422, "Plan no encontrado")
    await db.users.update_one({"_id": oid(uid)}, {"$set": body.model_dump()})
    return {"ok": True}


class ProfileIn(BaseModel):
    business_name: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=200)
    contact_phone: str = Field("", max_length=25)
    sector: str = Field("", max_length=80)
    website: str = Field("", max_length=200)
    business_hours: str = Field("", max_length=200)


def profile_out(u: dict) -> dict:
    return {k: u.get(k) or "" for k in ProfileIn.model_fields}


@router.get("/admin/users/{uid}/profile")
async def admin_get_profile(uid: str, user=Depends(require_admin)):
    u = await db.users.find_one({"_id": oid(uid)})
    if not u:
        raise HTTPException(404, "Cuenta no encontrada")
    return profile_out(u)


@router.put("/admin/users/{uid}/profile")
async def admin_put_profile(uid: str, body: ProfileIn, user=Depends(require_admin)):
    import re
    u = await db.users.find_one({"_id": oid(uid)})
    if not u:
        raise HTTPException(404, "Cuenta no encontrada")
    email = body.email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(422, "Email no válido")
    if email != u["email"] and await db.users.find_one({"email": email}):
        raise HTTPException(409, "Ya existe otra cuenta con ese email")
    phone = norm_phone(body.contact_phone, u.get("country", "ES")) if body.contact_phone.strip() else ""
    web = body.website.strip()
    upd = {"business_name": body.business_name.strip(), "name": body.name.strip(), "email": email, "contact_phone": phone,
           "sector": body.sector.strip(), "website": web if not web or web.startswith("http") else f"https://{web}",
           "business_hours": body.business_hours.strip(), "updated_at": now_iso()}
    await db.users.update_one({"_id": u["_id"]}, {"$set": upd})
    stripe_ok = None
    if u.get("stripe_customer_id"):
        import billing
        try:
            c, _, proxy = await billing.client(u.get("stripe_mode", "live"))
            if not proxy:
                await asyncio.to_thread(c.v1.customers.update, u["stripe_customer_id"], {
                    "name": upd["business_name"], "email": email, **({"phone": phone} if phone else {}),
                    "metadata": {"contacto": upd["name"]}})
                stripe_ok = True
        except Exception as e:  # noqa: BLE001
            stripe_ok = False
            import logging
            logging.getLogger("vozlead.saas").warning("Stripe customer update failed: %s", str(e)[:200])
    return {**profile_out({**u, **upd}), "stripe_updated": stripe_ok}


@router.delete("/admin/users/{uid}")
async def admin_delete_user(uid: str, user=Depends(require_admin)):
    if uid == user["id"]:
        raise HTTPException(400, "No puedes eliminar tu propia cuenta.")
    if not (await db.users.delete_one({"_id": oid(uid), "role": {"$ne": "admin"}})).deleted_count:
        raise HTTPException(404, "Cuenta no encontrada")
    for col in ("agents", "leads", "appointments", "dnc", "availability", "call_templates", "scheduled_calls",
                "support_tickets", "api_keys", "ambience_files", "kyc"):
        await db[col].delete_many({"tenant_id": uid})
    return {"ok": True}


@router.post("/admin/users/{uid}/impersonate")
async def impersonate(uid: str, response: Response, request: Request, user=Depends(require_admin)):
    target = await db.users.find_one({"_id": oid(uid)})
    if not target:
        raise HTTPException(404, "Usuario no encontrado")
    response.set_cookie("imp", A.create_refresh_token(user["id"]), httponly=True, secure=True, samesite="none",
                        max_age=7200, path="/")
    A.set_auth_cookies(response, uid, target["email"])
    return {"ok": True}


class SplitIn(BaseModel):
    email: str = Field(min_length=5, max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


SPLIT_KEEP = {"users", "platform_settings", "plans", "login_attempts", "oauth_states", "ip_geo", "tts_cache", "api_rate", "system.views"}
NO_COPY = {"_id", "email", "password_hash", "role", "plan_id", "billing_status", "stripe_customer_id", "stripe_subscription_id",
           "stripe_mode", "billing_test", "tour_done", "created_at", "admin_only", "client_id"}


@router.post("/admin/split-account")
async def split_account(body: SplitIn, user=Depends(require_admin)):
    """One-time: move the admin's own business (agents, leads, numbers…) to a normal client account; the admin stays admin-only."""
    admin = await db.users.find_one({"_id": oid(user["id"])})
    if admin.get("admin_only"):
        raise HTTPException(409, "Tu cuenta ya está separada.")
    email = body.email.strip().lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(409, "Ese email ya tiene una cuenta en VozLeads.")
    client = {k: v for k, v in admin.items() if k not in NO_COPY}
    res = await db.users.insert_one({**client, "email": email, "password_hash": admin["password_hash"], "role": "business",
                                     "created_at": now_iso(), "split_from_admin": True})
    new_id, old_id = str(res.inserted_id), user["id"]
    moved = {}
    for col in await db.list_collection_names():
        if col in SPLIT_KEEP:
            continue
        r = await db[col].update_many({"tenant_id": old_id}, {"$set": {"tenant_id": new_id}})
        if r.modified_count:
            moved[col] = r.modified_count
    await db.users.update_one({"_id": admin["_id"]}, {"$set": {"admin_only": True, "client_id": new_id, "business_name": "Administración VozLeads"}})
    return {"ok": True, "client_id": new_id, "email": email, "moved": moved}


@router.post("/auth/stop-impersonation")
async def stop_impersonation(request: Request, response: Response):
    token = request.cookies.get("imp")
    if not token:
        raise HTTPException(400, "No estás suplantando ninguna cuenta")
    admin = await A.get_user_by_id(A.decode(token, "refresh")["sub"])
    if admin.get("role") != "admin":
        raise HTTPException(403, "No autorizado")
    A.set_auth_cookies(response, admin["id"], admin["email"])
    response.delete_cookie("imp", path="/", secure=True, samesite="none")
    return {"ok": True}


async def quota_error(tenant_id: str) -> Optional[str]:
    import plan_limits as PL
    return await _quota_error(tenant_id) or await PL.concurrency_error(tenant_id)


async def usage_alerts() -> int:
    """Email each tenant once per month when they reach 80 % and 100 % of their plan minutes."""
    month, sent = month_start()[:7], 0
    async for u in db.users.find({"plan_id": {"$nin": [None, ""]}, "role": {"$ne": "admin"}, "billing_status": "active"},
                                 {"plan_id": 1, "email": 1, "usage_alerts": 1, "allow_overage": 1}):
        if not ObjectId.is_valid(u["plan_id"]):
            continue
        plan = await db.plans.find_one({"_id": ObjectId(u["plan_id"])}, {"minutes": 1, "name": 1})
        if not plan or not plan.get("minutes"):
            continue
        used = await minutes_used(str(u["_id"]))
        done = (u.get("usage_alerts") or {}).get(month, [])
        for pct in (100, 80):
            if used >= plan["minutes"] * pct / 100 and pct not in done:
                site = os.environ["APP_PUBLIC_URL"].rstrip("/")
                tail = ("Tus llamadas siguen funcionando: los minutos extra se cobran aparte." if u.get("allow_overage")
                        else "Las llamadas quedan en pausa hasta el mes que viene o hasta que mejores tu plan.") if pct == 100 \
                    else "Si crees que te faltarán minutos, puedes mejorar tu plan en un clic."
                await emailer.send(u["email"], f"Has usado el {pct}% de tus minutos de VozLeads",
                                   "Minutos agotados" if pct == 100 else "Te queda poco saldo de minutos",
                                   [("Plan", plan["name"]), ("Minutos usados", f"{used:g} de {plan['minutes']}")],
                                   f"{site}/app/plan", tail, "Ver mi plan")
                await db.users.update_one({"_id": u["_id"]}, {"$set": {f"usage_alerts.{month}": sorted({*done, 80, pct})}})
                sent += 1
                break
    return sent


@router.get("/account/usage")
async def my_usage(user=CurrentUser):
    import plan_limits as PL
    plan = await db.plans.find_one({"_id": ObjectId(user["plan_id"])}) if user.get("plan_id") else None
    cur = "clp" if user.get("country") == "CL" else "eur"
    return {"minutes_used": await minutes_used(user["id"]),
            "plan": plan and {"name": plan["name"], "minutes": plan["minutes"], "currency": cur.upper(),
                              "price": plan.get(f"price_{cur}", 0), "overage_price": plan.get(f"overage_{cur}", 0)},
            "allow_overage": user.get("allow_overage", False), "plan_id": user.get("plan_id"),
            "has_subscription": bool(user.get("stripe_subscription_id")) and user.get("billing_status") == "active", "limits": await PL.for_tenant(user["id"]),
            "agents": await db.agents.count_documents({"tenant_id": user["id"]}), "is_admin": user.get("role") == "admin"}


# ---------- Templates & outbound calls ----------
class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    call_type: Literal[tuple(CALL_TYPES)]
    purpose: str = Field(min_length=1, max_length=2000)
    greeting: str = Field(min_length=1, max_length=600)


TEMPLATE_GREETING = "Hola {nombre}, soy {agente}, de {empresa}. Te llamo un momento y la llamada se graba. ¿Tienes un minuto?"


@router.get("/templates")
async def list_templates(user=CurrentUser):
    if not await db.call_templates.count_documents({"tenant_id": user["id"]}):
        await db.call_templates.insert_many([{
            "tenant_id": user["id"], "name": label, "call_type": k, "purpose": text, "created_at": now_iso(),
            "greeting": TEMPLATE_GREETING}
            for k, (label, text) in CALL_TYPES.items()])
    docs = await db.call_templates.find({"tenant_id": user["id"]}).sort("created_at", 1).to_list(100)
    return [{**{k: v for k, v in d.items() if k != "_id"}, "id": str(d["_id"])} for d in docs]


@router.post("/templates")
async def create_template(body: TemplateIn, user=CurrentUser):
    res = await db.call_templates.insert_one({**body.model_dump(), "tenant_id": user["id"], "created_at": now_iso()})
    return {**body.model_dump(), "id": str(res.inserted_id)}


@router.put("/templates/{tid}")
async def update_template(tid: str, body: TemplateIn, user=CurrentUser):
    await db.call_templates.update_one({"_id": oid(tid), "tenant_id": user["id"]}, {"$set": body.model_dump()})
    return {**body.model_dump(), "id": tid}


@router.delete("/templates/{tid}")
async def delete_template(tid: str, user=CurrentUser):
    await db.call_templates.delete_one({"_id": oid(tid), "tenant_id": user["id"]})
    return {"ok": True}


async def place_call(agent: dict, name: str, phone: str, email: str, purpose: str, greeting: str, source: str) -> dict:
    if await db.dnc.find_one({"tenant_id": agent["tenant_id"], "phone": phone}):
        return {"status": "no_llamar", "error": "Número en la lista de no llamar"}
    lead = Lead(tenant_id=agent["tenant_id"], agent_id=str(agent["_id"]), agent_name=agent["name"], name=name, phone=phone,
                email=email, purpose=purpose, greeting=greeting, source=source)
    doc = lead.to_mongo()
    res = await db.leads.insert_one(doc)
    doc["_id"] = res.inserted_id
    await S.dial(agent, doc)
    return Lead.from_mongo(await db.leads.find_one({"_id": res.inserted_id})).out()


class Contact(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    phone: str
    email: str = ""


class ScheduleIn(BaseModel):
    agent_id: str
    template_id: str
    contacts: List[Contact] = Field(min_length=1, max_length=500)
    run_at: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$")


async def _agent(tenant_id: str, agent_id: str) -> dict:
    agent = await db.agents.find_one({"_id": oid(agent_id), "tenant_id": tenant_id})
    if not agent:
        raise HTTPException(404, "Agente no encontrado")
    return agent


def _to_utc(local: str, country: str) -> str:
    dt = datetime.fromisoformat(local).replace(tzinfo=S.tz_of(country))
    if dt <= datetime.now(timezone.utc):
        raise HTTPException(422, "La fecha y hora programadas ya han pasado.")
    return dt.astimezone(timezone.utc).isoformat()


@router.post("/scheduled-calls")
async def schedule_calls(body: ScheduleIn, user=CurrentUser):
    import plan_limits as PL
    await PL.require(user["id"], "outbound")
    agent = await _agent(user["id"], body.agent_id)
    tpl = await db.call_templates.find_one({"_id": oid(body.template_id), "tenant_id": user["id"]})
    if not tpl:
        raise HTTPException(404, "Plantilla no encontrada")
    country = agent.get("country", "ES")
    run_at = _to_utc(body.run_at, country) if body.run_at else now_iso()
    docs = [{"tenant_id": user["id"], "agent_id": body.agent_id, "template_id": body.template_id, "template_name": tpl["name"],
             "name": c.name.strip(), "phone": norm_phone(c.phone, country), "email": c.email.strip().lower(),
             "purpose": tpl["purpose"], "greeting": tpl["greeting"], "run_at": run_at, "run_at_local": body.run_at,
             "country": country, "status": "pendiente", "created_at": now_iso()} for c in body.contacts]
    await db.scheduled_calls.insert_many(docs)
    if not body.run_at:
        asyncio.create_task(dispatch_due())
    return {"ok": True, "count": len(docs)}


@router.get("/scheduled-calls")
async def list_scheduled(user=CurrentUser):
    docs = await db.scheduled_calls.find({"tenant_id": user["id"]}).sort("run_at", -1).to_list(500)
    return [{**{k: v for k, v in d.items() if k not in ("_id", "purpose", "greeting")}, "id": str(d["_id"])} for d in docs]


@router.delete("/scheduled-calls/{sid}")
async def cancel_scheduled(sid: str, user=CurrentUser):
    await db.scheduled_calls.update_one({"_id": oid(sid), "tenant_id": user["id"], "status": "pendiente"},
                                        {"$set": {"status": "cancelada"}})
    return {"ok": True}


async def dispatch_due():
    while True:
        job = await db.scheduled_calls.find_one_and_update({"status": "pendiente", "run_at": {"$lte": now_iso()}},
                                                           {"$set": {"status": "en_proceso"}})
        if not job:
            return
        import plan_limits as PL
        if await PL.concurrency_error(job["tenant_id"]):
            await db.scheduled_calls.update_one({"_id": job["_id"]}, {"$set": {"status": "pendiente", "run_at": (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat()}})
            continue
        agent = await db.agents.find_one({"_id": ObjectId(job["agent_id"])})
        result = await place_call(agent, job["name"], job["phone"], job["email"], job["purpose"], job["greeting"],
                                  "programada") if agent else {"status": "fallida", "error": "Agente eliminado"}
        await db.scheduled_calls.update_one({"_id": job["_id"]}, {"$set": {
            "status": "realizada" if result.get("status") not in ("fallida", "no_llamar") else result["status"],
            "lead_id": result.get("id"), "error": result.get("error", "")}})


@router.post("/cron/dispatch")
async def cron_dispatch(background: BackgroundTasks, authorization: str = Header("")):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    if not secrets.compare_digest(authorization, f"Bearer {os.environ['WEBHOOK_CRON_SECRET']}"):
        raise HTTPException(401, "No autorizado")
    background.add_task(dispatch_due)
    return {"ok": True}


# ---------- Public API ----------
def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


@router.get("/api-keys")
async def list_keys(user=CurrentUser):
    docs = await db.api_keys.find({"tenant_id": user["id"], "revoked": False}).to_list(50)
    return [{"id": str(d["_id"]), "prefix": d["prefix"], "name": d["name"], "created_at": d["created_at"]} for d in docs]


class KeyIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)


@router.post("/api-keys")
async def create_key(body: KeyIn, user=CurrentUser):
    key = "vl_live_" + secrets.token_urlsafe(32)
    res = await db.api_keys.insert_one({"tenant_id": user["id"], "key_hash": _hash(key), "prefix": key[:14], "name": body.name,
                                        "revoked": False, "created_at": now_iso()})
    return {"id": str(res.inserted_id), "key": key, "prefix": key[:14], "name": body.name}


@router.delete("/api-keys/{kid}")
async def revoke_key(kid: str, user=CurrentUser):
    await db.api_keys.update_one({"_id": oid(kid), "tenant_id": user["id"]}, {"$set": {"revoked": True}})
    return {"ok": True}


class ApiCallIn(BaseModel):
    agent_id: str
    name: str = Field(min_length=1, max_length=80)
    phone: str
    email: str = ""
    type: Literal[tuple(CALL_TYPES)]
    consent: bool
    context: dict = {}
    scheduled_at: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$")


def _purpose(call_type: str, ctx: dict) -> str:
    details = "; ".join(f"{k}: {str(v)[:200]}" for k, v in list(ctx.items())[:10])
    return CALL_TYPES[call_type][1] + (f"\nDatos de esta llamada: {details}" if details else "")
