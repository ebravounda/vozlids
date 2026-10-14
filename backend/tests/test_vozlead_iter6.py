"""VozLead iteration-6 tests: ElevenLabs voices, human handoff webhook,
Stripe admin settings + checkout, custom voices CRUD, voice-cost pricing fields,
and build_assistant payload shape.

Does NOT place real calls. Uses CL agents (no number configured) and in-process
unit tests for build_assistant.
"""
import os
import sys
import uuid

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else \
    os.environ["PUBLIC_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = "admin@vozlead.es"
ADMIN_PASSWORD = "VozLead2026!"
WEBHOOK_SECRET = os.environ["VAPI_WEBHOOK_SECRET"]


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    data = r.json()
    s.headers.update({"Authorization": f"Bearer {data['access_token']}"})
    me = s.get(f"{BASE}/api/auth/me").json()
    return s, me


@pytest.fixture(scope="module")
def cl_user():
    s = requests.Session()
    email = f"tb_cl_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{BASE}/api/auth/register", json={
        "name": "Biz CL", "business_name": "TEST Biz CL i6", "email": email,
        "password": "Password123!", "country": "CL"})
    assert r.status_code == 200, r.text
    data = r.json()
    s.headers.update({"Authorization": f"Bearer {data['access_token']}"})
    me = s.get(f"{BASE}/api/auth/me").json()
    yield {"session": s, "uid": me["id"], "email": email}


# ---------- ElevenLabs voices on agent ----------
class TestElevenVoices:
    def _agent_payload(self, voice, country="ES"):
        return {"name": "TEST agent", "business_name": "TEST biz", "product": "demo",
                "objective": "agendar", "questions": [], "country": country, "voice": voice,
                "ambience": "oficina", "ambience_volume": 35,
                "greeting": "Hola {nombre}, test.", "extra_instructions": "", "active": True}

    def test_create_agent_with_eleven_voice_es(self, admin):
        s, _ = admin
        r = s.post(f"{BASE}/api/agents", json=self._agent_payload("e_sarah", "ES"))
        assert r.status_code == 200, r.text
        a = r.json()
        assert a["voice"] == "e_sarah"
        # Verify persistence
        g = s.get(f"{BASE}/api/agents/{a['id']}").json()
        assert g["voice"] == "e_sarah"
        s.delete(f"{BASE}/api/agents/{a['id']}")

    def test_create_agent_with_eleven_voice_cl(self, cl_user):
        s = cl_user["session"]
        r = s.post(f"{BASE}/api/agents", json=self._agent_payload("e_chris", "CL"))
        assert r.status_code == 200, r.text
        a = r.json()
        assert a["voice"] == "e_chris"
        s.delete(f"{BASE}/api/agents/{a['id']}")

    def test_invalid_voice_returns_422(self, admin):
        s, _ = admin
        r = s.post(f"{BASE}/api/agents", json=self._agent_payload("nonexistent_voice", "ES"))
        assert r.status_code == 422, r.text

    def test_existing_agents_migrated(self, admin):
        s, _ = admin
        agents = s.get(f"{BASE}/api/agents").json()
        for a in agents:
            assert a["voice"].startswith(("e_", "x_")), f"Unmigrated voice: {a['voice']}"


# ---------- build_assistant unit test ----------
class TestBuildAssistant:
    def test_eleven_voice_shape_es(self):
        import vapi as V
        agent = {"name": "A", "business_name": "B", "product": "p", "objective": "calificar",
                 "questions": [], "country": "ES", "voice": "e_sarah", "ambience": "none",
                 "greeting": "Hola {nombre}", "extra_instructions": ""}
        lead = {"name": "Juan", "phone": "+34600111222", "email": ""}
        a = V.build_assistant(agent, lead, "Hoy es test")
        assert a["voice"]["provider"] == "11labs"
        assert a["voice"]["model"] == "eleven_turbo_v2_5"
        assert a["voice"]["language"] == "es"
        assert "fallbackPlan" in a["voice"]
        fb = a["voice"]["fallbackPlan"]["voices"][0]
        assert fb["provider"] == "cartesia"
        assert a["model"]["model"] == "gpt-4.1"
        tool_names = [t.get("function", {}).get("name") for t in a["model"]["tools"] if t.get("type") == "function"]
        assert "request_human" in tool_names
        assert a["transcriber"]["provider"] == "deepgram"
        assert a["transcriber"]["model"] == "nova-3"
        assert a["transcriber"]["language"] == "es"
        assert "startSpeakingPlan" in a
        assert "stopSpeakingPlan" in a

    def test_transcriber_cl(self):
        import vapi as V
        agent = {"name": "A", "business_name": "B", "product": "p", "objective": "calificar",
                 "questions": [], "country": "CL", "voice": "e_sarah", "ambience": "none",
                 "greeting": "Hola", "extra_instructions": ""}
        lead = {"name": "Juan", "phone": "+56912345678", "email": ""}
        a = V.build_assistant(agent, lead, "Hoy")
        assert a["transcriber"]["model"] == "nova-2"
        assert a["transcriber"]["language"] == "es-419"


# ---------- Human handoff via webhook ----------
class TestHumanHandoff:
    def test_human_tool_call_creates_ticket(self, admin):
        s, _ = admin
        # Get an existing admin lead
        leads = s.get(f"{BASE}/api/leads").json()
        assert leads, "no leads found for admin tenant"
        lead = leads[0]
        lid = lead["id"]

        before = s.get(f"{BASE}/api/support-tickets/open-count").json()
        human_before = before.get("human", 0)

        payload = {"message": {
            "type": "tool-calls",
            "call": {"metadata": {"lead_id": lid}},
            "toolCallList": [{
                "id": "t1",
                "function": {"name": "request_human",
                             "arguments": {"reason": "Quiere hablar con un comercial",
                                           "best_time": "mañana por la tarde"}}}],
        }}
        r = requests.post(f"{BASE}/api/vapi/webhook",
                          headers={"x-vapi-secret": WEBHOOK_SECRET}, json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "results" in body
        res_text = body["results"][0]["result"]
        assert "Aviso enviado" in res_text or "ok" in res_text.lower()

        after = s.get(f"{BASE}/api/support-tickets/open-count").json()
        assert after["human"] >= human_before + 1

        # Verify ticket surfaced with kind=humano and best_time
        tickets = s.get(f"{BASE}/api/support-tickets").json()
        hts = [t for t in tickets if t.get("kind") == "humano" and t.get("lead_id") == lid]
        assert hts, "No humano ticket created for lead"
        t0 = hts[0]
        assert t0.get("best_time") == "mañana por la tarde"
        assert t0.get("status") == "abierta"

        # Resolve it to clean up
        s.put(f"{BASE}/api/support-tickets/{t0['id']}/resolve")

    def test_webhook_rejects_invalid_secret(self):
        r = requests.post(f"{BASE}/api/vapi/webhook",
                          headers={"x-vapi-secret": "bad"},
                          json={"message": {"type": "status-update"}})
        assert r.status_code == 401


# ---------- Super admin Stripe settings ----------
class TestStripeAdmin:
    def test_admin_stripe_get_status(self, admin):
        s, _ = admin
        r = s.get(f"{BASE}/api/admin/stripe")
        assert r.status_code == 200, r.text
        d = r.json()
        assert "connected" in d and "mode" in d

    def test_non_admin_forbidden(self, cl_user):
        r = cl_user["session"].get(f"{BASE}/api/admin/stripe")
        assert r.status_code == 403

    def test_invalid_stripe_key_rejected(self, admin):
        s, _ = admin
        r = s.put(f"{BASE}/api/admin/stripe", json={"secret_key": "sk_test_invalid123456"})
        # Stripe should reject auth -> 400
        assert r.status_code == 400, r.text


# ---------- Custom voices CRUD ----------
class TestCustomVoices:
    def test_add_list_and_delete(self, admin, cl_user):
        s, _ = admin
        body = {"name": f"TEST_CV_{uuid.uuid4().hex[:4]}", "gender": "Mujer",
                "country": "CL", "voice_id": "AbCdEfGhIj1234567890", "tone": "cálida"}
        r = s.post(f"{BASE}/api/admin/voices", json=body)
        assert r.status_code == 200, r.text
        voice = r.json()
        vid = voice["id"]
        assert vid.startswith("x_")

        # list visible to any user
        lst = cl_user["session"].get(f"{BASE}/api/voices/custom").json()
        assert any(v["id"] == vid for v in lst)

        # delete (not used by any agent)
        r = s.delete(f"{BASE}/api/admin/voices/{vid}")
        assert r.status_code == 200

    def test_delete_in_use_blocked(self, admin):
        s, _ = admin
        # add
        body = {"name": "TEST_CV_InUse", "gender": "Hombre", "country": "ES",
                "voice_id": "ZzYyXxWwVv1234567890", "tone": ""}
        v = s.post(f"{BASE}/api/admin/voices", json=body).json()
        vid = v["id"]
        # create agent using this voice
        ap = {"name": "TEST a", "business_name": "B", "product": "demo",
              "objective": "calificar", "questions": [], "country": "ES", "voice": vid,
              "ambience": "oficina", "ambience_volume": 35,
              "greeting": "Hola {nombre}", "extra_instructions": "", "active": True}
        ag = s.post(f"{BASE}/api/agents", json=ap)
        assert ag.status_code == 200, ag.text
        try:
            r = s.delete(f"{BASE}/api/admin/voices/{vid}")
            assert r.status_code == 400
        finally:
            s.delete(f"{BASE}/api/agents/{ag.json()['id']}")
            s.delete(f"{BASE}/api/admin/voices/{vid}")

    def test_non_admin_cannot_add(self, cl_user):
        r = cl_user["session"].post(f"{BASE}/api/admin/voices", json={
            "name": "X", "gender": "Mujer", "country": "ES",
            "voice_id": "AbCdEfGhIj1234567890", "tone": ""})
        assert r.status_code == 403


# ---------- Pricing fields ----------
class TestPricingVoiceFields:
    def test_get_and_put_voice_cost_fields(self, admin):
        s, _ = admin
        cur = s.get(f"{BASE}/api/admin/pricing").json()
        for k in ("voice_11labs_usd_min", "voice_cartesia_usd_min", "voice_azure_usd_min"):
            assert k in cur
        body = {**cur, "voice_11labs_usd_min": 0.040, "voice_cartesia_usd_min": 0.025,
                "voice_azure_usd_min": 0.012}
        r = s.put(f"{BASE}/api/admin/pricing", json=body)
        assert r.status_code == 200, r.text
        after = s.get(f"{BASE}/api/admin/pricing").json()
        assert abs(after["voice_11labs_usd_min"] - 0.040) < 1e-6
        assert abs(after["voice_cartesia_usd_min"] - 0.025) < 1e-6
        assert abs(after["voice_azure_usd_min"] - 0.012) < 1e-6
        # restore
        s.put(f"{BASE}/api/admin/pricing", json=cur)

    def test_admin_costs_has_voices(self, admin):
        s, _ = admin
        d = s.get(f"{BASE}/api/admin/costs?days=30").json()
        assert "voices" in d
        for k in ("11labs", "cartesia", "azure"):
            assert k in d["voices"]
            assert "per_min" in d["voices"][k]


# ---------- Billing checkout ----------
class TestBilling:
    def test_billing_me(self, admin):
        s, _ = admin
        r = s.get(f"{BASE}/api/billing/me")
        assert r.status_code == 200, r.text
        d = r.json()
        assert "currency" in d and d["currency"] in ("EUR", "CLP")

    def test_checkout_creates_session(self, cl_user):
        s = cl_user["session"]
        plans = requests.get(f"{BASE}/api/public/plans").json()
        assert plans
        pid = plans[0]["id"]
        r = s.post(f"{BASE}/api/billing/checkout",
                   json={"plan_id": pid, "origin_url": "https://example.com"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("checkout_url", "").startswith("http")
        assert "checkout.stripe.com" in d["checkout_url"]
        sid = d["session_id"]
        # status should be pending
        st = s.get(f"{BASE}/api/billing/status/{sid}").json()
        assert st["session_id"] == sid
        assert st["payment_status"] in ("pending", "unpaid")

    def test_checkout_nonexistent_plan(self, cl_user):
        s = cl_user["session"]
        r = s.post(f"{BASE}/api/billing/checkout",
                   json={"plan_id": "507f1f77bcf86cd799439011", "origin_url": "https://example.com"})
        assert r.status_code == 404

    def test_other_user_session_404(self, admin, cl_user):
        # Create a session as CL user
        s_cl = cl_user["session"]
        plans = requests.get(f"{BASE}/api/public/plans").json()
        pid = plans[0]["id"]
        r = s_cl.post(f"{BASE}/api/billing/checkout",
                      json={"plan_id": pid, "origin_url": "https://example.com"})
        sid = r.json()["session_id"]
        # Admin querying this session -> 404
        s_adm, _ = admin
        r2 = s_adm.get(f"{BASE}/api/billing/status/{sid}")
        assert r2.status_code == 404
