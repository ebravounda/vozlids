import io
import wave
from functools import lru_cache
import numpy as np

SR = 16000
DUR = 30
PRESETS = {
    "oficina": {"voices": 4, "voice_gain": 0.35, "keys": 0.6, "room": 0.25, "seed": 11},
    "teclados": {"voices": 0, "voice_gain": 0.0, "keys": 1.0, "room": 0.18, "seed": 23},
    "call_center": {"voices": 9, "voice_gain": 0.75, "keys": 0.3, "room": 0.3, "seed": 37},
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


@lru_cache(maxsize=48)
def render(preset: str, volume: int) -> bytes:
    cfg = PRESETS[preset]
    rng = np.random.default_rng(cfg["seed"])
    n = SR * DUR
    mix = cfg["room"] * _room(rng, n)
    if cfg["voices"]:
        mix += cfg["voice_gain"] * _norm(sum(_voice(rng, n) for _ in range(cfg["voices"])))
    mix += cfg["keys"] * _norm(_keys(rng, n))
    fade = int(0.08 * SR)
    ramp = np.linspace(0, 1, fade)
    mix[:fade] *= ramp
    mix[-fade:] *= ramp[::-1]
    mix = _norm(mix) * 0.7 * (volume / 100)
    pcm = (mix * 32767).astype(np.int16).tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm)
    return buf.getvalue()
