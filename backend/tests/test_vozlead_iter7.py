# Iteration-7: server-side voice preview (ElevenLabs/OpenAI fallback) + admin ElevenLabs key
import io
import os
import uuid
import wave

import numpy as np
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or os.environ["PUBLIC_BACKEND_URL"]).rstrip("/")
ADMIN_EMAIL = "admin@vozlead.es"
ADMIN_PASSWORD = "VozLead2026!"


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def member_session():
    """A fresh non-admin tenant for permission checks."""
    s = requests.Session()
    email = f"tb_i7_{uuid.uuid4().hex[:10]}@example.com"
    r = s.post(f"{BASE}/api/auth/register",
               json={"name": "T7", "business_name": "Biz7", "email": email, "password": "Testing2026!"},
               timeout=30)
    assert r.status_code in (200, 201), r.text
    return s


# ---------- helpers ----------
def _wav_rms_windows(data: bytes):
    with wave.open(io.BytesIO(data)) as w:
        sr = w.getframerate()
        samples = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float) / 32768
    duration = len(samples) / sr
    rms = []
    for sec in range(int(duration)):
        chunk = samples[sec * sr:(sec + 1) * sr]
        rms.append(float(np.sqrt(np.mean(chunk ** 2)) if len(chunk) else 0.0))
    return duration, rms, sr


# ---------- demo preview (public) ----------
def test_demo_preview_returns_wav_with_voice_source_header():
    r = requests.get(f"{BASE}/api/voice-preview/demo.wav", timeout=90)
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("audio/wav")
    # No key configured yet -> openai fallback
    assert r.headers.get("X-Voice-Source") in ("openai", "elevenlabs")
    duration, rms, sr = _wav_rms_windows(r.content)
    assert duration >= 6, f"audio too short: {duration}s"
    # Non-silent voice content between seconds 1 and 8
    voiced_window_max = max(rms[1:min(8, len(rms))])
    assert voiced_window_max > 0.02, f"voice window too quiet, rms peaks={rms}"


def test_demo_preview_public_no_auth_required():
    r = requests.get(f"{BASE}/api/voice-preview/demo.wav", timeout=90)
    assert r.status_code == 200


# ---------- agent preview (auth) ----------
def test_agent_preview_requires_auth():
    r = requests.get(f"{BASE}/api/voice-preview",
                     params={"voice": "e_sarah", "text": "Hola", "ambience_id": "none", "volume": "35"},
                     timeout=30)
    assert r.status_code == 401


def test_agent_preview_invalid_voice_422(admin_session):
    r = admin_session.get(f"{BASE}/api/voice-preview",
                          params={"voice": "voice_that_does_not_exist", "text": "Hola", "ambience_id": "none",
                                  "volume": "35"}, timeout=30)
    assert r.status_code == 422


def test_agent_preview_empty_text_422(admin_session):
    r = admin_session.get(f"{BASE}/api/voice-preview",
                          params={"voice": "e_sarah", "text": "   ", "ambience_id": "none", "volume": "35"},
                          timeout=30)
    assert r.status_code == 422


def test_agent_preview_custom_ambience_other_tenant_404(member_session):
    # Member does not own custom ambience "nonexistent" -> 404
    r = member_session.get(f"{BASE}/api/voice-preview",
                           params={"voice": "e_sarah", "text": "Hola Laura", "ambience_id": "custom:does-not-exist",
                                   "volume": "35"}, timeout=90)
    assert r.status_code == 404


def test_agent_preview_success_returns_wav(admin_session):
    r = admin_session.get(f"{BASE}/api/voice-preview",
                          params={"voice": "e_sarah", "text": "Hola Laura, prueba de voz.",
                                  "ambience_id": "oficina_real", "volume": "35"},
                          timeout=120)
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("audio/wav")
    duration, rms, sr = _wav_rms_windows(r.content)
    assert duration >= 2
    assert max(rms) > 0.02


# ---------- admin ElevenLabs settings ----------
def test_eleven_status_requires_admin(member_session):
    r = member_session.get(f"{BASE}/api/admin/elevenlabs", timeout=30)
    assert r.status_code == 403


def test_eleven_status_initial(admin_session):
    r = admin_session.get(f"{BASE}/api/admin/elevenlabs", timeout=30)
    assert r.status_code == 200
    body = r.json()
    assert "connected" in body
    assert isinstance(body["connected"], bool)


def test_eleven_put_invalid_key_returns_400(admin_session):
    r = admin_session.put(f"{BASE}/api/admin/elevenlabs",
                          json={"api_key": "invalidkeyinvalidkey12345"}, timeout=60)
    assert r.status_code == 400, r.text
    # Should still not be connected after failing validation
    r2 = admin_session.get(f"{BASE}/api/admin/elevenlabs", timeout=30)
    assert r2.status_code == 200
    assert r2.json()["connected"] is False


def test_eleven_put_schema_short_key_422(admin_session):
    r = admin_session.put(f"{BASE}/api/admin/elevenlabs", json={"api_key": "short"}, timeout=30)
    assert r.status_code == 422


def test_eleven_put_requires_admin(member_session):
    r = member_session.put(f"{BASE}/api/admin/elevenlabs",
                           json={"api_key": "invalidkeyinvalidkey12345"}, timeout=30)
    assert r.status_code == 403
