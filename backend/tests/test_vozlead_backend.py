"""VozLead backend regression tests."""
import os
import re
import time
import uuid

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE:
    # fallback to backend .env public url
    BASE = os.environ.get("PUBLIC_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@vozlead.es"
ADMIN_PASSWORD = "VozLead2026!"
WEBHOOK_SECRET = os.environ["VAPI_WEBHOOK_SECRET"]


def _auth_header(session, email, password):
    r = session.post(f"{BASE}/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()


@pytest.fixture(scope="session")
def admin():
    s = requests.Session()
    h, data = _auth_header(s, ADMIN_EMAIL, ADMIN_PASSWORD)
    s.headers.update(h)
    return s, data


@pytest.fixture(scope="session")
def tenant2():
    """Second isolated tenant for isolation tests."""
    s = requests.Session()
    email = f"tenant2_{uuid.uuid4().hex[:8]}@test.es"
    r = s.post(f"{BASE}/api/auth/register", json={
        "name": "Test User2", "business_name": "T2 SL", "email": email, "password": "Password123!"
    })
    assert r.status_code == 200, r.text
    s.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    return s, email


# ---------- Health ----------
def test_root():
    r = requests.get(f"{BASE}/api/")
    assert r.status_code == 200
    assert r.json()["ok"] is True


# ---------- Auth ----------
def test_login_admin():
    r = requests.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200
    d = r.json()
    assert d["email"] == ADMIN_EMAIL
    assert d["role"] == "admin"
    assert d["access_token"]


def test_login_bad_credentials():
    r = requests.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"})
    assert r.status_code == 401


def test_register_duplicate(admin):
    r = requests.post(f"{BASE}/api/auth/register", json={
        "name": "X", "business_name": "X", "email": ADMIN_EMAIL, "password": "Password123!"})
    assert r.status_code == 400


def test_me(admin):
    s, _ = admin
    r = s.get(f"{BASE}/api/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == ADMIN_EMAIL


# ---------- Leads / seed data ----------
def test_leads_seeded(admin):
    s, _ = admin
    r = s.get(f"{BASE}/api/leads")
    assert r.status_code == 200
    leads = r.json()
    names = [l["name"] for l in leads]
    assert "Carlos Ruiz" in names
    assert any(l["status"] == "cita_agendada" for l in leads)


def test_lead_detail_with_appointment(admin):
    s, _ = admin
    leads = s.get(f"{BASE}/api/leads").json()
    carlos = next(l for l in leads if l["name"] == "Carlos Ruiz")
    r = s.get(f"{BASE}/api/leads/{carlos['id']}")
    assert r.status_code == 200
    d = r.json()
    assert len(d["messages"]) > 0
    assert d.get("appointment") is not None


def test_leads_search_and_filter(admin):
    s, _ = admin
    r = s.get(f"{BASE}/api/leads", params={"q": "Carlos"})
    assert r.status_code == 200
    assert all("Carlos" in l["name"] or "Carlos" in l.get("email", "") for l in r.json())
    r2 = s.get(f"{BASE}/api/leads", params={"status": "cita_agendada"})
    assert r2.status_code == 200
    assert all(l["status"] == "cita_agendada" for l in r2.json())


def test_stats(admin):
    s, _ = admin
    r = s.get(f"{BASE}/api/stats")
    assert r.status_code == 200
    d = r.json()
    assert d["total"] >= 4
    assert isinstance(d["by_status"], dict)


# ---------- Agents ----------
AGENT_PAYLOAD = {
    "name": "TEST Agent",
    "business_name": "TEST Negocio",
    "product": "Producto de prueba",
    "objective": "agendar",
    "questions": ["¿Qué necesitas?", "¿Cuándo?"],
    "voice": "elvira",
    "ambience": "oficina",
    "ambience_volume": 40,
    "greeting": "Hola {nombre}, soy el agente de prueba.",
    "extra_instructions": "",
    "active": True,
}


@pytest.fixture(scope="session")
def created_agent(admin):
    s, _ = admin
    r = s.post(f"{BASE}/api/agents", json=AGENT_PAYLOAD)
    assert r.status_code == 200, r.text
    agent = r.json()
    yield agent
    s.delete(f"{BASE}/api/agents/{agent['id']}")


def test_agent_crud(admin, created_agent):
    s, _ = admin
    aid = created_agent["id"]
    r = s.get(f"{BASE}/api/agents/{aid}")
    assert r.status_code == 200
    assert r.json()["name"] == "TEST Agent"
    upd = {**AGENT_PAYLOAD, "name": "TEST Agent 2"}
    r = s.put(f"{BASE}/api/agents/{aid}", json=upd)
    assert r.status_code == 200
    assert r.json()["name"] == "TEST Agent 2"
    r = s.get(f"{BASE}/api/agents/{aid}")
    assert r.json()["name"] == "TEST Agent 2"


def test_agent_list(admin, created_agent):
    s, _ = admin
    r = s.get(f"{BASE}/api/agents")
    assert r.status_code == 200
    assert any(a["id"] == created_agent["id"] for a in r.json())


# ---------- Test call (telephony LIVE - validation-only tests) ----------
def test_test_call_invalid_phone(admin, created_agent):
    s, _ = admin
    r = s.post(f"{BASE}/api/agents/{created_agent['id']}/test-call", json={"phone": "123"})
    assert r.status_code == 422


# ---------- Ambience ----------
def test_ambience_valid():
    r = requests.get(f"{BASE}/api/ambience/oficina/35.wav")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("audio/wav")
    assert r.content[:4] == b"RIFF"


def test_ambience_unknown():
    r = requests.get(f"{BASE}/api/ambience/unknown/35.wav")
    assert r.status_code == 404


# ---------- Public form (telephony LIVE: only test validation + DNC silent path) ----------
def test_public_form_consent_and_get(admin, created_agent):
    aid = created_agent["id"]
    # public GET
    r = requests.get(f"{BASE}/api/public/agents/{aid}")
    assert r.status_code == 200
    assert r.json()["id"] == aid

    # no consent -> 400 (no real call placed because validation fails first)
    r = requests.post(f"{BASE}/api/public/agents/{aid}/leads",
                      json={"name": "Pepe", "phone": "+34612000222", "consent": False})
    assert r.status_code == 400

    # invalid phone -> 422
    r = requests.post(f"{BASE}/api/public/agents/{aid}/leads",
                      json={"name": "Pepe", "phone": "123", "consent": True})
    assert r.status_code in (422, 400)


def test_public_dnc_silent(admin, created_agent):
    s, _ = admin
    phone = "+34612000333"
    # Add to DNC
    r = s.post(f"{BASE}/api/dnc", json={"phone": phone, "reason": "test"})
    assert r.status_code == 200
    dnc_id = r.json()["id"]
    # Submit via public form -> should return ok but not create a lead
    r = requests.post(f"{BASE}/api/public/agents/{created_agent['id']}/leads",
                      json={"name": "DNC TEST", "phone": phone, "consent": True})
    assert r.status_code == 200
    leads = s.get(f"{BASE}/api/leads", params={"agent_id": created_agent['id']}).json()
    assert not any(l["phone"] == phone for l in leads)
    # cleanup
    s.delete(f"{BASE}/api/dnc/{dnc_id}")


# ---------- Agenda / Availability ----------
def test_availability_get_and_put(admin):
    s, _ = admin
    r = s.get(f"{BASE}/api/availability")
    assert r.status_code == 200
    d = r.json()
    assert len(d["days"]) == 7
    body = {"slot_minutes": 30, "days": d["days"]}
    r = s.put(f"{BASE}/api/availability", json=body)
    assert r.status_code == 200


def test_availability_invalid_times(admin):
    s, _ = admin
    days = [{"enabled": True, "start": "18:00", "end": "09:00"}] + \
           [{"enabled": False, "start": "09:00", "end": "14:00"} for _ in range(6)]
    r = s.put(f"{BASE}/api/availability", json={"slot_minutes": 30, "days": days})
    assert r.status_code == 422


def test_appointments_list(admin):
    s, _ = admin
    r = s.get(f"{BASE}/api/appointments")
    assert r.status_code == 200


# ---------- DNC ----------
def test_dnc_crud(admin):
    s, _ = admin
    phone = "+34612000444"
    r = s.post(f"{BASE}/api/dnc", json={"phone": phone, "reason": "test"})
    assert r.status_code == 200
    did = r.json()["id"]
    # duplicate
    r = s.post(f"{BASE}/api/dnc", json={"phone": phone})
    assert r.status_code == 400
    # list
    r = s.get(f"{BASE}/api/dnc")
    assert any(e["phone"] == phone for e in r.json())
    # delete
    r = s.delete(f"{BASE}/api/dnc/{did}")
    assert r.status_code == 200


# ---------- Telephony status (LIVE) ----------
def test_telephony_configured(admin):
    s, _ = admin
    r = s.get(f"{BASE}/api/telephony/status")
    assert r.status_code == 200
    d = r.json()
    assert d["configured"] is True


# ---------- Vapi webhook ----------
def test_webhook_unauthorized():
    r = requests.post(f"{BASE}/api/vapi/webhook", headers={"x-vapi-secret": "wrong"},
                      json={"message": {"type": "status-update"}})
    assert r.status_code == 401


def test_webhook_tool_calls_and_eocr(admin, created_agent):
    """
    Skipped when telephony is live because this test used to create leads via the
    public form (which now places REAL outbound calls). The webhook contract was
    exercised in iteration 1 while Vapi was unconfigured.
    """
    s, _ = admin
    status = s.get(f"{BASE}/api/telephony/status").json()
    if status.get("configured"):
        pytest.skip("Telephony LIVE: skipping to avoid placing real phone calls")
    aid = created_agent["id"]
    # Create a lead via public form
    phone = "+34612000555"
    r = requests.post(f"{BASE}/api/public/agents/{aid}/leads",
                      json={"name": "Webhook TEST", "phone": phone, "consent": True})
    assert r.status_code == 200
    time.sleep(0.3)
    leads = s.get(f"{BASE}/api/leads", params={"agent_id": aid}).json()
    lead = next(l for l in leads if l["phone"] == phone)
    lid = lead["id"]

    # check_availability tool
    payload = {"message": {"type": "tool-calls",
                            "call": {"metadata": {"lead_id": lid}},
                            "toolCallList": [{"id": "tc1",
                                              "function": {"name": "check_availability",
                                                           "arguments": {}}}]}}
    r = requests.post(f"{BASE}/api/vapi/webhook", headers={"x-vapi-secret": WEBHOOK_SECRET}, json=payload)
    assert r.status_code == 200
    out = r.json()
    assert "results" in out
    assert out["results"][0]["toolCallId"] == "tc1"

    # Determine a bookable future date (2 days from now, weekday)
    from datetime import date, timedelta
    d = date.today() + timedelta(days=2)
    # move forward until weekday
    while d.weekday() > 4:
        d += timedelta(days=1)
    date_str = d.isoformat()
    time_str = "10:00"

    book_payload = {"message": {"type": "tool-calls",
                                 "call": {"metadata": {"lead_id": lid}},
                                 "toolCallList": [{"id": "tc2",
                                                   "function": {"name": "book_appointment",
                                                                "arguments": {"date": date_str,
                                                                              "time": time_str}}}]}}
    r = requests.post(f"{BASE}/api/vapi/webhook", headers={"x-vapi-secret": WEBHOOK_SECRET}, json=book_payload)
    assert r.status_code == 200
    import json as _j
    res1 = _j.loads(r.json()["results"][0]["result"])
    # could fail if slot not in availability; print to help
    print("book1:", res1)

    # double booking same slot (new lead)
    r = requests.post(f"{BASE}/api/public/agents/{aid}/leads",
                      json={"name": "Webhook TEST2", "phone": "+34612000666", "consent": True})
    time.sleep(0.3)
    leads2 = s.get(f"{BASE}/api/leads", params={"agent_id": aid}).json()
    lead2 = next(l for l in leads2 if l["phone"] == "+34612000666")
    book_payload["message"]["call"]["metadata"]["lead_id"] = lead2["id"]
    book_payload["message"]["toolCallList"][0]["id"] = "tc3"
    r = requests.post(f"{BASE}/api/vapi/webhook", headers={"x-vapi-secret": WEBHOOK_SECRET}, json=book_payload)
    res2 = _j.loads(r.json()["results"][0]["result"])
    print("book2:", res2)
    if res1.get("ok"):
        assert res2.get("ok") is False

    # mark_do_not_call
    dnc_payload = {"message": {"type": "tool-calls",
                                "call": {"metadata": {"lead_id": lid}},
                                "toolCallList": [{"id": "tc4",
                                                  "function": {"name": "mark_do_not_call",
                                                               "arguments": {}}}]}}
    r = requests.post(f"{BASE}/api/vapi/webhook", headers={"x-vapi-secret": WEBHOOK_SECRET}, json=dnc_payload)
    assert r.status_code == 200
    # check lead has no_llamar
    time.sleep(0.3)
    ld = s.get(f"{BASE}/api/leads/{lid}").json()
    assert ld["status"] == "no_llamar"

    # end-of-call-report updates another lead
    eocr = {"message": {"type": "end-of-call-report",
                        "call": {"metadata": {"lead_id": lead2["id"]},
                                 "endedReason": "assistant-ended-call"},
                        "endedReason": "assistant-ended-call",
                        "durationSeconds": 42.0,
                        "artifact": {"transcript": "A: hola\nB: hola",
                                     "recordingUrl": "https://example.com/rec.mp3",
                                     "messages": [{"role": "assistant", "message": "Hola"},
                                                  {"role": "user", "message": "Hola, dime"}]},
                        "analysis": {"summary": "Lead calificado por teléfono.",
                                     "structuredData": {"outcome": "calificado",
                                                        "interest_score": 72,
                                                        "answers": "quiere info"}}}}
    r = requests.post(f"{BASE}/api/vapi/webhook", headers={"x-vapi-secret": WEBHOOK_SECRET}, json=eocr)
    assert r.status_code == 200
    time.sleep(0.3)
    ld2 = s.get(f"{BASE}/api/leads/{lead2['id']}").json()
    # lead2 might have appointment, in which case status is cita_agendada; otherwise calificado
    assert ld2["status"] in ("calificado", "cita_agendada")
    assert ld2["summary"] == "Lead calificado por teléfono."
    assert ld2["interest_score"] == 72
    assert ld2["recording_url"] == "https://example.com/rec.mp3"


# ---------- Tenant isolation ----------
def test_tenant_isolation(admin, tenant2):
    s_admin, _ = admin
    s2, _ = tenant2
    admin_leads = s_admin.get(f"{BASE}/api/leads").json()
    admin_lead_id = admin_leads[0]["id"]
    r = s2.get(f"{BASE}/api/leads/{admin_lead_id}")
    assert r.status_code == 404
    r = s2.get(f"{BASE}/api/leads")
    assert r.json() == []
    r = s2.get(f"{BASE}/api/agents")
    assert r.json() == []


# ========================================================
# Iteration 2: new ambience presets, custom ambience upload,
# recording proxy, admin costs & pricing
# ========================================================

import io
import wave
import struct


def _make_wav_bytes(seconds: float = 11.0, sr: int = 16000) -> bytes:
    """Build a simple PCM16 mono WAV in memory."""
    n = int(seconds * sr)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        # low volume 220Hz tone so clean() keeps it
        import math
        frames = bytearray()
        for i in range(n):
            v = int(0.3 * 32767 * math.sin(2 * math.pi * 440 * i / sr))
            frames += struct.pack("<h", v)
        w.writeframes(bytes(frames))
    return buf.getvalue()


# ---------- New real-recording presets ----------
def test_ambience_oficina_real():
    r = requests.get(f"{BASE}/api/ambience/oficina_real/35.wav")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("audio/wav")
    assert r.content[:4] == b"RIFF"


def test_ambience_teclado_real():
    r = requests.get(f"{BASE}/api/ambience/teclado_real/35.wav")
    assert r.status_code == 200
    assert r.content[:4] == b"RIFF"


def test_agent_save_with_oficina_real(admin):
    s, _ = admin
    payload = {**AGENT_PAYLOAD, "name": "TEST OfRealAgent", "ambience": "oficina_real"}
    r = s.post(f"{BASE}/api/agents", json=payload)
    assert r.status_code == 200, r.text
    aid = r.json()["id"]
    assert r.json()["ambience"] == "oficina_real"
    g = s.get(f"{BASE}/api/agents/{aid}")
    assert g.json()["ambience"] == "oficina_real"
    s.delete(f"{BASE}/api/agents/{aid}")


def test_agent_save_with_teclado_real(admin):
    s, _ = admin
    payload = {**AGENT_PAYLOAD, "name": "TEST TecRealAgent", "ambience": "teclado_real"}
    r = s.post(f"{BASE}/api/agents", json=payload)
    assert r.status_code == 200, r.text
    aid = r.json()["id"]
    assert r.json()["ambience"] == "teclado_real"
    s.delete(f"{BASE}/api/agents/{aid}")


# ---------- Custom ambience upload CRUD ----------
def test_custom_ambience_upload_list_delete_fallback(admin):
    s, _ = admin
    # Upload valid >=10s wav
    wav = _make_wav_bytes(11.0)
    r = s.post(f"{BASE}/api/ambiences/custom",
               files={"file": ("myamb.wav", wav, "audio/wav")},
               data={"name": "TEST Mi Oficina"})
    assert r.status_code == 200, r.text
    amb = r.json()
    token = amb["id"]
    assert len(token) == 32
    assert amb["name"] == "TEST Mi Oficina"
    assert amb["duration"] >= 10

    # List includes it
    r = s.get(f"{BASE}/api/ambiences/custom")
    assert r.status_code == 200
    assert any(a["id"] == token for a in r.json())

    # Rendered audio endpoint works
    r = s.get(f"{BASE}/api/ambience/custom/{token}/40.wav")
    assert r.status_code == 200
    assert r.content[:4] == b"RIFF"

    # Create an agent using the custom ambience
    payload = {**AGENT_PAYLOAD, "name": "TEST CustomAmbAgent", "ambience": f"custom:{token}"}
    r = s.post(f"{BASE}/api/agents", json=payload)
    assert r.status_code == 200, r.text
    aid = r.json()["id"]
    assert r.json()["ambience"] == f"custom:{token}"

    # Delete ambience -> agent must fall back to oficina_real
    r = s.delete(f"{BASE}/api/ambiences/custom/{token}")
    assert r.status_code == 200
    g = s.get(f"{BASE}/api/agents/{aid}")
    assert g.json()["ambience"] == "oficina_real"

    # Cleanup agent
    s.delete(f"{BASE}/api/agents/{aid}")


def test_custom_ambience_too_short_rejected(admin):
    s, _ = admin
    wav = _make_wav_bytes(5.0)
    r = s.post(f"{BASE}/api/ambiences/custom",
               files={"file": ("short.wav", wav, "audio/wav")},
               data={"name": "TEST short"})
    assert r.status_code == 422
    assert "10 segundos" in r.text or "10" in r.text


def test_custom_ambience_invalid_file_rejected(admin):
    s, _ = admin
    r = s.post(f"{BASE}/api/ambiences/custom",
               files={"file": ("bad.wav", b"not an audio file at all", "audio/wav")},
               data={"name": "TEST invalid"})
    assert r.status_code == 422


def test_agent_with_nonexistent_custom_ambience_422(admin):
    s, _ = admin
    bogus = "ff" * 16  # 32 hex
    payload = {**AGENT_PAYLOAD, "name": "TEST BogusAmb", "ambience": f"custom:{bogus}"}
    r = s.post(f"{BASE}/api/agents", json=payload)
    assert r.status_code == 422


# ---------- Recording proxy ----------
REAL_CALL_LEAD_ID = "6acfb5712bf3b88d8cca8172"


def test_recording_proxy_other_tenant_404(tenant2):
    s2, _ = tenant2
    r = s2.get(f"{BASE}/api/leads/{REAL_CALL_LEAD_ID}/recording", allow_redirects=False)
    assert r.status_code == 404


def test_recording_proxy_admin_lead(admin):
    s, _ = admin
    r = s.get(f"{BASE}/api/leads/{REAL_CALL_LEAD_ID}/recording", allow_redirects=False)
    # If the lead exists and has a vapi_call_id, we expect 302 to signed Vapi URL.
    # If the recording isn't ready / lead missing in this env, allow 404 as acceptable.
    assert r.status_code in (302, 404)
    if r.status_code == 302:
        loc = r.headers.get("location", "")
        assert loc.startswith("http")


# ---------- Admin pricing & costs ----------
def test_admin_pricing_get_put_roundtrip(admin):
    s, _ = admin
    r = s.get(f"{BASE}/api/admin/pricing")
    assert r.status_code == 200
    orig = r.json()
    assert "line_rate_usd_min" in orig and "usd_eur" in orig and "margin_pct" in orig

    new_pricing = {**orig, "line_rate_usd_min": 0.03, "usd_eur": 0.91, "margin_pct": 180}
    r = s.put(f"{BASE}/api/admin/pricing", json=new_pricing)
    assert r.status_code == 200
    r = s.get(f"{BASE}/api/admin/pricing")
    d = r.json()
    assert abs(d["line_rate_usd_min"] - 0.03) < 1e-6
    assert d["margin_pct"] == 180

    # restore
    s.put(f"{BASE}/api/admin/pricing", json=orig)


def test_admin_costs_structure(admin):
    s, _ = admin
    r = s.get(f"{BASE}/api/admin/costs", params={"days": 60})
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("pricing", "totals", "breakdown", "tenants", "calls"):
        assert k in d
    for k in ("calls", "minutes", "total"):
        assert k in d["totals"]
    for k in ("voz", "transcripcion", "ia", "vapi", "analisis", "linea", "otros"):
        assert k in d["breakdown"]


def test_admin_costs_sync(admin):
    s, _ = admin
    r = s.post(f"{BASE}/api/admin/costs/sync")
    assert r.status_code == 200
    d = r.json()
    assert "updated" in d and "pending" in d


# ---------- Non-admin forbidden ----------
def test_non_admin_cannot_access_admin_endpoints(tenant2):
    s2, _ = tenant2
    for path in ("/api/admin/costs", "/api/admin/pricing"):
        r = s2.get(f"{BASE}{path}")
        assert r.status_code == 403, f"{path}: {r.status_code} {r.text}"
    r = s2.put(f"{BASE}/api/admin/pricing",
               json={"line_rate_usd_min": 0.03, "usd_eur": 0.91, "margin_pct": 180})
    assert r.status_code == 403
    r = s2.post(f"{BASE}/api/admin/costs/sync")
    assert r.status_code == 403


# ---------- Lead detail transcript (seed data) ----------
def test_carlos_ruiz_transcript_present(admin):
    s, _ = admin
    leads = s.get(f"{BASE}/api/leads").json()
    carlos = next(l for l in leads if l["name"] == "Carlos Ruiz")
    d = s.get(f"{BASE}/api/leads/{carlos['id']}").json()
    assert d["messages"] and len(d["messages"]) >= 2
    roles = {m["role"] for m in d["messages"]}
    assert roles & {"assistant", "agent", "user", "agente", "lead", "cliente"}


# ========================================================
# Iteration 3: Chile multi-country support (ES + CL)
# ========================================================
CL_AGENT_PAYLOAD = {**AGENT_PAYLOAD, "name": "TEST CL Agent", "country": "CL", "voice": "l_fernanda"}


@pytest.fixture()
def cl_agent(admin):
    s, _ = admin
    r = s.post(f"{BASE}/api/agents", json=CL_AGENT_PAYLOAD)
    assert r.status_code == 200, r.text
    agent = r.json()
    assert agent["country"] == "CL"
    assert agent["voice"] == "l_fernanda"
    yield agent
    s.delete(f"{BASE}/api/agents/{agent['id']}")


# ----- Register with country CL -----
def test_register_with_country_cl():
    s = requests.Session()
    email = f"cl_user_{uuid.uuid4().hex[:8]}@test.cl"
    r = s.post(f"{BASE}/api/auth/register", json={
        "name": "Test CL", "business_name": "T-CL SpA", "email": email,
        "password": "Password123!", "country": "CL"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["country"] == "CL"
    tok = data["access_token"]
    r = requests.get(f"{BASE}/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.json()["country"] == "CL"


def test_register_default_country_es():
    s = requests.Session()
    email = f"def_user_{uuid.uuid4().hex[:8]}@test.es"
    r = s.post(f"{BASE}/api/auth/register", json={
        "name": "Def", "business_name": "D SL", "email": email, "password": "Password123!"})
    assert r.status_code == 200
    assert r.json()["country"] == "ES"


# ----- PUT /api/account/country -----
def test_set_country_roundtrip(admin):
    s, me = admin
    orig = me.get("country", "ES")
    try:
        r = s.put(f"{BASE}/api/account/country", json={"country": "CL"})
        assert r.status_code == 200
        assert r.json()["country"] == "CL"
        r = s.get(f"{BASE}/api/auth/me")
        assert r.json()["country"] == "CL"
    finally:
        s.put(f"{BASE}/api/account/country", json={"country": orig})
        assert s.get(f"{BASE}/api/auth/me").json()["country"] == orig


def test_set_country_invalid(admin):
    s, _ = admin
    r = s.put(f"{BASE}/api/account/country", json={"country": "FR"})
    assert r.status_code == 422


# ----- Agent voice/country validation -----
def test_create_cl_agent_with_es_voice_rejected(admin):
    s, _ = admin
    bad = {**AGENT_PAYLOAD, "name": "TEST BadVoiceCL", "country": "CL", "voice": "p_marta"}
    r = s.post(f"{BASE}/api/agents", json=bad)
    assert r.status_code == 422


def test_create_es_agent_with_cl_voice_rejected(admin):
    s, _ = admin
    bad = {**AGENT_PAYLOAD, "name": "TEST BadVoiceES", "country": "ES", "voice": "l_fernanda"}
    r = s.post(f"{BASE}/api/agents", json=bad)
    assert r.status_code == 422


def test_create_cl_agent_with_cl_catalina_ok(admin):
    s, _ = admin
    body = {**AGENT_PAYLOAD, "name": "TEST CL Catalina", "country": "CL", "voice": "cl_catalina"}
    r = s.post(f"{BASE}/api/agents", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["country"] == "CL"
    assert r.json()["voice"] == "cl_catalina"
    s.delete(f"{BASE}/api/agents/{r.json()['id']}")


# ----- Phone validation by agent country -----
def test_test_call_wrong_country_phone(admin, cl_agent):
    s, _ = admin
    # +34 full E.164 is clearly not a CL number
    r = s.post(f"{BASE}/api/agents/{cl_agent['id']}/test-call",
               json={"phone": "+34612345678"})
    assert r.status_code == 422
    assert "Chile" in r.text or "+56" in r.text


def test_test_call_bare_digits_ambiguity_note(admin, cl_agent):
    """Documents an edge: norm_phone(bare 9 digits, 'CL') converts to +56 + digits.
    A Spanish '612345678' becomes +56612345678 and would be dialled if CL had a
    number configured. CL has no number configured here so the call is safe."""
    s, _ = admin
    # Guard: only run if CL is NOT configured
    stat = s.get(f"{BASE}/api/telephony/status").json()
    if stat["countries"]["CL"]["configured"]:
        pytest.skip("CL is live - skipping to avoid misdial risk")
    r = s.post(f"{BASE}/api/agents/{cl_agent['id']}/test-call",
               json={"phone": "612345678"})
    # Iteration 4: backend now rejects bare 9-digit as ambiguous for CL (safety fix).
    # Accept either (safe): 422 rejection OR 200 with +56 norm + 'fallida'.
    if r.status_code == 422:
        return
    assert r.status_code == 200
    assert r.json()["phone"] == "+56612345678"
    assert r.json()["status"] == "fallida"


def test_public_cl_agent_consent_false_400(cl_agent):
    r = requests.post(f"{BASE}/api/public/agents/{cl_agent['id']}/leads",
                      json={"name": "X", "phone": "+56912345678", "consent": False})
    assert r.status_code == 400


def test_public_cl_agent_spanish_phone_422(cl_agent):
    r = requests.post(f"{BASE}/api/public/agents/{cl_agent['id']}/leads",
                      json={"name": "X", "phone": "+34612345678", "consent": True})
    assert r.status_code == 422


def test_public_cl_agent_get_returns_country_and_example(cl_agent):
    r = requests.get(f"{BASE}/api/public/agents/{cl_agent['id']}")
    assert r.status_code == 200
    d = r.json()
    assert d["country"] == "CL"
    assert d["phone_example"] == "+56 9 1234 5678"


def test_public_es_agent_get_returns_country_and_example(admin, created_agent):
    r = requests.get(f"{BASE}/api/public/agents/{created_agent['id']}")
    assert r.status_code == 200
    d = r.json()
    assert d["country"] == "ES"
    assert d["phone_example"].startswith("+34")


# ----- DNC accepts both +34 and +56 -----
def test_dnc_accepts_cl_and_es(admin):
    s, _ = admin
    cl_phone = "+56912999777"
    es_phone = "+34612999777"
    created = []
    try:
        for p in (cl_phone, es_phone):
            r = s.post(f"{BASE}/api/dnc", json={"phone": p, "reason": "test"})
            assert r.status_code == 200, f"{p}: {r.text}"
            created.append(r.json()["id"])
        # Invalid
        r = s.post(f"{BASE}/api/dnc", json={"phone": "123"})
        assert r.status_code == 422
    finally:
        for i in created:
            s.delete(f"{BASE}/api/dnc/{i}")


# ----- CL agent without CL number => fallida -----
def test_cl_agent_no_number_test_call_fallida(admin, cl_agent):
    """CL has no number configured => safe to call test-call with a valid CL number.
    This must NOT place a real call and must return a lead with status 'fallida'."""
    s, _ = admin
    r = s.get(f"{BASE}/api/telephony/status")
    assert r.status_code == 200
    assert r.json()["countries"]["CL"]["configured"] is False, \
        "CL became configured - skipping to avoid real call risk"
    r = s.post(f"{BASE}/api/agents/{cl_agent['id']}/test-call",
               json={"phone": "+56912345678"})
    assert r.status_code == 200, r.text
    lead = r.json()
    assert lead["status"] == "fallida"
    err = (lead.get("error") or "") + " " + (lead.get("call_error") or "")
    # cleanup
    s_lead = s.get(f"{BASE}/api/leads/{lead['id']}")
    if s_lead.status_code == 200:
        pass  # no delete endpoint
    assert "Chile" in err or "Telefonía" in err or "sin configurar" in err.lower(), err


# ----- Telephony status -----
def test_telephony_status_has_both_countries(admin):
    s, _ = admin
    r = s.get(f"{BASE}/api/telephony/status")
    assert r.status_code == 200
    d = r.json()
    assert "ES" in d["countries"] and "CL" in d["countries"]
    es = d["countries"]["ES"]
    cl = d["countries"]["CL"]
    assert es["configured"] is True
    assert es["number"] == "+34919932652"
    assert cl["configured"] is False


# ----- Admin costs by_country structure -----
def test_admin_costs_by_country(admin):
    s, _ = admin
    r = s.get(f"{BASE}/api/admin/costs", params={"days": 60})
    assert r.status_code == 200
    d = r.json()
    assert "by_country" in d
    for c in ("ES", "CL"):
        assert c in d["by_country"]
        assert set(("calls", "minutes", "total")).issubset(d["by_country"][c].keys())
    # pricing has the new fields
    for k in ("line_rate_cl_usd_min", "usd_clp"):
        assert k in d["pricing"]


def test_admin_pricing_cl_fields_roundtrip(admin):
    s, _ = admin
    r = s.get(f"{BASE}/api/admin/pricing")
    assert r.status_code == 200
    orig = r.json()
    assert "line_rate_cl_usd_min" in orig and "usd_clp" in orig
    new = {**orig, "line_rate_cl_usd_min": 0.06, "usd_clp": 960}
    r = s.put(f"{BASE}/api/admin/pricing", json=new)
    assert r.status_code == 200
    r = s.get(f"{BASE}/api/admin/pricing")
    d = r.json()
    assert abs(d["line_rate_cl_usd_min"] - 0.06) < 1e-6
    assert d["usd_clp"] == 960
    # restore
    s.put(f"{BASE}/api/admin/pricing", json=orig)


# ----- Regression: existing ES agent 'Marta' loads/saves unchanged -----
def test_marta_agent_regression(admin):
    s, _ = admin
    agents = s.get(f"{BASE}/api/agents").json()
    marta = next((a for a in agents if a["name"] == "Marta"), None)
    if not marta:
        pytest.skip("No seeded Marta agent in this env")
    r = s.get(f"{BASE}/api/agents/{marta['id']}")
    assert r.status_code == 200
    full = r.json()
    assert full.get("country", "ES") == "ES"
    # save unchanged
    r = s.put(f"{BASE}/api/agents/{marta['id']}", json={
        "name": full["name"], "business_name": full["business_name"], "product": full["product"],
        "objective": full["objective"], "questions": full.get("questions", []),
        "country": full.get("country", "ES"), "voice": full["voice"],
        "ambience": full["ambience"], "ambience_volume": full.get("ambience_volume", 35),
        "greeting": full["greeting"], "extra_instructions": full.get("extra_instructions", ""),
        "active": full.get("active", True),
    })
    assert r.status_code == 200, r.text

