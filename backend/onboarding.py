import logging
import os
import re
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import emailer
import extra_routes as X
import phone_numbers as N
import vapi
import zadarma as Z
from countries import COUNTRIES
from db import db
from models import now_iso

router = APIRouter(prefix="/api")
log = logging.getLogger("vozlead.onboarding")
DOCS = {"ES": ("DNI", "NIE", "Pasaporte"), "CL": ("RUT", "Pasaporte")}
LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"


def valid_doc(country: str, kind: str, num: str) -> str:
    n = re.sub(r"[\s.\-]", "", num).upper()
    if kind not in DOCS[country]:
        raise ValueError("Tipo de documento no válido para tu país")
    if kind == "DNI" and not (re.fullmatch(r"\d{8}[A-Z]", n) and LETTERS[int(n[:8]) % 23] == n[8]):
        raise ValueError("El DNI no es válido (8 números y la letra)")
    if kind == "NIE":
        if not re.fullmatch(r"[XYZ]\d{7}[A-Z]", n) or LETTERS[int("XYZ".index(n[0]).__str__() + n[1:8]) % 23] != n[8]:
            raise ValueError("El NIE no es válido (ej. X1234567L)")
    if kind == "RUT":
        if not re.fullmatch(r"\d{7,8}[0-9K]", n):
            raise ValueError("El RUT no es válido (ej. 12.345.678-5)")
        body, dv = n[:-1], n[-1]
        s = sum(int(d) * (2 + i % 6) for i, d in enumerate(reversed(body)))
        exp = {11: "0", 10: "K"}.get(11 - s % 11, str(11 - s % 11))
        if dv != exp:
            raise ValueError("El RUT no es válido: revisa el dígito verificador")
        n = f"{int(body):,}".replace(",", ".") + f"-{dv}"
    if kind == "Pasaporte" and not re.fullmatch(r"[A-Z0-9]{5,15}", n):
        raise ValueError("El pasaporte no es válido")
    return n


async def mark_pending(user_id: str) -> None:
    """After first payment: queue the account for manual number provisioning and alert the super admin."""
    cur = await N.record(user_id)
    if cur and cur.get("status") in ("activo", "pendiente", "comprando"):
        return
    await db.tenant_numbers.update_one({"tenant_id": user_id, "extra": {"$ne": True}}, {"$set": {"status": "pendiente", "error": "", "updated_at": now_iso()},
                                                                "$setOnInsert": {"created_at": now_iso()}}, upsert=True)
    u = await db.users.find_one({"_id": ObjectId(user_id)}) or {}
    import monitor
    await monitor.notify(f"alta_{user_id}", f"Nueva alta pagada: {u.get('business_name', '')}", [
        ("Cliente", f"{u.get('first_name', u.get('name', ''))} {u.get('last_name', '')}".strip()), ("Email", u.get("email", "")),
        ("País", COUNTRIES.get(u.get("country", "ES"), {}).get("name", "")), ("Web", u.get("website", "")),
        ("Qué hacer", "Compra el número en Zadarma, crea su SIP y asígnalo en Super admin → Altas pendientes")], every_hours=24 * 365)


class AssignIn(BaseModel):
    number: str = Field(min_length=6, max_length=20)
    sip_login: str = Field(min_length=3, max_length=40)
    sip_password: str = Field(min_length=4, max_length=80)


@router.get("/admin/onboarding")
async def pending(user=Depends(X.require_admin)):
    nums = {n["tenant_id"]: n async for n in db.tenant_numbers.find({"platform": {"$ne": True}, "extra": {"$ne": True}})}
    out = []
    async for u in db.users.find({"role": "business"}, {"password_hash": 0}).sort("created_at", -1):
        n = nums.get(str(u["_id"]), {})
        paid = u.get("billing_status") == "active"
        if not paid and not n:
            continue
        out.append({"id": str(u["_id"]), "email": u["email"], "business_name": u.get("business_name"),
                    "name": f"{u.get('first_name', u.get('name', ''))} {u.get('last_name', '')}".strip(),
                    "country": u.get("country", "ES"), "website": u.get("website", ""), "doc": f"{u.get('doc_type', '')} {u.get('doc_number', '')}".strip(),
                    "billing": u.get("billing_address") or {}, "billing_status": u.get("billing_status"), "test": bool(u.get("billing_test")), "created_at": u.get("created_at"),
                    "number": n.get("number"), "status": n.get("status") or "pendiente", "error": n.get("error", "")})
    return out


@router.post("/admin/onboarding/{uid}/assign")
async def assign(uid: str, body: AssignIn, user=Depends(X.require_admin)):
    u = await db.users.find_one({"_id": ObjectId(uid)}) if ObjectId.is_valid(uid) else None
    if not u:
        raise HTTPException(404, "Cliente no encontrado")
    number = "+" + re.sub(r"\D", "", body.number)
    cur = await N.record(uid) or {}
    if cur.get("phone_number_id"):
        for path in (f"/phone-number/{cur['phone_number_id']}", f"/credential/{cur.get('credential_id')}"):
            if "None" not in path:
                await vapi.delete(path)
    try:
        v = await vapi.connect_tenant_number(body.sip_login.strip(), body.sip_password, number, u.get("business_name") or u["email"])
    except vapi.VapiError as e:
        await db.tenant_numbers.update_one({"tenant_id": uid, "extra": {"$ne": True}}, {"$set": {"status": "error", "error": str(e)[:300], "number": number}}, upsert=True)
        raise HTTPException(400, f"No se pudo conectar la línea: {e}")
    uri = v["inbound_uri"]
    routed = ""
    if (await Z.creds()).get("key"):
        try:
            await Z.route_to(number, uri)
        except Z.ZadarmaError as e:
            routed = str(e)
    country = u.get("country", "ES")
    await db.tenant_numbers.update_one({"tenant_id": uid, "extra": {"$ne": True}}, {"$set": {
        "tenant_id": uid, "country": country, "number": number, "status": "activo", "error": "", "sip_id": body.sip_login.strip(),
        **v, "activated_at": now_iso(), "inbound_agent_id": cur.get("inbound_agent_id") or await N._default_agent(uid, country)},
        "$setOnInsert": {"created_at": now_iso()}}, upsert=True)
    await emailer.send(u["email"], "¡Felicidades! Tu línea de VozLeads ya está lista", "¡Felicidades, tu línea ya está lista!", [
        ("Tu número", number), ("Compártelo", "En tu web, Google Maps y redes sociales"),
        ("Quién contesta", "Tu recepcionista con IA, 24/7"), ("Llamadas salientes", "Tus agentes ya llaman a tus leads desde este número"),
        ("Siguiente paso", "Elige quién contesta y añade el botón «Solicitar llamada» a tu web")],
        os.environ["APP_PUBLIC_URL"] + "/app/numero",
        intro=f"Hola {u.get('first_name') or u.get('name', '')}, ya hemos configurado tu línea. Desde ahora cada llamada a tu negocio la atiende tu asistente con IA.",
        cta_label="Ver mi número")
    return {"ok": True, "number": number, "inbound_uri": uri, "route_error": routed}


@router.post("/admin/onboarding/{uid}/block")
async def block(uid: str, blocked: bool = True, user=Depends(X.require_admin)):
    cur = await N.record(uid)
    if not cur or cur.get("status") not in ("activo", "pausado"):
        raise HTTPException(400, "Este cliente no tiene una línea activa.")
    await db.tenant_numbers.update_one({"tenant_id": uid, "extra": {"$ne": True}}, {"$set": {"status": "pausado" if blocked else "activo", "updated_at": now_iso()}})
    return {"ok": True, "status": "pausado" if blocked else "activo"}
