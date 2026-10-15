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
DUR = 30
PRESETS = {
    "oficina": {"voices": 4, "voice_gain": 0.35, "keys": 0.6, "room": 0.25, "seed": 11},
    "teclados": {"voices": 0, "voice_gain": 0.0, "keys": 1.0, "room": 0.18, "seed": 23},
    "call_center": {"layers": [("Call_center_real", 0.09), ("Computer_keyboard", 0.035)], "seed": 37},
    "oficina_real": {"layers": [("Oficina_aristeia", 0.055), ("Computer_keyboard", 0.075), ("Laptop_keyboard", 0.05)],
                     "drive": 3.0, "seed": 5},
    "teclado_real": {"layers": [("Laptop_keyboard", 0.12)], "seed": 7},
}


def _band(x, lo, hi):
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    spec[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(spec, len(x))


def _norm(x):
    p = np.max(np.abs(x))
    return x / p if p > 0 else x


def _envelope(rng, n):
    env = np.zeros(n)
    t = int(rng.uniform(0, 2) * SR)
    while t < n:
        end = min(n, t + int(rng.uniform(1.2, 4.5) * SR))
        k = t
        while k < end:
            syl = int(rng.uniform(0.07, 0.22) * SR)
            env[k:k + syl] = rng.uniform(0.4, 1.0)
            k += syl + int(rng.uniform(0.02, 0.09) * SR)
        t = end + int(rng.uniform(0.6, 3.0) * SR)
    return np.clip(_band(env, 0, 10), 0, None)


def _voice(rng, n):
    lo = rng.uniform(250, 400)
    v = _band(rng.standard_normal(n), lo, lo + rng.uniform(500, 900))
    return _norm(v) * _envelope(rng, n) * rng.uniform(0.35, 1.0)


def _keys(rng, n):
    out = np.zeros(n)
    clen = int(0.035 * SR)
    tt = np.arange(clen) / SR
    t = int(rng.uniform(0, 1.5) * SR)
    while t < n:
        for _ in range(int(rng.integers(4, 30))):
            if t + clen >= n:
                break
            click = np.diff(rng.standard_normal(clen) * np.exp(-tt / 0.0016), prepend=0)
            thump = np.sin(2 * np.pi * rng.uniform(140, 330) * tt) * np.exp(-tt / 0.006) * 0.5
            amp = rng.uniform(0.35, 1.0) * (1.7 if rng.random() < 0.08 else 1.0)
            out[t:t + clen] += (0.6 * click + thump) * amp
            t += int(rng.uniform(0.07, 0.26) * SR)
        t += int(rng.uniform(0.7, 4.5) * SR)
    return out


def _room(rng, n):
    brown = np.cumsum(rng.standard_normal(n))
    return _norm(_band(brown, 25, 300))


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


def to_wav(x, volume: int, gain: float = 0.7) -> bytes:
    x = x.copy()
    fade = int(0.08 * SR)
    ramp = np.linspace(0, 1, fade)
    x[:fade] *= ramp
    x[-fade:] *= ramp[::-1]
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


def _presence(x):
    return x + 0.8 * _band(x, 1500, 3400)


@lru_cache(maxsize=48)
def render(preset: str, volume: int) -> bytes:
    cfg = PRESETS[preset]
    rng = np.random.default_rng(cfg["seed"])
    if "layers" in cfg:
        srcs = [(_real(f), g, "keyboard" in f.lower()) for f, g in cfg["layers"]]
        n = max(len(x) for x, _, _ in srcs)
        mix = sum(_level(_presence(x) if k else x, g) if len(x) == n else _level(np.resize(_presence(x) if k else x, n), g)
                  for x, g, k in srcs)
        if cfg.get("voices"):
            mix = mix + _level(sum(_voice(rng, n) for _ in range(cfg["voices"])), cfg["voice_gain"])
        d = cfg.get("drive", 2.2)
        return to_wav(np.tanh(mix * d) / d, volume, gain=0.7)
    n = SR * DUR
    mix = cfg["room"] * _room(rng, n)
    if cfg["voices"]:
        mix += cfg["voice_gain"] * _norm(sum(_voice(rng, n) for _ in range(cfg["voices"])))
    mix += cfg["keys"] * _norm(_keys(rng, n))
    return to_wav(mix, volume)
