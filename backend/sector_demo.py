import asyncio
import json
import logging
import subprocess
from pathlib import Path
import imageio_ffmpeg
import numpy as np
from bson import Binary
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
import ambience
import vapi
import voice_preview as V
from db import db
from extra_routes import require_admin
from models import now_iso

router = APIRouter(prefix="/api")
log = logging.getLogger("vozlead.sector_demo")
DIALOGS = json.loads((Path(__file__).parent / "assets" / "sector_dialogs.json").read_text())
FALLBACK = {"agent": ["e_sarah", "elvira"], "caller": ["e_chris", "alvaro"]}
_locks: dict = {}


def voices_for(country: str) -> dict:
    custom = [v for v in vapi.STATE["custom_voices"].values() if v["country"] == country]
    pick = lambda g: [v["id"] for v in custom if v["gender"] == g][:1]  # noqa: E731
    return {"agent": pick("Mujer") + FALLBACK["agent"], "caller": pick("Hombre") + FALLBACK["caller"]}


async def speak(candidates: list, text: str) -> np.ndarray:
    for i, voice in enumerate(candidates):
        try:
            audio, _ = await V.tts(voice, text)
            return ambience.decode(audio)
        except Exception as e:  # noqa: BLE001
            if i == len(candidates) - 1:
                raise
            log.warning("Sector demo voice %s failed, trying next: %s", voice, e)


def phone_line(x: np.ndarray) -> np.ndarray:
    return ambience._band(x, 300, 3400) * 0.8


def to_mp3(x: np.ndarray) -> bytes:
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes()
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-f", "s16le", "-ar", str(ambience.SR), "-ac", "1",
           "-i", "pipe:0", "-b:a", "64k", "-f", "mp3", "pipe:1"]
    return subprocess.run(cmd, input=pcm, capture_output=True, timeout=120, check=True).stdout


async def build(country: str, slug: str) -> dict:
    lines = DIALOGS[f"{country}-{slug}"]
    voices = voices_for(country)
    parts = [await speak(voices[who], text) for who, text in lines]
    sr = ambience.SR
    out, marks, t = [np.zeros(int(0.6 * sr))], [], 0.6
    for (who, _), x in zip(lines, parts):
        x = x / (np.max(np.abs(x)) or 1) * 0.8
        x = phone_line(x) if who == "caller" else x
        marks.append(round(t, 2))
        out += [x, np.zeros(int(0.45 * sr))]
        t += len(x) / sr + 0.45
    voice = np.concatenate(out + [np.zeros(int(0.8 * sr))])
    bg = V._wav_samples(await asyncio.to_thread(ambience.render, "oficina_real", 30))
    mixed = voice + np.resize(bg, len(voice))
    mixed = mixed / (np.max(np.abs(mixed)) or 1) * 0.9
    fade = int(0.4 * sr)
    mixed[-fade:] *= np.linspace(1, 0, fade)
    mp3 = await asyncio.to_thread(to_mp3, mixed)
    doc = {"_id": f"{country}-{slug}", "audio": Binary(mp3), "marks": marks, "duration": round(t + 0.8, 2),
           "voices": voices, "created_at": now_iso()}
    await db.sector_demos.replace_one({"_id": doc["_id"]}, doc, upsert=True)
    return doc


async def get_demo(country: str, slug: str) -> dict:
    country = country.upper()
    if f"{country}-{slug}" not in DIALOGS:
        raise HTTPException(404, "Ejemplo no encontrado")
    key = f"{country}-{slug}"
    async with _locks.setdefault(key, asyncio.Lock()):
        doc = await db.sector_demos.find_one({"_id": key})
        if not doc:
            try:
                doc = await build(country, slug)
            except Exception as e:  # noqa: BLE001
                log.warning("Sector demo %s failed: %s", key, e)
                raise HTTPException(503, "El audio de ejemplo no está disponible ahora mismo")
    return doc


@router.get("/public/sector-demo/{country}/{slug}.mp3")
async def demo_audio(country: str, slug: str):
    doc = await get_demo(country, slug)
    return Response(bytes(doc["audio"]), media_type="audio/mpeg", headers={"Cache-Control": "public, max-age=86400"})


@router.get("/public/sector-demo/{country}/{slug}/marks")
async def demo_marks(country: str, slug: str):
    doc = await get_demo(country, slug)
    return {"marks": doc["marks"], "duration": doc["duration"]}


@router.delete("/admin/sector-demos")
async def reset_demos(user=Depends(require_admin)):
    res = await db.sector_demos.delete_many({})
    return {"deleted": res.deleted_count}
