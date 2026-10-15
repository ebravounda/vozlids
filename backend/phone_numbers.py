import asyncio
import logging
import os
import secrets
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import emailer
import extra_routes as X
import vapi
import zadarma as Z
from auth import get_current_user
from countries import COUNTRIES
from db import db
from models import Lead, now_iso

router = APIRouter(prefix="/api")
log = logging.getLogger("vozlead.numbers")
CurrentUser = Depends(get_current_user)
BUSY = {"comprando"}


async def record(tenant_id: str):
    return await db.tenant_numbers.find_one({"tenant_id": tenant_id})


async def phone_id_for(tenant_id: str, country: str):
    r = await record(tenant_id)
    return r["phone_number_id"] if r and r.get("status") == "activo" and r.get("country") == country else None


def _out(r: dict | None) -> dict:
    if not r:
        return {"status": "sin_numero"}
    keep = ("tenant_id", "country", "number", "status", "error", "inbound_agent_id", "created_at", "activated_at", "released_at")
    return {k: r.get(k) for k in keep}


async def _default_agent(tenant_id: str, country: str):
    a = await db.agents.find_one({"tenant_id": tenant_id, "country": country, "objective": "recepcion", "active": True}) or \
        await db.agents.find_one({"tenant_id": tenant_id, "country": country, "active": True})
    return str(a["_id"]) if a else ""


async def provision(user_id: str) -> dict:
    u = await db.users.find_one({"_id": ObjectId(user_id)})
    cur = await record(user_id)
    if not u or (cur and cur.get("status") in ("activo", *BUSY)):
        return _out(cur)
    country = u.get("country", "ES")
    cfg = await Z.creds()
    direction = cfg.get(f"direction_{country.lower()}")
    base = {"tenant_id": user_id, "country": country, "updated_at": now_iso()}
    await db.tenant_numbers.update_one({"tenant_id": user_id}, {"$set": {**base, "status": "comprando", "error": ""},
                                                                 "$setOnInsert": {"created_at": now_iso()}}, upsert=True)
    try:
        if not direction:
            raise Z.ZadarmaError(f"Falta elegir la ciudad/tipo de número de {COUNTRIES[country]['name']} en Super admin → Zadarma.")
        number = await Z.order(direction, cfg.get(f"docs_{country.lower()}", ""))
        await db.tenant_numbers.update_one({"tenant_id": user_id}, {"$set": {"number": number}})
        pwd = secrets.token_urlsafe(10) + "Vz7"
        sip = await Z.create_sip(f"VozLeads {u.get('business_name', '')}", pwd, number)
        await Z.route_to(number, vapi.inbound_sip_uri(number))
        v = await vapi.connect_tenant_number(sip, pwd, number, u.get("business_name") or u["email"])
        await db.tenant_numbers.update_one({"tenant_id": user_id}, {"$set": {
            "status": "activo", "sip_id": sip, **v, "activated_at": now_iso(),
            "inbound_agent_id": (cur or {}).get("inbound_agent_id") or await _default_agent(user_id, country)}})
        await emailer.send(u["email"], f"Tu número {number} ya está activo", "¡Tu número de VozLeads está listo!", [
            ("Número", number), ("Llamadas salientes", "Tus agentes ya llaman desde este número"),
            ("Llamadas entrantes", "Tu recepcionista IA contesta cuando te llamen")], os.environ["APP_PUBLIC_URL"] + "/app/telefonia")
    except (Z.ZadarmaError, vapi.VapiError) as e:
        log.warning("Provision failed for %s: %s", user_id, e)
        await db.tenant_numbers.update_one({"tenant_id": user_id}, {"$set": {"status": "error", "error": str(e)[:300]}})
        admin = await db.users.find_one({"role": "admin"}, {"email": 1})
        if admin:
            await emailer.send(admin["email"], "No se pudo asignar un número", "Error al comprar número en Zadarma", [
                ("Cliente", u["email"]), ("País", COUNTRIES[country]["name"]), ("Error", str(e)[:300])],
                os.environ["APP_PUBLIC_URL"] + "/app/admin")
    return _out(await record(user_id))


async def release(user_id: str) -> dict:
    r = await record(user_id)
    if not r or r.get("platform") or r.get("status") not in ("activo", "error"):
        return _out(r)
    errors = []
    if r.get("number"):
        try:
            await Z.autorenew(r["number"], False)
        except Z.ZadarmaError as e:
            errors.append(str(e))
    for path in (f"/phone-number/{r.get('phone_number_id')}", f"/credential/{r.get('credential_id')}"):
        if "None" not in path:
            await vapi.delete(path)
    await db.tenant_numbers.update_one({"_id": r["_id"]}, {"$set": {
        "status": "liberado", "released_at": now_iso(), "error": "; ".join(errors)[:300], "phone_number_id": None}})
    return _out(await record(user_id))


async def auto_provision(user_id: str, test_payment: bool):
    cfg = await Z.creds()
    if cfg.get("key") and (not test_payment or cfg.get("buy_on_test")):
        await provision(user_id)


# ---------- Inbound: Vapi assistant-request ----------
UNAVAILABLE = "Hola, gracias por llamar. Ahora mismo no podemos atenderte; por favor, inténtalo de nuevo más tarde. ¡Hasta luego!"


def _short(text: str) -> dict:
    return {"assistant": {"firstMessage": text, "maxDurationSeconds": 20, "endCallPhrases": ["hasta luego"],
                          "model": {"provider": "openai", "model": "gpt-4.1-mini", "messages": [
                              {"role": "system", "content": "Despídete con amabilidad y termina la llamada."}],
                              "tools": [{"type": "endCall"}]}}}


async def assistant_request(msg: dict) -> dict:
    import saas
    import services as S
    call = msg.get("call") or {}
    r = await db.tenant_numbers.find_one({"phone_number_id": call.get("phoneNumberId"), "status": "activo"})
    if not r:
        return _short(UNAVAILABLE)
    agent = None
    if r.get("inbound_agent_id") and ObjectId.is_valid(r["inbound_agent_id"]):
        agent = await db.agents.find_one({"_id": ObjectId(r["inbound_agent_id"]), "tenant_id": r["tenant_id"]})
    if not agent or await saas.quota_error(r["tenant_id"]):
        return _short(UNAVAILABLE)
    phone = (call.get("customer") or {}).get("number") or "oculto"
    lead = Lead(tenant_id=r["tenant_id"], agent_id=str(agent["_id"]), agent_name=agent["name"], name="Llamada entrante",
                phone=phone if phone.startswith("+") or phone == "oculto" else f"+{phone}", source="entrante",
                direction="entrante", status="en_curso")
    doc = lead.to_mongo()
    doc["vapi_call_id"] = call.get("id")
    doc["_id"] = (await db.leads.insert_one(doc)).inserted_id
    return {"assistant": vapi.build_assistant(agent, doc, S.today_text(agent.get("country", "ES")))}


# ---------- Tenant ----------
@router.get("/my-number")
async def my_number(user=CurrentUser):
    return _out(await record(user["id"]))


class InboundIn(BaseModel):
    inbound_agent_id: str = Field("", max_length=40)


@router.put("/my-number")
async def set_inbound(body: InboundIn, user=CurrentUser):
    if body.inbound_agent_id:
        a = await db.agents.find_one({"_id": ObjectId(body.inbound_agent_id) if ObjectId.is_valid(body.inbound_agent_id) else None,
                                      "tenant_id": user["id"]})
        if not a:
            raise HTTPException(404, "Agente no encontrado")
    res = await db.tenant_numbers.update_one({"tenant_id": user["id"]}, {"$set": {"inbound_agent_id": body.inbound_agent_id}})
    if not res.matched_count:
        raise HTTPException(400, "Aún no tienes un número asignado.")
    return _out(await record(user["id"]))


# ---------- Super admin ----------
class ZadarmaApiIn(BaseModel):
    key: str = Field("", max_length=100)
    secret: str = Field("", max_length=100)
    direction_es: str = Field("", max_length=20)
    direction_cl: str = Field("", max_length=20)
    docs_es: str = Field("", max_length=40)
    docs_cl: str = Field("", max_length=40)
    buy_on_test: bool = False


@router.get("/admin/zadarma")
async def zadarma_status(user=Depends(X.require_admin)):
    c = await Z.creds()
    bal = None
    if c.get("key"):
        try:
            b = await Z.balance()
            bal = f"{b['balance']} {b['currency']}"
        except Z.ZadarmaError as e:
            bal = str(e)
    return {"connected": bool(c.get("key")), "key_last4": (c.get("key") or "")[-4:], "balance": bal,
            **{k: c.get(k, "") for k in ("direction_es", "direction_cl", "docs_es", "docs_cl")},
            "buy_on_test": bool(c.get("buy_on_test"))}


@router.put("/admin/zadarma")
async def zadarma_save(body: ZadarmaApiIn, user=Depends(X.require_admin)):
    upd = body.model_dump()
    if body.key:
        try:
            await Z.balance(body.key.strip(), body.secret.strip())
        except Z.ZadarmaError as e:
            raise HTTPException(400, f"Clave de Zadarma no válida. {e}")
        upd["key"], upd["secret"] = body.key.strip(), body.secret.strip()
    else:
        upd.pop("key"), upd.pop("secret")
    await db.platform_settings.update_one({"_id": "zadarma_api"}, {"$set": {**upd, "updated_at": now_iso()}}, upsert=True)
    return await zadarma_status(user)


@router.delete("/admin/zadarma")
async def zadarma_disconnect(user=Depends(X.require_admin)):
    await db.platform_settings.update_one({"_id": "zadarma_api"}, {"$unset": {"key": "", "secret": ""}})
    return {"ok": True}


@router.get("/admin/zadarma/options")
async def zadarma_options(country: str, user=Depends(X.require_admin)):
    if country not in COUNTRIES:
        raise HTTPException(422, "País no válido")
    try:
        dirs, docs = await asyncio.gather(Z.directions(country), Z.document_groups())
    except Z.ZadarmaError as e:
        raise HTTPException(400, str(e))
    return {"directions": [{"id": str(d["id"]), "name": d.get("name"), "monthly_fee": d.get("monthly_fee"),
                            "connect_fee": d.get("connect_fee"), "currency": d.get("currency"),
                            "documents": bool(d.get("restrictions"))} for d in dirs],
            "document_groups": [{"id": str(g.get("id")), "name": g.get("name") or g.get("title") or str(g.get("id")),
                                 "status": g.get("status")} for g in docs]}


@router.get("/admin/numbers")
async def admin_numbers(user=Depends(X.require_admin)):
    out = []
    async for r in db.tenant_numbers.find({}).sort("updated_at", -1):
        u = await db.users.find_one({"_id": ObjectId(r["tenant_id"])}, {"email": 1, "business_name": 1})
        out.append({**_out(r), "email": (u or {}).get("email"), "business_name": (u or {}).get("business_name")})
    return out


@router.post("/admin/numbers/{user_id}/provision")
async def admin_provision(user_id: str, user=Depends(X.require_admin)):
    if not ObjectId.is_valid(user_id) or not await db.users.find_one({"_id": ObjectId(user_id)}):
        raise HTTPException(404, "Cliente no encontrado")
    if not (await Z.creds()).get("key"):
        raise HTTPException(400, "Conecta primero la API de Zadarma.")
    return await provision(user_id)


@router.post("/admin/numbers/{user_id}/release")
async def admin_release(user_id: str, user=Depends(X.require_admin)):
    return await release(user_id)


# ---------- Super admin: inbound on the platform numbers ----------
class PlatformInboundIn(BaseModel):
    country: str = Field(pattern="^(ES|CL)$")
    agent_id: str = Field(min_length=1, max_length=40)


@router.get("/admin/platform-inbound")
async def platform_inbound(user=Depends(X.require_admin)):
    out = []
    for c, n in vapi.STATE["numbers"].items():
        r = await db.tenant_numbers.find_one({"platform": True, "country": c}) or {}
        out.append({"country": c, "number": n.get("number"), "enabled": r.get("status") == "activo",
                    "agent_id": r.get("inbound_agent_id", ""), "sip_uri": vapi.inbound_sip_uri(n.get("number", "")),
                    "routed": r.get("routed", False)})
    return out


@router.put("/admin/platform-inbound")
async def platform_inbound_on(body: PlatformInboundIn, user=Depends(X.require_admin)):
    n = vapi.STATE["numbers"].get(body.country)
    if not n:
        raise HTTPException(400, "Conecta primero la línea de este país.")
    a = await db.agents.find_one({"_id": ObjectId(body.agent_id) if ObjectId.is_valid(body.agent_id) else None, "tenant_id": user["id"]})
    if not a:
        raise HTTPException(404, "Agente no encontrado")
    await vapi.enable_inbound(n["credential_id"], n["phone_number_id"])
    routed, note = False, ""
    if (await Z.creds()).get("key"):
        try:
            await Z.route_to(n["number"], vapi.inbound_sip_uri(n["number"]))
            routed = True
        except Z.ZadarmaError as e:
            note = str(e)[:200]
    await db.tenant_numbers.update_one({"platform": True, "country": body.country}, {"$set": {
        "tenant_id": user["id"], "number": n["number"], "phone_number_id": n["phone_number_id"], "credential_id": n["credential_id"],
        "status": "activo", "inbound_agent_id": body.agent_id, "routed": routed, "updated_at": now_iso()},
        "$setOnInsert": {"created_at": now_iso()}}, upsert=True)
    return {"ok": True, "routed": routed, "note": note, "sip_uri": vapi.inbound_sip_uri(n["number"])}


@router.delete("/admin/platform-inbound/{country}")
async def platform_inbound_off(country: str, user=Depends(X.require_admin)):
    await db.tenant_numbers.update_one({"platform": True, "country": country}, {"$set": {"status": "pausado"}})
    return {"ok": True}
