"""Identity verification (KYC) of each tenant: their data and ID photos register their Zadarma lines in their name."""
import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal
from bson import ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
import emailer
import storage
import zadarma as Z
from db import db
from extra_routes import CurrentUser, require_admin
from models import now_iso

log = logging.getLogger("vozlead.kyc")
router = APIRouter(prefix="/api")
GRACE_DAYS = 30
MAX_BYTES = 8 * 1024 * 1024
MIMES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "application/pdf": "pdf"}
FILE_TYPES = ("id_front", "id_back", "passport", "company_cert")
ZADARMA_TYPE = {"id_front": "passport", "id_back": "passport", "passport": "passport", "company_cert": "certificate"}
LOCKED = ("pendiente", "enviado_zadarma", "verificado")
NOTICE = {
    "ES": "En España, la Ley 11/2022 General de Telecomunicaciones obliga a identificar al titular de cada número de teléfono. "
          "Necesitamos tu DNI o NIE por las dos caras (o tu pasaporte) y una dirección en España. Si contratas como empresa, "
          "también el CIF y un certificado de la empresa. Tus datos se usan solo para dar de alta tus líneas a tu nombre.",
    "CL": "En Chile, la Ley General de Telecomunicaciones (Ley 18.168) y la normativa de la Subtel exigen identificar al titular "
          "de cada línea. Necesitamos tu cédula de identidad por ambas caras (o tu pasaporte), tu RUT y una dirección en Chile. "
          "Si contratas como empresa, también el RUT de la empresa y su certificado de vigencia o e-RUT.",
}
ID_TYPES = {"ES": ["DNI", "NIE", "PASSPORT"], "CL": ["NATIONAL_ID_CARD", "PASSPORT"]}


def required_files(doc: dict) -> list:
    base = ["passport"] if doc.get("id_type") == "PASSPORT" else ["id_front", "id_back"]
    return base + (["company_cert"] if doc.get("kind") == "empresa" else [])


async def _needs(user: dict) -> bool:
    if user.get("role") == "admin":
        return False
    return user.get("billing_status") == "active" or bool(await db.tenant_numbers.find_one({"tenant_id": user["id"], "platform": {"$ne": True}}))


def _out(doc: dict, needed: bool) -> dict:
    files = [{"type": f["type"], "name": f["name"], "index": i} for i, f in enumerate(doc.get("files", []))]
    keep = ("kind", "first_name", "last_name", "nationality", "id_type", "id_number", "email", "phone", "city", "zip_code",
            "street", "building_number", "organization", "organization_reg_number", "status", "reject_reason", "deadline",
            "submitted_at", "verified_at", "zadarma_status")
    return {**{k: doc.get(k, "") for k in keep}, "status": doc.get("status") or "sin_enviar", "files": files,
            "required": needed, "required_files": required_files(doc)}


async def get_doc(tid: str) -> dict:
    return await db.kyc.find_one({"tenant_id": tid}) or {}


@router.get("/kyc")
async def my_kyc(user=CurrentUser):
    doc = await get_doc(user["id"])
    needed = await _needs(user)
    if needed and not doc:
        has_line = await db.tenant_numbers.find_one({"tenant_id": user["id"], "status": "activo"})
        doc = {"tenant_id": user["id"], "status": "sin_enviar", "files": [], "created_at": now_iso(), "country": user.get("country", "ES"),
               "deadline": (datetime.now(timezone.utc) + timedelta(days=GRACE_DAYS)).isoformat() if has_line else ""}
        await db.kyc.insert_one(doc)
    country = doc.get("country") or user.get("country", "ES")
    return {**_out(doc, needed), "country": country, "notice": NOTICE.get(country, NOTICE["ES"]), "id_types": ID_TYPES.get(country, ID_TYPES["ES"])}


class KycIn(BaseModel):
    kind: Literal["persona", "empresa"]
    first_name: str = Field(min_length=1, max_length=60)
    last_name: str = Field(min_length=1, max_length=80)
    nationality: str = Field(pattern=r"^[A-Z]{2}$")
    id_type: Literal["DNI", "NIE", "PASSPORT", "NATIONAL_ID_CARD"]
    id_number: str = Field(min_length=4, max_length=30)
    email: str = Field(min_length=5, max_length=120)
    phone: str = Field(min_length=6, max_length=20)
    city: str = Field(min_length=2, max_length=80)
    zip_code: str = Field("", max_length=12)
    street: str = Field(min_length=2, max_length=120)
    building_number: str = Field(min_length=1, max_length=12)
    organization: str = Field("", max_length=120)
    organization_reg_number: str = Field("", max_length=30)


def _editable(doc: dict):
    if doc.get("status") in LOCKED:
        raise HTTPException(409, "Tus documentos ya están enviados. Si necesitas cambiar algo, escríbenos.")


@router.put("/kyc")
async def save_kyc(body: KycIn, user=CurrentUser):
    doc = await get_doc(user["id"])
    _editable(doc)
    if body.kind == "empresa" and (not body.organization or not body.organization_reg_number):
        raise HTTPException(422, "Indica el nombre de la empresa y su RUT o CIF.")
    await db.kyc.update_one({"tenant_id": user["id"]}, {"$set": {**body.model_dump(), "country": user.get("country", "ES"),
                                                                 "updated_at": now_iso()},
                                                        "$setOnInsert": {"files": [], "status": "sin_enviar", "created_at": now_iso()}},
                            upsert=True)
    return await my_kyc(user)


@router.post("/kyc/files")
async def upload_kyc_file(type: str, file: UploadFile = File(...), user=CurrentUser):
    if type not in FILE_TYPES:
        raise HTTPException(422, "Tipo de documento no válido")
    doc = await get_doc(user["id"])
    _editable(doc)
    data = await file.read()
    if file.content_type not in MIMES:
        raise HTTPException(422, "Sube una foto (JPG o PNG) o un PDF.")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "El archivo pesa más de 8 MB.")
    path = f"{storage.APP_NAME}/kyc/{user['id']}/{uuid.uuid4().hex}.{MIMES[file.content_type]}"
    await asyncio.to_thread(storage.put_object, path, data, file.content_type)
    item = {"type": type, "path": path, "name": (file.filename or type)[:80], "mime": file.content_type, "uploaded_at": now_iso()}
    files = [f for f in doc.get("files", []) if f["type"] != type] + [item]
    await db.kyc.update_one({"tenant_id": user["id"]}, {"$set": {"files": files, "updated_at": now_iso()},
                                                        "$setOnInsert": {"status": "sin_enviar", "created_at": now_iso()}}, upsert=True)
    return await my_kyc(user)


async def _file(tid: str, index: int) -> Response:
    files = (await get_doc(tid)).get("files", [])
    if not 0 <= index < len(files):
        raise HTTPException(404, "Documento no encontrado")
    f = files[index]
    data = await asyncio.to_thread(storage.get_object, f["path"])
    return Response(data, media_type=f["mime"], headers={"Cache-Control": "private, no-store"})


@router.get("/kyc/files/{index}")
async def my_kyc_file(index: int, user=CurrentUser):
    return await _file(user["id"], index)


@router.post("/kyc/submit")
async def submit_kyc(user=CurrentUser):
    doc = await get_doc(user["id"])
    _editable(doc)
    if not doc.get("first_name"):
        raise HTTPException(422, "Completa y guarda tus datos antes de enviar.")
    have = {f["type"] for f in doc.get("files", [])}
    missing = [t for t in required_files(doc) if t not in have]
    if missing:
        raise HTTPException(422, "Faltan fotos de tus documentos: " + ", ".join(LABEL[t] for t in missing) + ".")
    await db.kyc.update_one({"_id": doc["_id"]}, {"$set": {"status": "pendiente", "submitted_at": now_iso(), "reject_reason": ""}})
    admin = await db.users.find_one({"role": "admin"}, {"email": 1})
    if admin:
        await emailer.send(admin["email"], "Documentos de un cliente por revisar", "Nueva verificación de identidad", [
            ("Cliente", user.get("business_name") or user["email"]), ("País", doc.get("country", "")),
            ("Titular", f"{doc['first_name']} {doc['last_name']}" + (f" · {doc['organization']}" if doc.get("kind") == "empresa" else ""))],
            os.environ["APP_PUBLIC_URL"] + "/app/admin")
    return await my_kyc(user)


LABEL = {"id_front": "documento (cara delantera)", "id_back": "documento (cara trasera)", "passport": "pasaporte",
         "company_cert": "certificado de la empresa"}


# ---------- Super admin ----------
@router.get("/admin/kyc")
async def admin_kyc_list(user=Depends(require_admin)):
    rows = await db.kyc.find({}, {"files.path": 0}).sort("submitted_at", -1).to_list(500)
    users = {str(u["_id"]): u async for u in db.users.find({"_id": {"$in": [ObjectId(r["tenant_id"]) for r in rows]}},
                                                         {"business_name": 1, "email": 1})}
    now = datetime.now(timezone.utc).isoformat()
    out = []
    for r in rows:
        u = users.get(r["tenant_id"], {})
        out.append({**_out(r, True), "tenant_id": r["tenant_id"], "country": r.get("country", "ES"),
                    "business": u.get("business_name") or u.get("email", ""), "account_email": u.get("email", ""),
                    "overdue": bool(r.get("deadline")) and r.get("status") in ("sin_enviar", "rechazado") and r["deadline"] < now})
    return out


@router.get("/admin/kyc/{tid}/files/{index}")
async def admin_kyc_file(tid: str, index: int, user=Depends(require_admin)):
    return await _file(tid, index)


async def _admin_doc(tid: str) -> dict:
    doc = await get_doc(tid)
    if not doc:
        raise HTTPException(404, "Verificación no encontrada")
    return doc


def _group_payload(doc: dict) -> dict:
    company = doc.get("kind") == "empresa"
    return {"email": doc["email"], "salutation": "COMPANY" if company else "MR", "nationality": doc["nationality"],
            "first_name": doc["first_name"], "last_name": doc["last_name"], "country": doc.get("country", "ES"),
            "city": doc["city"], "zip_code": doc.get("zip_code", ""), "street": doc["street"], "building_number": doc["building_number"],
            "address": f"{doc['street']} {doc['building_number']}, {doc.get('zip_code', '')} {doc['city']}".strip(),
            "phone": doc["phone"].lstrip("+"), "type_of_id": doc["id_type"], "id_number": doc["id_number"],
            **({"organization": doc["organization"], "organization_reg_number": doc["organization_reg_number"]} if company else {})}


@router.post("/admin/kyc/{tid}/approve")
async def admin_kyc_approve(tid: str, user=Depends(require_admin)):
    doc = await _admin_doc(tid)
    if doc.get("status") not in ("pendiente", "error"):
        raise HTTPException(409, "Esta verificación no está pendiente de revisión.")
    try:
        gid = doc.get("zadarma_group_id") or await Z.create_group(_group_payload(doc))
        await db.kyc.update_one({"_id": doc["_id"]}, {"$set": {"zadarma_group_id": gid}})
        for f in [x for x in doc.get("files", []) if x["type"] in required_files(doc)]:
            data = await asyncio.to_thread(storage.get_object, f["path"])
            await Z.upload_doc(gid, ZADARMA_TYPE[f["type"]], data, f["name"], f["mime"])
    except Z.ZadarmaError as e:
        await db.kyc.update_one({"_id": doc["_id"]}, {"$set": {"status": "error", "zadarma_status": str(e)[:300]}})
        raise HTTPException(424, str(e))
    await db.kyc.update_one({"_id": doc["_id"]}, {"$set": {"status": "enviado_zadarma", "approved_at": now_iso(), "zadarma_status": ""}})
    u = await db.users.find_one({"_id": ObjectId(tid)}, {"email": 1})
    await emailer.send((u or {}).get("email", ""), "Tus documentos están aprobados", "Documentación aprobada", [
        ("Estado", "Enviada al operador para dar de alta tus líneas a tu nombre"),
        ("Siguiente paso", "Te avisaremos cuando tu número esté activo")], os.environ["APP_PUBLIC_URL"] + "/app/numero")
    import phone_numbers as N
    for r in await db.tenant_numbers.find({"tenant_id": tid, "status": "pendiente_documentos"}).to_list(20):
        await db.tenant_numbers.update_one({"_id": r["_id"]}, {"$set": {"status": "pendiente"}})
        asyncio.create_task(N.provision(tid, r["_id"] if r.get("extra") else None))
    return {"ok": True}


class RejectIn(BaseModel):
    reason: str = Field(min_length=3, max_length=400)


@router.post("/admin/kyc/{tid}/reject")
async def admin_kyc_reject(tid: str, body: RejectIn, user=Depends(require_admin)):
    doc = await _admin_doc(tid)
    await db.kyc.update_one({"_id": doc["_id"]}, {"$set": {"status": "rechazado", "reject_reason": body.reason, "rejected_at": now_iso()}})
    u = await db.users.find_one({"_id": ObjectId(tid)}, {"email": 1})
    await emailer.send((u or {}).get("email", ""), "Revisa tus documentos", "Necesitamos que corrijas tus documentos", [
        ("Motivo", body.reason), ("Qué hacer", "Entra en «Mi número», corrige los datos o las fotos y vuelve a enviarlos")],
        os.environ["APP_PUBLIC_URL"] + "/app/numero")
    return {"ok": True}


@router.post("/admin/kyc/{tid}/check")
async def admin_kyc_check(tid: str, user=Depends(require_admin)):
    doc = await _admin_doc(tid)
    if not doc.get("zadarma_group_id"):
        raise HTTPException(409, "Aún no se ha enviado a Zadarma.")
    cfg = await Z.creds()
    direction = cfg.get(f"direction_{doc.get('country', 'ES').lower()}", "")
    try:
        v = await Z.group_valid(doc["zadarma_group_id"], direction)
    except Z.ZadarmaError as e:
        raise HTTPException(424, str(e))
    ok = all(str(v.get(k)).lower() == "true" for k in ("is_information_match", "is_documents_uploaded", "is_documents_verified"))
    labels = {"is_information_match": "datos", "is_documents_uploaded": "documentos subidos", "is_documents_verified": "documentos verificados",
              "is_address_match": "dirección"}
    summary = ", ".join(f"{l}: {'sí' if str(v.get(k)).lower() == 'true' else 'no'}" for k, l in labels.items() if k in v)
    await db.kyc.update_one({"_id": doc["_id"]}, {"$set": {"zadarma_status": summary, **({"status": "verificado", "verified_at": now_iso()} if ok else {})}})
    return {"verified": ok, "summary": summary}


async def group_for(tid: str) -> str | None:
    """Zadarma documents group of the tenant once approved; None when the tenant still has to upload or be reviewed."""
    doc = await get_doc(tid)
    return doc.get("zadarma_group_id") if doc.get("status") in ("enviado_zadarma", "verificado") else None
