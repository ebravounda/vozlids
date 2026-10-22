"""Super admin «Líneas»: every Zadarma number in one table — connect, change agent, move, reconfigure, disconnect."""
import re
from datetime import date

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import extra_numbers as E
import kyc
import phone_numbers as N
import vapi
import zadarma as Z
from db import db
from extra_routes import require_admin
from models import now_iso

router = APIRouter(prefix="/api/admin/lines")
PREFIX = {"34": "ES", "56": "CL"}
OFF = {"off", "blocked", "disabled", "expired", "deleted", "inactive"}
ALIVE = {"status": {"$nin": ["liberado"]}}
LIVE = {**ALIVE, "number": {"$nin": [None, ""]}}


def norm(n) -> str:
    return "+" + re.sub(r"\D", "", str(n or ""))


def country_of(n: str) -> str:
    return PREFIX.get(norm(n)[1:3], "")


async def _zadarma():
    try:
        nums = await Z.my_numbers()
        sips, left = await Z.list_sips()
    except Z.ZadarmaError as e:
        raise HTTPException(424, str(e))
    return nums, sips, left


async def _platform_tenant(admin: dict) -> str:
    u = await db.users.find_one({"_id": ObjectId(admin["id"])}, {"client_id": 1})
    return (u or {}).get("client_id") or admin["id"]


async def _names(ids) -> dict:
    oids = [ObjectId(i) for i in ids if i and ObjectId.is_valid(i)]
    return {str(d["_id"]): d.get("business_name") or d.get("email") or d.get("name", "")
            async for d in db.users.find({"_id": {"$in": oids}}, {"business_name": 1, "email": 1})} | \
        {str(d["_id"]): d.get("name", "") async for d in db.agents.find({"_id": {"$in": oids}}, {"name": 1})}


def _role(r: dict) -> str:
    return "platform" if r.get("platform") else "agent" if r.get("extra") else "main"


@router.get("")
async def lines(user=Depends(require_admin)):
    nums, sips, left = await _zadarma()
    recs = {r["number"]: r async for r in db.tenant_numbers.find(LIVE)}
    names = await _names({r.get("tenant_id") for r in recs.values()} | {r.get("agent_id") or r.get("inbound_agent_id") for r in recs.values()})
    kyc_ok = {t: await kyc.group_for(t) is not None for t in {r.get("tenant_id") for r in recs.values() if not r.get("platform")}}
    sip_of = {str(r.get("sip_id")): n for n, r in recs.items() if r.get("sip_id")}
    out, seen = [], set()
    for z in nums:
        n = norm(z.get("number"))
        seen.add(n)
        stop = str(z.get("stop_date") or "")[:10]
        usable = str(z.get("status", "")).lower() not in OFF and (not stop or stop >= date.today().isoformat())
        r = recs.get(n)
        row = {"number": n, "country": country_of(n), "description": z.get("description") or z.get("number_name") or "",
               "stop_date": stop, "usable": usable, "connected": bool(r)}
        if r:
            agent = r.get("agent_id") if r.get("extra") else r.get("inbound_agent_id")
            row.update({"role": _role(r), "tenant_id": r.get("tenant_id"), "owner": names.get(r.get("tenant_id"), ""),
                        "agent_id": agent or "", "agent": names.get(agent, ""), "sip_id": str(r.get("sip_id") or ""),
                        "status": r.get("status"), "error": r.get("error", ""), "billing": r.get("billing") or ("stripe" if r.get("stripe_item_id") else ""),
                        "ok_in": r.get("status") == "activo" and bool(r.get("credential_id")) and r.get("routed", True) is not False and r.get("health") != "caida",
                        "ok_out": r.get("status") == "activo" and bool(r.get("phone_number_id")) and r.get("health") != "caida",
                        "health_reason": r.get("health_reason", "") if r.get("health") == "caida" else "", "health_at": r.get("health_at", ""),
                        "ok_docs": bool(r.get("platform")) or kyc_ok.get(r.get("tenant_id"), False)})
        out.append(row)
    orphans = [{"number": n, "owner": names.get(r.get("tenant_id"), ""), "status": r.get("status")} for n, r in recs.items() if n not in seen]
    return {"lines": out, "orphans": orphans, "sips_left": left,
            "sips": [{"id": str(s["id"]), "name": s.get("display_name", ""), "used_by": sip_of.get(str(s["id"]), "")} for s in sips]}


@router.get("/options")
async def options(user=Depends(require_admin)):
    taken = {r["agent_id"] async for r in db.tenant_numbers.find({"extra": True, **LIVE}, {"agent_id": 1})}
    plat = await _platform_tenant(user)
    owners = []
    async for u in db.users.find({"admin_only": {"$ne": True}}, {"business_name": 1, "email": 1, "country": 1, "role": 1,
                                                                 "stripe_subscription_id": 1, "billing_status": 1}).sort("business_name", 1):
        tid = str(u["_id"])
        main = await N.record(tid)
        owners.append({"id": tid, "name": u.get("business_name") or u["email"], "country": u.get("country", "ES"),
                       "kyc_ok": u.get("role") == "admin" or await kyc.group_for(tid) is not None,
                       "can_charge": bool(u.get("stripe_subscription_id")) and u.get("billing_status") == "active",
                       "price": E.price_label(u.get("country", "ES")), "is_platform_owner": tid == plat,
                       "main_number": (main or {}).get("number", "") if main and main.get("status") not in ("liberado", None) else "",
                       "agents": [{"id": str(a["_id"]), "name": a["name"], "has_own": str(a["_id"]) in taken}
                                  async for a in db.agents.find({"tenant_id": tid}, {"name": 1})]})
    return {"owners": owners, "platform_tenant": plat}


class ConnectIn(BaseModel):
    number: str = Field(min_length=6, max_length=20)
    tenant_id: str
    role: str = Field(pattern="^(main|agent|platform)$")
    agent_id: str = ""
    sip_id: str = Field(min_length=1, max_length=20)
    charge: bool = False


async def _wire(number: str, sip_id: str, label: str) -> dict:
    pwd = Z.new_password()
    if sip_id == "new":
        sip = await N._step("crear la línea SIP en Zadarma", Z.create_sip(f"VozLeads {label}", pwd, number))
    else:
        await N._step(f"preparar tu línea SIP {sip_id} en Zadarma", Z.reuse_sip(sip_id, pwd, number))
        sip = sip_id
    v = await N._step("conectar la línea con la IA (Vapi)", vapi.connect_tenant_number(sip, pwd, number, label))
    await N._step("desviar el número a la recepcionista en Zadarma", Z.route_to(number, v["inbound_uri"]))
    return {"sip_id": str(sip), **v, "routed": True}


async def _unwire(r: dict) -> None:
    for path in (f"/phone-number/{r.get('phone_number_id')}", f"/phone-number/{r.get('inbound_phone_number_id')}",
                 f"/credential/{r.get('credential_id')}"):
        if "None" not in path and path.split("/")[-1]:
            try:
                await vapi.delete(path)
            except Exception:  # noqa: BLE001 — already gone in Vapi
                pass


def _platform_state(country: str, rec: dict | None) -> None:
    if rec:
        vapi.STATE["numbers"][country] = {k: rec[k] for k in ("number", "phone_number_id", "credential_id")}
    else:
        vapi.STATE["numbers"].pop(country, None)


async def _save_platform(country: str, rec: dict | None) -> None:
    _platform_state(country, rec)
    key = f"numbers.{country}"
    if rec:
        await db.platform_settings.update_one({"_id": "telephony"}, {"$set": {key: {**{k: rec[k] for k in ("number", "phone_number_id", "credential_id")}, "updated_at": now_iso()}}}, upsert=True)
    else:
        await db.platform_settings.update_one({"_id": "telephony"}, {"$unset": {key: ""}})


async def _check_free(number: str, sip_id: str, sips: list, nums: list, skip_id=None) -> None:
    z = next((x for x in nums if norm(x.get("number")) == number), None)
    if not z:
        raise HTTPException(404, "Ese número no está en tu cuenta de Zadarma.")
    other = await db.tenant_numbers.find_one({"number": number, **ALIVE, **({"_id": {"$ne": skip_id}} if skip_id else {})})
    if other:
        raise HTTPException(409, "Ese número ya está conectado. Usa «Mover» o «Reconfigurar».")
    if sip_id != "new":
        if sip_id not in {str(s["id"]) for s in sips}:
            raise HTTPException(409, f"La línea SIP {sip_id} no existe en tu Zadarma.")
        used = await db.tenant_numbers.find_one({"sip_id": sip_id, **ALIVE, **({"_id": {"$ne": skip_id}} if skip_id else {})})
        if used:
            raise HTTPException(409, f"La línea SIP {sip_id} ya la usa el número {used['number']}.")


async def _connect(body: ConnectIn, admin: dict, keep: dict | None = None) -> dict:
    number = norm(body.number)
    nums, sips, left = await _zadarma()
    await _check_free(number, body.sip_id, sips, nums, keep and keep["_id"])
    if body.sip_id == "new" and left <= 0:
        raise HTTPException(409, "Zadarma no deja crear más líneas SIP. Elige una de tus líneas existentes o recarga saldo en Zadarma.")
    u = await db.users.find_one({"_id": ObjectId(body.tenant_id)}) if ObjectId.is_valid(body.tenant_id) else None
    if not u:
        raise HTTPException(404, "Cliente no encontrado")
    tid, country = body.tenant_id, country_of(number) or u.get("country", "ES")
    if body.role != "platform" and u.get("role") != "admin" and await kyc.group_for(tid) is None:
        raise HTTPException(409, "Este cliente aún no tiene sus documentos aprobados. Revísalos en «Documentos de los titulares».")
    agent = await E._agent(tid, body.agent_id) if body.agent_id else None
    if body.role == "agent":
        if not agent:
            raise HTTPException(400, "Elige el agente.")
        if await db.tenant_numbers.find_one({"tenant_id": tid, "extra": True, "agent_id": body.agent_id, **LIVE, **({"_id": {"$ne": keep["_id"]}} if keep else {})}):
            raise HTTPException(409, f"{agent['name']} ya tiene un número propio.")
    if body.role == "main" and await db.tenant_numbers.find_one({"tenant_id": tid, **N.PRIMARY, **LIVE, **({"_id": {"$ne": keep["_id"]}} if keep else {})}):
        raise HTTPException(409, "Este cliente ya tiene número principal. Conéctalo a un agente o mueve el principal primero.")
    if body.role == "platform" and await db.tenant_numbers.find_one({"platform": True, "country": country, **LIVE, **({"_id": {"$ne": keep["_id"]}} if keep else {})}):
        raise HTTPException(409, f"Ya hay un número de plataforma en {country}. Desconéctalo o muévelo primero.")
    item = (keep or {}).get("stripe_item_id", "")
    if body.role == "agent" and body.charge and not item:
        item = await E._charge(u, u.get("country", "ES"))
    inbound = body.agent_id or await N._default_agent(tid, country)
    try:
        w = await _wire(number, body.sip_id, (u.get("business_name") or "")[:20])
    except (Z.ZadarmaError, vapi.VapiError) as e:
        if item and not keep:
            await E._uncharge(u, item, u.get("country", "ES"))
        raise HTTPException(424, f"No se pudo conectar: {str(e)[:300]} No se ha cobrado nada y el número sigue libre.")
    doc = {"tenant_id": tid, "number": number, "country": country, "status": "activo", "error": "", **w,
           "extra": body.role == "agent", "platform": body.role == "platform", "agent_id": body.agent_id if body.role == "agent" else "",
           "inbound_agent_id": inbound, "stripe_item_id": item, "billing": "stripe" if item else "manual",
           "source": "zadarma_existente", "activated_at": now_iso(), "updated_at": now_iso()}
    if keep:
        await db.tenant_numbers.update_one({"_id": keep["_id"]}, {"$set": doc})
    else:
        await db.tenant_numbers.insert_one({**doc, "created_at": now_iso()})
    if body.role == "platform":
        await _save_platform(country, doc)
    return {"ok": True, "number": number}


@router.post("/connect")
async def connect(body: ConnectIn, user=Depends(require_admin)):
    return await _connect(body, user)


async def _rec(number: str) -> dict:
    r = await db.tenant_numbers.find_one({"number": norm(number), **ALIVE})
    if not r:
        raise HTTPException(404, "Ese número no está conectado.")
    return r


class TestIn(BaseModel):
    phone: str = Field(min_length=9, max_length=20)


@router.post("/{number}/test")
async def test_line(number: str, body: TestIn, user=Depends(require_admin)):
    """The line's agent calls `phone` from this exact number."""
    import services as S
    from countries import norm_phone
    from models import Lead
    r = await _rec(number)
    if r.get("status") != "activo" or not r.get("phone_number_id"):
        raise HTTPException(409, "Esta línea no está activa: reconfigúrala primero.")
    aid = (r.get("agent_id") if r.get("extra") else r.get("inbound_agent_id")) or await N._default_agent(r["tenant_id"], country_of(r["number"]) or "ES")
    agent = await db.agents.find_one({"_id": ObjectId(aid)}) if aid and ObjectId.is_valid(aid) else None
    if not agent:
        raise HTTPException(409, "Esta línea no tiene agente: usa «Cambiar agente».")
    raw = body.phone.strip()
    try:
        phone = raw if raw.startswith("+") else norm_phone(raw, country_of(r["number"]) or agent.get("country", "ES"))
    except ValueError as e:
        raise HTTPException(400, str(e))
    lead = Lead(tenant_id=agent["tenant_id"], agent_id=aid, agent_name=agent["name"], name="Prueba de línea", phone=phone,
                is_test=True, source="prueba_linea", via_phone_id=r["phone_number_id"], line_number=r["number"])
    doc = lead.to_mongo()
    doc["_id"] = (await db.leads.insert_one(doc)).inserted_id
    await S.dial(agent, doc)
    out = await db.leads.find_one({"_id": doc["_id"]}, {"status": 1, "error": 1, "vapi_call_id": 1})
    if out.get("status") == "fallida":
        raise HTTPException(424, f"No se pudo llamar: {out.get('error') or 'error desconocido'}")
    return {"ok": True, "agent": agent["name"], "phone": phone}


class AgentIn(BaseModel):
    agent_id: str = Field(min_length=1, max_length=40)


@router.post("/{number}/agent")
async def change_agent(number: str, body: AgentIn, user=Depends(require_admin)):
    r = await _rec(number)
    a = await E._agent(r["tenant_id"], body.agent_id)
    if r.get("extra") and await db.tenant_numbers.find_one({"tenant_id": r["tenant_id"], "extra": True, "agent_id": body.agent_id, **LIVE, "_id": {"$ne": r["_id"]}}):
        raise HTTPException(409, f"{a['name']} ya tiene otro número propio.")
    await db.tenant_numbers.update_one({"_id": r["_id"]}, {"$set": {"inbound_agent_id": body.agent_id, "updated_at": now_iso(),
                                                                     **({"agent_id": body.agent_id} if r.get("extra") else {})}})
    return {"ok": True}


class SipIn(BaseModel):
    sip_id: str = Field(min_length=1, max_length=20)


@router.post("/{number}/reconfigure")
async def reconfigure(number: str, body: SipIn, user=Depends(require_admin)):
    r = await _rec(number)
    await _unwire(r)
    role = _role(r)
    await db.tenant_numbers.update_one({"_id": r["_id"]}, {"$set": {"status": "error", "error": "Reconfigurando…", "phone_number_id": None}})
    try:
        return await _connect(ConnectIn(number=r["number"], tenant_id=r["tenant_id"], role=role, sip_id=body.sip_id,
                                        agent_id=(r.get("agent_id") if role == "agent" else r.get("inbound_agent_id")) or ""), user, keep=r)
    except HTTPException as e:
        await db.tenant_numbers.update_one({"_id": r["_id"]}, {"$set": {"status": "error", "error": str(e.detail)[:300]}})
        raise


@router.post("/health-check")
async def health_check(user=Depends(require_admin)):
    import linehealth
    return await linehealth.check_once()


async def repair(only: set | None) -> dict:
    if not (await Z.creds()).get("key"):
        raise HTTPException(400, "Conecta Zadarma en Telefonía antes de reparar: sin Zadarma no se pueden ajustar los desvíos.")
    isolated = await vapi.isolate_inbound()
    out = []
    async for r in db.tenant_numbers.find({"status": "activo", "number": {"$nin": [None, ""]}}):
        if only and r["number"] not in only:
            continue
        try:
            v = await vapi.connect_inbound(r["number"])
            await Z.route_to(r["number"], v["inbound_uri"])
            await db.tenant_numbers.update_one({"_id": r["_id"]}, {"$set": {**v, "routed": True, "updated_at": now_iso()}})
            out.append({"number": r["number"], "ok": True, "detail": "Llamadas entrantes reparadas"})
        except (vapi.VapiError, Z.ZadarmaError) as e:
            out.append({"number": r["number"], "ok": False, "detail": str(e)[:200]})
    cred = await vapi.inbound_credential()
    for p in await vapi._list("/phone-number"):
        legacy = p.get("provider") == "vapi" and (p.get("sipUri") or "").startswith("sip:vozleads-")
        if legacy or (p.get("credentialId") == cred and not str(p.get("number", "")).startswith("00")):
            await vapi.delete(f"/phone-number/{p['id']}")
    return {"isolated": isolated, "numbers": out}


@router.post("/repair-inbound")
async def repair_inbound(user=Depends(require_admin)):
    return await repair(None)


@router.post("/reconfigure-all")
async def reconfigure_all(user=Depends(require_admin)):
    out = []
    async for r in db.tenant_numbers.find(LIVE):
        if not r.get("sip_id"):
            out.append({"number": r["number"], "ok": False, "detail": "Sin línea SIP conocida: usa «Reconfigurar» y elige su línea."})
            continue
        try:
            await reconfigure(r["number"], SipIn(sip_id=str(r["sip_id"])), user)
            out.append({"number": r["number"], "ok": True, "detail": "Reconfigurado"})
        except HTTPException as e:
            out.append({"number": r["number"], "ok": False, "detail": str(e.detail)[:200]})
    return out


class MoveIn(BaseModel):
    tenant_id: str
    role: str = Field(pattern="^(main|agent|platform)$")
    agent_id: str = ""
    sip_id: str = Field(min_length=1, max_length=20)
    charge: bool = False


@router.post("/{number}/move")
async def move(number: str, body: MoveIn, user=Depends(require_admin)):
    r = await _rec(number)
    await disconnect(number, user)
    try:
        return await _connect(ConnectIn(number=r["number"], **body.model_dump()), user)
    except HTTPException as e:
        raise HTTPException(e.status_code, f"Se desconectó de su dueño anterior, pero no se pudo conectar al nuevo: {e.detail}")


@router.post("/{number}/disconnect")
async def disconnect(number: str, user=Depends(require_admin)):
    r = await _rec(number)
    await _unwire(r)
    if r.get("stripe_item_id"):
        tenant = await db.users.find_one({"_id": ObjectId(r["tenant_id"])}) or {}
        await E._uncharge(tenant, r["stripe_item_id"])
    await db.tenant_numbers.update_one({"_id": r["_id"]}, {"$set": {"status": "liberado", "released_at": now_iso(), "phone_number_id": None,
                                                                     "credential_id": None, "sip_id": None, "stripe_item_id": ""}})
    if r.get("platform"):
        await _save_platform(r.get("country") or country_of(r["number"]), None)
    return {"ok": True}
