import asyncio
import hashlib
import io
from pathlib import Path
import logging
import os
import wave
from collections import OrderedDict
import httpx
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from emergentintegrations.llm.openai import OpenAITextToSpeech
import ambience
import auth as A
import extra_routes as X
import storage
import vapi
from db import db
from models import now_iso

router = APIRouter(prefix="/api")
log = logging.getLogger("vozlead.preview")
ELEVEN_URL = "https://api.elevenlabs.io/v1"
_mix_cache: "OrderedDict[str, bytes]" = OrderedDict()


async def eleven_key() -> str:
    return ((await db.platform_settings.find_one({"_id": "elevenlabs"})) or {}).get("api_key", "")


def eleven_voice_id(voice: str) -> str:
    custom = vapi.STATE["custom_voices"].get(voice)
    return custom["voice_id"] if custom else vapi.ELEVEN.get(voice, "")


async def eleven_tts(key: str, voice_id: str, text: str, lang: str = "es") -> bytes:
    v = vapi.eleven_voice(voice_id)
    body = {"text": text, "model_id": v["model"], "language_code": lang,
            "voice_settings": {"stability": v["stability"], "similarity_boost": v["similarityBoost"], "style": v["style"],
                               "use_speaker_boost": v["useSpeakerBoost"], "speed": v["speed"]}}
    async with httpx.AsyncClient(timeout=40) as x:
        r = await x.post(f"{ELEVEN_URL}/text-to-speech/{voice_id}?output_format=mp3_44100_128", json=body,
                         headers={"xi-api-key": key})
    if r.status_code >= 400:
        try:
            msg = r.json().get("detail", {})
            msg = msg.get("message") if isinstance(msg, dict) else msg
        except ValueError:
            msg = r.text
        raise HTTPException(400, f"El motor de voz respondió: {str(msg)[:200]}")
    return r.content


async def cartesia_key() -> str:
    doc = await db.platform_settings.find_one({"_id": "cartesia"}) or {}
    return doc.get("api_key") or os.environ.get("CARTESIA_API_KEY", "")


async def _cartesia_post(key: str, voice_id: str, text: str) -> httpx.Response:
    body = {"model_id": "sonic-3", "transcript": text, "voice": {"mode": "id", "id": voice_id}, "language": "es",
            "output_format": {"container": "wav", "encoding": "pcm_s16le", "sample_rate": 24000}}
    async with httpx.AsyncClient(timeout=40) as x:
        return await x.post("https://api.cartesia.ai/tts/bytes", json=body,
                            headers={"X-API-Key": key, "Cartesia-Version": "2025-04-16"})


async def cartesia_tts(voice_id: str, text: str) -> bytes:
    key = await cartesia_key()
    if not key:
        raise HTTPException(503, "La vista previa de las voces Premium no está activada: conecta la clave de Cartesia en Super Admin.")
    r = await _cartesia_post(key, voice_id, text)
    if r.status_code >= 400:
        log.warning("Cartesia preview failed %s: %s", r.status_code, r.text[:200])
        raise HTTPException(424, "El motor de las voces Premium no respondió. Revisa la clave de Cartesia en Super Admin.")
    return r.content


async def azure_tts(voice_name: str, text: str) -> bytes:
    import edge_tts
    out = bytearray()
    try:
        async for chunk in edge_tts.Communicate(text, voice_name).stream():
            if chunk["type"] == "audio":
                out += chunk["data"]
    except Exception as e:  # noqa: BLE001
        log.warning("Standard voice preview failed: %s", e)
        raise HTTPException(424, "El motor de las voces estándar no respondió. Inténtalo en unos segundos.") from e
    return bytes(out)


async def tts(voice: str, text: str, lang: str = "es") -> tuple:
    key = await eleven_key()
    vid = eleven_voice_id(voice)
    premium = {**vapi.PREMIUM, **vapi.PREMIUM_LATAM}
    standard = {**vapi.STANDARD, **vapi.STANDARD_CL, **{k: v[1] for k, v in vapi.L.LANG_VOICES.items()}}
    if vid:
        source, ref = ("elevenlabs" if key else "openai"), f"{vid}|{vapi.eleven_voice(vid)['model']}"
    elif voice in premium:
        source, ref = "cartesia", premium[voice]
    else:
        source, ref = "azure", standard[voice]
    h = hashlib.sha256(f"{source}|{ref}|{text}{'' if lang == 'es' else '|' + lang}".encode()).hexdigest()
    cached = await db.tts_cache.find_one({"hash": h})
    if cached:
        try:
            return await asyncio.to_thread(storage.get_object, cached["path"]), source
        except Exception:  # noqa: BLE001
            pass
    audio = None
    if source == "cartesia":
        audio = await cartesia_tts(premium[voice], text)
    elif source == "azure":
        audio = await azure_tts(standard[voice], text)
    elif source == "elevenlabs":
        try:
            audio = await eleven_tts(key, vid, text, lang)
        except Exception as e:  # noqa: BLE001
            log.warning("ElevenLabs falló (%s); uso la voz de respaldo", getattr(e, "detail", e))
            source = "openai"
    if audio is None:
        female = voice in vapi.FEMALE or (vapi.STATE["custom_voices"].get(voice) or {}).get("gender") == "Mujer"
        try:
            audio = await OpenAITextToSpeech(api_key=os.environ["EMERGENT_LLM_KEY"]).generate_speech(
                text=text, model="tts-1-hd", voice="nova" if female else "onyx")
        except Exception as e:  # noqa: BLE001
            log.exception("Voz de respaldo falló")
            raise HTTPException(424, "El motor de voz no está disponible ahora mismo. Revisa la clave de ElevenLabs en Super Admin.") from e
    try:
        res = await asyncio.to_thread(storage.put_object, f"{storage.APP_NAME}/tts/{h}.mp3", audio, "audio/mpeg")
        await db.tts_cache.update_one({"hash": h}, {"$set": {"path": res["path"], "created_at": now_iso()}}, upsert=True)
    except Exception as e:  # noqa: BLE001
        log.warning("TTS cache store failed: %s", e)
    return audio, source


def _wav_samples(data: bytes):
    with wave.open(io.BytesIO(data)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float) / 32768


async def ambience_samples(amb: str, volume: int):
    if amb in ("none", "vapi_office") or volume <= 0:
        return None
    if amb.startswith("custom:"):
        x = await X._custom_samples(amb[7:])
        return ambience._norm(x) * 0.7 * volume / 100
    if amb not in ambience.PRESETS:
        raise HTTPException(404, "Ambiente no encontrado")
    return _wav_samples(await asyncio.to_thread(ambience.render, amb, volume))


def _phone(x):
    """Sound like a real phone call (narrow band + light compression), not a studio voice-over."""
    x = ambience._band(x, 250, 3600)
    x = np.tanh(x * 1.6) / np.tanh(1.6)
    return np.clip(x / (np.max(np.abs(x)) or 1) * 0.9, -1, 1)


def mix(voice_audio: bytes, bg) -> bytes:
    v = ambience.decode(voice_audio)
    v = v / (np.max(np.abs(v)) or 1) * 0.85
    lead, tail = int(0.9 * ambience.SR), int(1.8 * ambience.SR)
    out = np.zeros(lead + len(v) + tail)
    out[lead:lead + len(v)] += v
    if bg is not None and len(bg):
        out += np.resize(bg, len(out))
    out = _phone(out)
    fade = int(0.3 * ambience.SR)
    out[-fade:] *= np.linspace(1, 0, fade)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(ambience.SR)
        w.writeframes((out * 32767).astype(np.int16).tobytes())
    return buf.getvalue()


async def preview(voice: str, text: str, amb: str, volume: int, lang: str = "es") -> Response:
    vol = max(0, min(100, round(volume / 5) * 5))
    key = hashlib.sha256(f"{voice}|{text}|{amb}|{vol}|{lang}|{bool(await eleven_key())}".encode()).hexdigest()
    if key not in _mix_cache:
        audio, source = await tts(voice, text, lang)
        wav = await asyncio.to_thread(mix, audio, await ambience_samples(amb, vol))
        _mix_cache[key] = (wav, source)
        if len(_mix_cache) > 40:
            _mix_cache.popitem(last=False)
    _mix_cache.move_to_end(key)
    wav, source = _mix_cache[key]
    return Response(wav, media_type="audio/wav", headers={"Cache-Control": "private, max-age=3600", "X-Voice-Source": source})


DEMO_CALL = Path(__file__).resolve().parent / "assets" / "demo" / "demo_call.wav"


@router.get("/voice-preview/demo.wav")
async def demo_preview():
    # Pre-recorded two-voice call (tools/make_demo_call.py): native Spain voices, no API key needed in production.
    return Response(DEMO_CALL.read_bytes(), media_type="audio/wav", headers={"Cache-Control": "public, max-age=86400"})


@router.get("/voice-preview")
async def agent_preview(voice: str, text: str, ambience_id: str = "none", volume: int = 35, lang: str = "es",
                        user=Depends(A.get_current_user)):
    text = text.strip()[:600]
    if not text:
        raise HTTPException(422, "Falta el texto del saludo")
    if not vapi.voice_ok(voice, lang):
        raise HTTPException(422, "Voz no válida para ese idioma")
    if ambience_id.startswith("custom:") and not await X.custom_ambience_allowed(user["id"], ambience_id[7:]):
        raise HTTPException(404, "Ambiente no encontrado")
    return await preview(voice, text, ambience_id, volume, lang)


# ---------- Admin: Cartesia key (Premium voice previews) ----------
class CartesiaIn(BaseModel):
    api_key: str = Field(min_length=10, max_length=200)


@router.get("/admin/cartesia")
async def cartesia_status(user=Depends(X.require_admin)):
    doc = await db.platform_settings.find_one({"_id": "cartesia"}) or {}
    k = await cartesia_key()
    return {"connected": bool(k), "key_last4": k[-4:] if k else None, "from_panel": bool(doc.get("api_key"))}


@router.put("/admin/cartesia")
async def cartesia_connect(body: CartesiaIn, user=Depends(X.require_admin)):
    k = body.api_key.strip()
    r = await _cartesia_post(k, vapi.PREMIUM["p_marta"], "Hola.")
    if r.status_code >= 400:
        raise HTTPException(400, "Cartesia no aceptó la clave. Copia una clave de API válida (empieza por sk_car_).")
    await db.platform_settings.update_one({"_id": "cartesia"}, {"$set": {"api_key": k, "updated_at": now_iso()}}, upsert=True)
    _mix_cache.clear()
    return {"ok": True, "key_last4": k[-4:]}


@router.delete("/admin/cartesia")
async def cartesia_disconnect(user=Depends(X.require_admin)):
    await db.platform_settings.delete_one({"_id": "cartesia"})
    _mix_cache.clear()
    return {"ok": True}


# ---------- Admin: ElevenLabs key ----------
class ElevenIn(BaseModel):
    api_key: str = Field(min_length=20, max_length=200)


@router.get("/admin/elevenlabs")
async def eleven_status(user=Depends(X.require_admin)):
    k = await eleven_key()
    doc = (await db.platform_settings.find_one({"_id": "elevenlabs"})) or {}
    return {"connected": bool(k), "key_last4": k[-4:] if k else None, "vapi_linked": bool(doc.get("vapi_linked"))}


@router.put("/admin/elevenlabs")
async def eleven_connect(body: ElevenIn, user=Depends(X.require_admin)):
    k = body.api_key.strip()
    await eleven_tts(k, vapi.ELEVEN["e_sarah"], "Hola.")
    await db.platform_settings.update_one({"_id": "elevenlabs"}, {"$set": {"api_key": k, "updated_at": now_iso()}}, upsert=True)
    _mix_cache.clear()
    vapi_ok = await sync_vapi_credential(k)
    return {"ok": True, "key_last4": k[-4:], "vapi_linked": vapi_ok}


async def sync_vapi_credential(k: str) -> bool:
    try:
        await vapi.ensure_11labs_credential(k)
    except vapi.VapiError as e:
        log.warning("Vapi 11labs credential failed: %s", e)
        await db.platform_settings.update_one({"_id": "elevenlabs"}, {"$set": {"vapi_linked": False}})
        return False
    await db.platform_settings.update_one({"_id": "elevenlabs"}, {"$set": {"vapi_linked": True}})
    return True


@router.post("/admin/elevenlabs/link-vapi")
async def eleven_link(user=Depends(X.require_admin)):
    k = await eleven_key()
    if not k:
        raise HTTPException(400, "Conecta primero tu clave de ElevenLabs.")
    if not await sync_vapi_credential(k):
        raise HTTPException(400, "Vapi no aceptó la clave de ElevenLabs.")
    return {"ok": True}


ACCENTS = {"ES": ["peninsular", "spain", "castilian", "spanish"], "CL": ["chilean", "chile", "latin american", "latin"]}


async def _eleven_get(path: str, params: dict) -> dict:
    key = await eleven_key()
    if not key:
        raise HTTPException(400, "Conecta primero tu clave de ElevenLabs.")
    async with httpx.AsyncClient(timeout=30) as x:
        r = await x.get(f"{ELEVEN_URL}{path}", params=params, headers={"xi-api-key": key})
    if r.status_code >= 400:
        detail = (r.json().get("detail") or {}) if r.headers.get("content-type", "").startswith("application/json") else {}
        if isinstance(detail, dict) and detail.get("status") == "missing_permissions":
            raise HTTPException(400, "Tu clave de ElevenLabs no tiene permiso de «Voices». Crea una clave nueva con permisos "
                                     "Text to Speech y Voices (lectura y escritura) y pégala aquí.")
        raise HTTPException(400, f"ElevenLabs respondió {r.status_code}")
    return r.json()


@router.get("/admin/elevenlabs/library")
async def eleven_library(country: str = "ES", gender: str = "", language: str = "es", accent: str = "",
                         user=Depends(X.require_admin)):
    seen, out = set(), []
    if language not in vapi.L.ELEVEN_LANGS:
        raise HTTPException(422, "Idioma no disponible")
    for acc in ([accent[:30]] if accent else ACCENTS.get(country, ACCENTS["ES"])[:2] if language == "es" else [""]):
        params = {"language": language, "page_size": 24, "sort": "cloned_by_count", **({"accent": acc} if acc else {})}
        if gender in ("female", "male"):
            params["gender"] = gender
        for v in (await _eleven_get("/shared-voices", params)).get("voices", []):
            if v["voice_id"] in seen:
                continue
            seen.add(v["voice_id"])
            out.append({"voice_id": v["voice_id"], "public_owner_id": v.get("public_owner_id"), "name": v.get("name"),
                        "gender": v.get("gender"), "accent": v.get("accent"), "age": v.get("age"),
                        "use_case": v.get("use_case"), "description": (v.get("description") or "")[:160],
                        "preview_url": v.get("preview_url"), "uses": v.get("cloned_by_count"), "free": bool(v.get("free_users_allowed"))})
    return out


class LibraryAddIn(BaseModel):
    public_owner_id: str = Field(min_length=5, max_length=100)
    voice_id: str = Field(min_length=10, max_length=60)
    name: str = Field(min_length=1, max_length=30)
    gender: str = Field(pattern="^(Mujer|Hombre)$")
    country: str = Field("ES", pattern="^(ES|CL)$")
    tone: str = Field("", max_length=80)
    language: str = Field("es", pattern=r"^(es|en|pt|fr|it|de)$")
    accent: str = Field("", max_length=30)


@router.post("/admin/elevenlabs/library/add")
async def eleven_library_add(body: LibraryAddIn, user=Depends(X.require_admin)):
    key = await eleven_key()
    async with httpx.AsyncClient(timeout=30) as x:
        r = await x.post(f"{ELEVEN_URL}/voices/add/{body.public_owner_id}/{body.voice_id}",
                         json={"new_name": f"VozLeads {body.name}"}, headers={"xi-api-key": key})
    if r.status_code >= 400:
        raise HTTPException(400, f"ElevenLabs no permitió añadir la voz ({r.status_code}): {r.text[:160]}")
    vid = r.json().get("voice_id") or body.voice_id
    return await X.add_custom_voice(X.CustomVoiceIn(name=body.name, gender=body.gender, country=body.country,
                                                    voice_id=vid, tone=body.tone or "Acento nativo",
                                                    language=body.language, accent=body.accent), user)


@router.delete("/admin/elevenlabs")
async def eleven_disconnect(user=Depends(X.require_admin)):
    await db.platform_settings.delete_one({"_id": "elevenlabs"})
    _mix_cache.clear()
    return {"ok": True}
