import asyncio
import uuid
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from bson import ObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
import ambience
import auth as A
import services as S
import storage
import vapi
from db import db
from models import now_iso

router = APIRouter(prefix="/api")
CurrentUser = Depends(A.get_current_user)
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
DEFAULT_PRICING = {"line_rate_usd_min": 0.025, "line_rate_cl_usd_min": 0.05, "usd_eur": 0.92, "usd_clp": 950,
                   "margin_pct": 150, "voice_11labs_usd_min": 0.036, "voice_cartesia_usd_min": 0.022,
                   "voice_azure_usd_min": 0.011}
_custom_cache: "OrderedDict[str, object]" = OrderedDict()


async def require_admin(user=CurrentUser) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(403, "Solo para el administrador de la plataforma")
    return user


def ambience_out(d: dict) -> dict:
    return {"id": d["token"], "name": d["name"], "duration": d.get("duration"), "shared": d.get("shared", False),
            "created_at": d["created_at"]}


async def custom_ambience_allowed(tenant_id: str, token: str) -> bool:
    return bool(await db.ambience_files.find_one({"token": token, "is_deleted": False,
                                                 "$or": [{"tenant_id": tenant_id}, {"shared": True}]}))


# ---------- Custom ambience recordings ----------
@router.get("/ambiences/custom")
async def list_custom(user=CurrentUser):
    docs = await db.ambience_files.find({"is_deleted": False, "$or": [{"tenant_id": user["id"]}, {"shared": True}]}) \
        .sort("created_at", -1).to_list(100)
    return [ambience_out(d) for d in docs]


@router.post("/ambiences/custom")
async def upload_custom(name: str = Form(..., min_length=1, max_length=60), file: UploadFile = File(...),
                        user=CurrentUser):
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "El archivo supera 25 MB.")
    try:
        x = await asyncio.to_thread(ambience.decode, data)
    except ValueError as e:
        raise HTTPException(422, str(e))
    duration = len(x) / ambience.SR
    if duration < 10:
        raise HTTPException(422, "La grabación debe durar al menos 10 segundos.")
    wav = await asyncio.to_thread(ambience.to_wav, ambience.clean(x), 100, 0.95)
    token = uuid.uuid4().hex
    res = await asyncio.to_thread(storage.put_object, f"{storage.APP_NAME}/ambience/{user['id']}/{token}.wav", wav,
                                  "audio/wav")
    doc = {"token": token, "tenant_id": user["id"], "name": name.strip(), "storage_path": res["path"],
           "duration": round(duration, 1), "shared": user.get("role") == "admin", "is_deleted": False,
           "original_filename": file.filename, "created_at": now_iso()}
    await db.ambience_files.insert_one(doc)
    return ambience_out(doc)


@router.delete("/ambiences/custom/{token}")
async def delete_custom(token: str, user=CurrentUser):
    res = await db.ambience_files.update_one({"token": token, "tenant_id": user["id"]}, {"$set": {"is_deleted": True}})
    if not res.matched_count:
        raise HTTPException(404, "Grabación no encontrada")
    await db.agents.update_many({"tenant_id": user["id"], "ambience": f"custom:{token}"}, {"$set": {"ambience": "oficina_real"}})
    return {"ok": True}


async def _custom_samples(token: str):
    if token in _custom_cache:
        _custom_cache.move_to_end(token)
        return _custom_cache[token]
    doc = await db.ambience_files.find_one({"token": token, "is_deleted": False})
    if not doc:
        raise HTTPException(404, "Ambiente no encontrado")
    raw = await asyncio.to_thread(storage.get_object, doc["storage_path"])
    x = await asyncio.to_thread(ambience.decode, raw)
    _custom_cache[token] = x
    if len(_custom_cache) > 6:
        _custom_cache.popitem(last=False)
    return x


@router.get("/ambience/custom/{token}/{volume}.wav")
async def custom_wav(token: str, volume: int):
    x = await _custom_samples(token)
    vol = max(0, min(100, round(volume / 5) * 5))
    wav = await asyncio.to_thread(ambience.to_wav, x, vol)
    return Response(wav, media_type="audio/wav", headers={"Cache-Control": "public, max-age=86400"})


# ---------- Custom ElevenLabs voices (admin) ----------
class CustomVoiceIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    gender: str = Field(pattern=r"^(Mujer|Hombre)$")
    country: str = Field(pattern=r"^(ES|CL)$")
    voice_id: str = Field(pattern=r"^[A-Za-z0-9]{10,40}$")
    tone: str = Field("", max_length=60)


async def load_custom_voices():
    doc = await db.platform_settings.find_one({"_id": "voices"}) or {}
    vapi.STATE["custom_voices"] = {v["id"]: v for v in doc.get("items", [])}


@router.get("/voices/custom")
async def list_custom_voices(user=CurrentUser):
    return list(vapi.STATE["custom_voices"].values())


@router.post("/admin/voices")
async def add_custom_voice(body: CustomVoiceIn, user=Depends(require_admin)):
    item = {"id": f"x_{uuid.uuid4().hex[:10]}", **body.model_dump(), "created_at": now_iso()}
    await db.platform_settings.update_one({"_id": "voices"}, {"$push": {"items": item}}, upsert=True)
    await load_custom_voices()
    return item


@router.delete("/admin/voices/{vid}")
async def delete_custom_voice(vid: str, user=Depends(require_admin)):
    if await db.agents.count_documents({"voice": vid}):
        raise HTTPException(400, "Hay agentes usando esta voz. Cámbiales la voz antes de borrarla.")
    await db.platform_settings.update_one({"_id": "voices"}, {"$pull": {"items": {"id": vid}}})
    await load_custom_voices()
    return {"ok": True}


# ---------- Recording proxy ----------
@router.get("/leads/{lead_id}/recording")
async def lead_recording(lead_id: str, user=CurrentUser):
    lead = await db.leads.find_one({"_id": ObjectId(lead_id) if ObjectId.is_valid(lead_id) else None,
                                    "tenant_id": user["id"]})
    if not lead or not lead.get("vapi_call_id"):
        raise HTTPException(404, "Grabación no disponible")
    try:
        url = await vapi.recording_url(lead["vapi_call_id"])
    except vapi.VapiError as e:
        raise HTTPException(404, str(e))
    return RedirectResponse(url, status_code=302)


# ---------- Admin: costs & pricing ----------
class PricingIn(BaseModel):
    line_rate_usd_min: float = Field(ge=0, le=2)
    line_rate_cl_usd_min: float = Field(ge=0, le=2)
    usd_eur: float = Field(gt=0, le=2)
    usd_clp: float = Field(gt=100, le=5000)
    margin_pct: float = Field(ge=0, le=1000)
    voice_11labs_usd_min: float = Field(0.036, ge=0, le=1)
    voice_cartesia_usd_min: float = Field(0.022, ge=0, le=1)
    voice_azure_usd_min: float = Field(0.011, ge=0, le=1)


async def get_pricing() -> dict:
    doc = await db.platform_settings.find_one({"_id": "pricing"}) or {}
    return {k: doc.get(k, v) for k, v in DEFAULT_PRICING.items()}


@router.get("/admin/pricing")
async def read_pricing(user=Depends(require_admin)):
    return await get_pricing()


@router.put("/admin/pricing")
async def save_pricing(body: PricingIn, user=Depends(require_admin)):
    await db.platform_settings.update_one({"_id": "pricing"}, {"$set": body.model_dump()}, upsert=True)
    return body.model_dump()


def _parts(lead: dict, rate: float) -> dict:
    b = lead.get("cost_breakdown") or {}
    a = b.get("analysisCostBreakdown") or {}
    minutes = (lead.get("duration_seconds") or 0) / 60
    p = {"voz": b.get("tts", 0), "transcripcion": b.get("stt", 0), "ia": b.get("llm", 0), "vapi": b.get("vapi", 0),
         "analisis": sum(a.get(k, 0) for k in ("summary", "structuredData", "successEvaluation")),
         "linea": round(minutes * rate, 5)}
    vapi_total = lead.get("cost")
    if vapi_total is None:
        vapi_total = sum(v for k, v in p.items() if k != "linea")
    p["otros"] = max(0.0, round(vapi_total - sum(v for k, v in p.items() if k != "linea"), 5))
    p["total"] = round(vapi_total + p["linea"], 5)
    return {"minutes": round(minutes, 2), **p}


@router.get("/admin/costs")
async def admin_costs(days: int = 30, user=Depends(require_admin)):
    pricing = await get_pricing()
    since = (datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 365)))).isoformat()
    leads = await db.leads.find({"vapi_call_id": {"$ne": None}, "created_at": {"$gte": since}},
                                {"messages": 0, "transcript": 0}).sort("created_at", -1).to_list(5000)
    users = {str(u["_id"]): u async for u in db.users.find({}, {"business_name": 1, "email": 1, "country": 1})}
    agent_country = {str(a["_id"]): a.get("country", "ES") async for a in db.agents.find({}, {"country": 1})}
    rates = {"ES": pricing["line_rate_usd_min"], "CL": pricing["line_rate_cl_usd_min"]}
    by_country = {c: {"calls": 0, "minutes": 0.0, "total": 0.0, "voz": 0.0} for c in rates}
    voices = {k: {"minutes": 0.0, "voz": 0.0, "calls": 0} for k in ("11labs", "cartesia", "azure")}
    calls, tenants, totals = [], {}, {"calls": 0, "minutes": 0.0, "total": 0.0, "missing_cost": 0}
    keys = ["voz", "transcripcion", "ia", "vapi", "analisis", "linea", "otros"]
    breakdown = dict.fromkeys(keys, 0.0)
    for ld in leads:
        country = agent_country.get(ld["agent_id"], "ES")
        p = _parts(ld, rates[country])
        bc = by_country[country]
        bc["calls"] += 1
        bc["minutes"] += p["minutes"]
        bc["total"] += p["total"]
        bc["voz"] += p["voz"]
        vp = voices.get(ld.get("voice_provider") or "")
        if vp is not None and p["minutes"]:
            vp["calls"] += 1
            vp["minutes"] += p["minutes"]
            vp["voz"] += p["voz"]
        if ld.get("cost") is None:
            totals["missing_cost"] += 1
        totals["calls"] += 1
        totals["minutes"] += p["minutes"]
        totals["total"] += p["total"]
        for k in keys:
            breakdown[k] += p[k]
        u = users.get(ld["tenant_id"], {})
        currency = "CLP" if u.get("country") == "CL" else "EUR"
        t = tenants.setdefault(ld["tenant_id"], {"tenant_id": ld["tenant_id"], "business": u.get("business_name") or "—",
                                                 "currency": currency, "calls": 0, "minutes": 0.0, "total": 0.0})
        t["calls"] += 1
        t["minutes"] += p["minutes"]
        t["total"] += p["total"]
        if len(calls) < 300:
            calls.append({"id": str(ld["_id"]), "created_at": ld["created_at"], "business": t["business"],
                          "lead": ld["name"], "status": ld["status"], "is_test": ld.get("is_test", False),
                          "country": country, "currency": currency, **p})
    for t in tenants.values():
        t["cost_per_min"] = t["total"] / t["minutes"] if t["minutes"] else None
    for bc in by_country.values():
        bc["cost_per_min"] = bc["total"] / bc["minutes"] if bc["minutes"] else None
        bc["minutes_per_call"] = bc["minutes"] / bc["calls"] if bc["calls"] else None
        bc["base_per_min"] = (bc["total"] - bc["voz"]) / bc["minutes"] if bc["minutes"] else None
    for k, vp in voices.items():
        vp["measured_per_min"] = vp["voz"] / vp["minutes"] if vp["minutes"] else None
        vp["per_min"] = vp["measured_per_min"] if vp["minutes"] >= 5 else pricing[f"voice_{k}_usd_min"]
    return {"pricing": pricing, "totals": totals, "voices": voices, "breakdown": breakdown, "by_country": by_country,
            "cost_per_min": totals["total"] / totals["minutes"] if totals["minutes"] else None,
            "cost_per_call": totals["total"] / totals["calls"] if totals["calls"] else None,
            "minutes_per_call": totals["minutes"] / totals["calls"] if totals["calls"] else None,
            "tenants": sorted(tenants.values(), key=lambda t: -t["total"]), "calls": calls}


@router.post("/admin/costs/sync")
async def sync_costs(user=Depends(require_admin)):
    leads = await db.leads.find({"vapi_call_id": {"$ne": None}, "cost": None}).to_list(200)
    updated = 0
    for ld in leads:
        if await S.sync_call_cost(ld):
            updated += 1
    return {"updated": updated, "pending": len(leads) - updated}
