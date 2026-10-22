"""Super admin: connect numbers already owned in the platform's Zadarma account to a client (main line or one agent)."""
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

router = APIRouter(prefix="/api/admin/zadarma")
PREFIX = {"34": "ES", "56": "CL"}


def _norm(n) -> str:
    return "+" + re.sub(r"\D", "", str(n or ""))


async def _in_use() -> dict:
    used = {r["number"]: r["tenant_id"] async for r in db.tenant_numbers.find(
        {"number": {"$nin": [None, ""]}, "status": {"$in": E.OPEN},
         "$nor": [{"status": "error", "source": "zadarma_existente"}]}, {"number": 1, "tenant_id": 1})}
    plat = (await db.platform_settings.find_one({"_id": "platform_inbound"}) or {}).get("number")
    if plat:
        used[_norm(plat)] = "plataforma"
    return used


OFF = {"off", "blocked", "disabled", "expired", "deleted", "inactive"}


def _usable(r: dict) -> bool:
    if str(r.get("status", "")).lower() in OFF:
        return False
    stop = str(r.get("stop_date") or "")[:10]
    return not stop or stop >= date.today().isoformat()


async def _free() -> tuple[list, int]:
    try:
        rows = await Z.my_numbers()
    except Z.ZadarmaError as e:
        raise HTTPException(424, str(e))
    used = await _in_use()
    free = [r for r in rows if _usable(r) and _norm(r.get("number")) not in used]
    return free, len(rows) - len(free)


async def _sip_room() -> dict:
    try:
        sips, left = await Z.list_sips()
    except Z.ZadarmaError:
        return {}
    used = {str(r.get("sip_id")) async for r in db.tenant_numbers.find({"sip_id": {"$nin": [None, ""]}, "status": {"$nin": ["liberado"]}}, {"sip_id": 1})}
    reusable = sum(1 for s in sips if str(s.get("display_name", "")).startswith("VozLeads") and str(s["id"]) not in used)
    return {"sips": len(sips), "sips_left": left, "sips_reusable": reusable}


@router.get("/my-numbers")
async def my_numbers(user=Depends(require_admin)):
    """Only numbers that are active in Zadarma, not expired and not used by any VozLeads account."""
    free, hidden = await _free()
    return {"hidden": hidden, **await _sip_room(), "numbers": [
        {"number": _norm(r.get("number")), "country": PREFIX.get(_norm(r.get("number"))[1:3], ""),
         "description": r.get("description") or r.get("number_name") or "", "stop_date": str(r.get("stop_date") or "")[:10]}
        for r in free]}


@router.get("/connect-options/{tid}")
async def connect_options(tid: str, user=Depends(require_admin)):
    u = await db.users.find_one({"_id": ObjectId(tid)}) if ObjectId.is_valid(tid) else None
    if not u:
        raise HTTPException(404, "Cliente no encontrado")
    main = await N.record(tid)
    nums = [{"number": r.get("number"), "agent": r.get("agent_id", ""), "extra": bool(r.get("extra"))}
            async for r in db.tenant_numbers.find({"tenant_id": tid, "status": "activo"}, {"number": 1, "agent_id": 1, "extra": 1})]
    taken = {n["agent"] for n in nums if n["extra"]}
    return {"kyc_ok": u.get("role") == "admin" or await kyc.group_for(tid) is not None, "numbers": nums,
            "can_charge": bool(u.get("stripe_subscription_id")) and u.get("billing_status") == "active", "has_main": bool(main and main.get("status") == "activo"),
            "main_number": (main or {}).get("number") if main and main.get("status") == "activo" else "",
            "price": E.price_label(u.get("country", "ES")),
            "agents": [{"id": str(a["_id"]), "name": a["name"], "role": a.get("role", "")}
                       async for a in db.agents.find({"tenant_id": tid}, {"name": 1, "role": 1}) if str(a["_id"]) not in taken]}


class ConnectIn(BaseModel):
    number: str = Field(min_length=6, max_length=20)
    tenant_id: str
    agent_id: str = ""
    charge: bool = True


@router.post("/connect")
async def connect(body: ConnectIn, user=Depends(require_admin)):
    number = _norm(body.number)
    u = await db.users.find_one({"_id": ObjectId(body.tenant_id)}) if ObjectId.is_valid(body.tenant_id) else None
    if not u:
        raise HTTPException(404, "Cliente no encontrado")
    if u.get("role") != "admin" and await kyc.group_for(body.tenant_id) is None:
        raise HTTPException(409, "Este cliente aún no tiene sus documentos de identidad aprobados. Revísalos en «Documentos de los titulares».")
    free, _ = await _free()
    if number not in {_norm(r.get("number")) for r in free}:
        raise HTTPException(409, "Ese número ya no está disponible (en uso, vencido o inactivo en Zadarma). Actualiza la lista.")
    room = await _sip_room()
    if room and room["sips_left"] + room["sips_reusable"] <= 0:
        raise HTTPException(409, "Tu cuenta de Zadarma llegó al límite de líneas SIP. Recarga saldo en Zadarma (el límite sube con el saldo) "
                                 "o pide a su soporte que lo amplíe, y vuelve a intentarlo. No se ha cobrado nada.")
    country = PREFIX.get(number[1:3], u.get("country", "ES"))
    tid = body.tenant_id
    if body.agent_id:
        agent = await E._agent(tid, body.agent_id)
        if await db.tenant_numbers.find_one({"tenant_id": tid, "extra": True, "agent_id": body.agent_id, "status": {"$in": E.OPEN}}):
            raise HTTPException(409, f"{agent['name']} ya tiene un número propio.")
        bill = u.get("country", "ES")
        item = await E._charge(u, bill) if body.charge else ""
        res = await db.tenant_numbers.insert_one({"tenant_id": tid, "extra": True, "agent_id": body.agent_id, "country": bill if item else country,
                                                  "number": number, "status": "comprando", "stripe_item_id": item,
                                                  "created_at": now_iso(), "updated_at": now_iso(), "source": "zadarma_existente",
                                                  "billing": "stripe" if item else "manual"})
        filt, inbound = {"_id": res.inserted_id}, body.agent_id
    else:
        main = await N.record(tid)
        if main and main.get("status") == "activo":
            raise HTTPException(409, f"Este cliente ya tiene su número principal ({main.get('number')}). Elige un agente para conectarlo como adicional.")
        filt = {"_id": main["_id"]} if main else {"tenant_id": tid, **N.PRIMARY}
        await db.tenant_numbers.update_one(filt, {"$set": {"tenant_id": tid, "country": country, "number": number, "status": "comprando",
                                                           "error": "", "updated_at": now_iso(), "source": "zadarma_existente"},
                                                  "$setOnInsert": {"created_at": now_iso()}}, upsert=True)
        filt = {"_id": (await db.tenant_numbers.find_one(filt))["_id"]}
        inbound = (main or {}).get("inbound_agent_id") or await N._default_agent(tid, country)
    try:
        await N.activate(filt, u, number, inbound)
    except (Z.ZadarmaError, vapi.VapiError) as e:
        # Undo so the number is free again and nothing stays charged.
        if body.agent_id:
            await db.tenant_numbers.delete_one(filt)
            await E._uncharge(u, item, u.get("country", "ES") if item else "")
        else:
            await db.tenant_numbers.update_one(filt, {"$set": {"status": "error", "number": "", "error": str(e)[:300]}})
        raise HTTPException(424, f"No se pudo conectar: {str(e)[:300]} No se ha cobrado nada y el número sigue disponible.")
    return {"ok": True, "number": number, "extra": bool(body.agent_id)}
