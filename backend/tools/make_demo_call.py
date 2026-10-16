"""Builds the landing "Escuchar una llamada real" audio: a short two-voice call with native Spain voices.
Run: cd /app/backend && python tools/make_demo_call.py  (needs the Cartesia key saved in Super Admin)."""
import asyncio
import io
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ambience  # noqa: E402
import vapi  # noqa: E402
import voice_preview as V  # noqa: E402

AGENT = vapi.PREMIUM["p_blanca"]
CLIENT = vapi.PREMIUM["p_alicia"]
OUT = Path(__file__).resolve().parent.parent / "assets" / "demo" / "demo_call.wav"

SCRIPT = [
    ("c", "¿Sí? ¿Diga?"),
    ("a", "Hola, ¿Laura? Soy Blanca, de Clínica Sonrisa. Oye, te llamo porque hace un ratito has pedido información en la web sobre el blanqueamiento... ¿te pillo bien?"),
    ("c", "Ah, sí, sí. Dime, dime."),
    ("a", "Genial. Pues mira, la primera visita es gratis, y ahí mismo la doctora te dice qué tratamiento te va mejor. ¿Te vendría bien pasarte esta semana?"),
    ("c", "Mmm... pues el jueves por la tarde podría."),
    ("a", "Vale, a ver, déjame mirar... El jueves tengo hueco a las cinco y media o a las siete. ¿Qué te viene mejor?"),
    ("c", "A las siete mejor, que salgo de trabajar."),
    ("a", "Perfecto, te apunto el jueves a las siete. Ahora te llega un mensaje con la dirección, ¿vale? Muchas gracias, Laura. ¡Hasta el jueves!"),
    ("c", "¡Genial, gracias! Hasta luego."),
]
GAPS = {"c": (0.35, 0.55), "a": (0.45, 0.7)}


def _trim(x, thr=0.01):
    idx = np.flatnonzero(np.abs(x) > thr)
    return x[max(0, idx[0] - 400):idx[-1] + 1600] if len(idx) else x


async def main():
    rng = np.random.default_rng(3)
    parts = []
    for who, text in SCRIPT:
        x = _trim(ambience.decode(await V.cartesia_tts(AGENT if who == "a" else CLIENT, text)))
        x = x / (np.max(np.abs(x)) or 1) * (0.85 if who == "a" else 0.8)
        if who == "c":
            x = ambience._band(x, 320, 3300)
        parts += [np.zeros(int(rng.uniform(*GAPS[who]) * ambience.SR)), x]
    voice = np.concatenate([np.zeros(int(0.6 * ambience.SR))] + parts + [np.zeros(int(1.2 * ambience.SR))])
    bg = V._wav_samples(ambience.render("oficina_real", 15))
    out = V._phone(voice + np.resize(bg, len(voice)))
    fade = int(0.4 * ambience.SR)
    out[-fade:] *= np.linspace(1, 0, fade)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(ambience.SR)
        w.writeframes((out * 32767).astype(np.int16).tobytes())
    OUT.write_bytes(buf.getvalue())
    print(OUT, f"{len(out) / ambience.SR:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
