import io
import subprocess
import wave
from functools import lru_cache
from pathlib import Path
import imageio_ffmpeg
import numpy as np

ASSETS = Path(__file__).parent / "assets" / "ambience"
MAX_UPLOAD_SECONDS = 180
RAW = {"Call_center_real"}

SR = 16000
PRESETS = {
    "oficina": {"layers": [("Ambient_classroom_mono", 0.03), ("Computer_keyboard", 0.05), ("Laptop_keyboard", 0.035)],
                "bursts": True, "distant": {"Ambient_classroom_mono": 1400}, "room": 0.004, "seed": 11},
    "teclados": {"layers": [("Computer_keyboard", 0.06), ("Laptop_keyboard", 0.045)], "bursts": True,
                 "burst_off": (2.5, 7.0), "room": 0.006, "seed": 23},
    "call_center": {"layers": [("Call_center_real", 0.09)], "drive": 1.2, "seed": 37},
    "oficina_real": {"layers": [("Oficina_aristeia", 0.055), ("Computer_keyboard", 0.07), ("Laptop_keyboard", 0.045)],
                     "bursts": True, "drive": 3.0, "seed": 5},
    "teclado_real": {"layers": [("Laptop_keyboard", 0.11)], "bursts": True, "burst_on": (1.5, 5.0), "burst_off": (2.5, 7.0),
                     "room": 0.01, "seed": 7},
}


def _band(x, lo, hi):
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    spec[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(spec, len(x))


def _norm(x):
    p = np.max(np.abs(x))
    return x / p if p > 0 else x


def _room(rng, n):
    brown = np.cumsum(rng.standard_normal(n))
    return _norm(_band(brown, 60, 1500))


def clean(x):
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    spec[f < 220] = 0
    for width in (80, 30):
        lm = np.log(np.abs(spec) + 1e-9)
        bw = int(width / (SR / len(x))) | 1
        base = np.convolve(lm, np.ones(bw) / bw, mode="same")
        mask = (lm - base > np.log(2)) & (f < 5000) & (f >= 220)
        spec[mask] *= np.exp(base[mask] - lm[mask])
    return np.fft.irfft(spec, len(x))


def decode(data: bytes):
    """Any audio format -> cleaned mono float array at SR (max MAX_UPLOAD_SECONDS)."""
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-i", "pipe:0", "-t", str(MAX_UPLOAD_SECONDS),
           "-ac", "1", "-ar", str(SR), "-f", "s16le", "pipe:1"]
    out = subprocess.run(cmd, input=data, capture_output=True, timeout=120)
    if out.returncode != 0 or not out.stdout:
        raise ValueError("No se pudo leer el audio. Usa MP3, M4A, WAV u OGG.")
    return np.frombuffer(out.stdout, np.int16).astype(float) / 32768


def seamless(x, secs: float = 2.0):
    """Crossfade the tail into the head so the call's background loop has no audible seam or gap."""
    k = int(secs * SR)
    if len(x) <= 3 * k:
        return x
    ramp = np.sqrt(np.linspace(0, 1, k))
    head = x[:k] * ramp + x[-k:] * ramp[::-1]
    return np.concatenate([head, x[k:-k]])


def to_wav(x, volume: int, gain: float = 0.7) -> bytes:
    x = seamless(x)
    pcm = (_norm(x) * gain * (volume / 100) * 32767).astype(np.int16).tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm)
    return buf.getvalue()


@lru_cache(maxsize=4)
def _real(name: str):
    with open(ASSETS / f"{name}.wav", "rb") as fh:
        x = decode(fh.read())
    return x if name in RAW else clean(x)


def _level(x, rms):
    r = np.sqrt(np.mean(x ** 2))
    return x * (rms / r) if r > 0 else x


def _bursts(rng, x, on=(1.2, 4.0), off=(4.0, 11.0)):
    """Real typing comes in short bursts with pauses, not a non-stop stream of keys."""
    n, env, t = len(x), np.zeros(len(x)), int(rng.uniform(*off) * SR / 2)
    fade = int(0.06 * SR)
    while t < n:
        d = int(rng.uniform(*on) * SR)
        seg = np.ones(d)
        seg[:fade], seg[-fade:] = np.linspace(0, 1, fade), np.linspace(1, 0, fade)
        env[t:t + d] = seg[:max(0, min(d, n - t))]
        t += d + int(rng.uniform(*off) * SR)
    start = int(rng.integers(0, max(1, n - SR)))
    return np.roll(x, -start) * env


def _presence(x):
    return x + 0.8 * _band(x, 1500, 3400)


@lru_cache(maxsize=48)
def render(preset: str, volume: int) -> bytes:
    cfg = PRESETS[preset]
    rng = np.random.default_rng(cfg["seed"])
    srcs = [(_real(f), g, "keyboard" in f.lower()) for f, g in cfg["layers"]]
    n = max(len(x) for x, _, _ in srcs)
    mix = _level(_room(rng, n), cfg.get("room", 0))
    timing = {"on": cfg.get("burst_on", (1.2, 4.0)), "off": cfg.get("burst_off", (4.0, 11.0))}
    for (x, g, k), (name, _) in zip(srcs, cfg["layers"]):
        if name in cfg.get("distant", {}):
            x = _band(x, 120, cfg["distant"][name])
        layer = _level(np.resize(_presence(x) if k else x, n), g)
        mix = mix + (_bursts(rng, layer, **timing) if k and cfg.get("bursts") else layer)
    d = cfg.get("drive", 2.2)
    return to_wav(np.tanh(mix * d) / d, volume, gain=0.7)
