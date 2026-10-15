"""Iter-14 tests: country-scoped landing, info-request validation, vapi build_assistant.

Covers:
  * GET /api/public/geo returns a dict with 'country'
  * POST /api/public/info-request:
      - MX phone 5512345678 normalized to +525512345678
      - country=FR -> 422 Spanish message
      - DO must start 809/829/849
      - invalid short numbers -> 422
      - rate limit: 3/IP/10min -> 429
      - consent=false -> 400
      - success returns {ok, calling}
  * vapi.build_assistant: endCallPhrases = ['hasta luego'] when max_seconds <= 20
  * landing.MAX_SECONDS == 15, GREETING contains the required template
"""
import os
import sys
import time
import importlib
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    # fallback for pytest inside container
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip()
BASE_URL = BASE_URL.rstrip("/")

sys.path.insert(0, "/app/backend")

# Load backend/.env so module-level imports (db, vapi) find their env vars
with open("/app/backend/.env") as _f:
    for _line in _f:
        _line = _line.strip()
        if _line and "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))
os.environ.setdefault("VAPI_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("PUBLIC_BACKEND_URL", "https://example.com")


# ---------- Backend module import tests (no HTTP) ----------
class TestBackendModule:
    def test_landing_constants(self):
        import landing
        importlib.reload(landing)
        assert landing.MAX_SECONDS == 15
        assert "Hola {nombre}, soy {agente}, de VozLeads" in landing.GREETING
        assert "muestra" in landing.GREETING.lower()
        assert "hasta luego" in landing.GREETING.lower()

    def test_vapi_build_assistant_endcall_phrases_short(self):
        import vapi
        agent = {
            "name": "Sara", "business_name": "Clínica", "country": "ES",
            "voice": "elvira", "greeting": "Hola {nombre}, soy {agente}",
            "product": "producto", "objective": "calificar", "questions": [],
            "ambience": "none", "extra_instructions": "",
        }
        lead = {"_id": "x", "tenant_id": "t", "name": "Laura", "phone": "+34600000000",
                "greeting": "Hola {nombre}, soy {agente}, de VozLeads.",
                "max_seconds": 15, "purpose": "muestra"}
        a = vapi.build_assistant(agent, lead, "hoy es ...")
        assert a.get("endCallPhrases") == ["hasta luego"], a.get("endCallPhrases")
        assert a["maxDurationSeconds"] == 15

    def test_vapi_build_assistant_endcall_phrases_long(self):
        import vapi
        agent = {
            "name": "Sara", "business_name": "Clínica", "country": "ES",
            "voice": "elvira", "greeting": "Hola", "product": "p",
            "objective": "calificar", "questions": [], "ambience": "none",
            "extra_instructions": "",
        }
        lead = {"_id": "x", "tenant_id": "t", "name": "Laura", "phone": "+34600000000",
                "greeting": "Hola", "max_seconds": 300, "purpose": "x"}
        a = vapi.build_assistant(agent, lead, "hoy")
        assert "endCallPhrases" not in a

    def test_norm_demo_phone_mx(self):
        from countries import norm_demo_phone
        assert norm_demo_phone("5512345678", "MX") == "+525512345678"

    def test_norm_demo_phone_do_prefix(self):
        from countries import norm_demo_phone
        with pytest.raises(ValueError):
            norm_demo_phone("5551234567", "DO")  # not 809/829/849
        assert norm_demo_phone("8095551234", "DO") == "+18095551234"


# ---------- HTTP API tests ----------
@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers["Content-Type"] = "application/json"
    return s


class TestGeo:
    def test_geo_endpoint(self, client):
        r = client.get(f"{BASE_URL}/api/public/geo")
        assert r.status_code == 200
        assert "country" in r.json()


class TestInfoRequest:
    """Rate limit is 3/IP/10min; keep count low & use distinct IPs via XFF header."""

    def _post(self, client, payload, ip):
        return client.post(
            f"{BASE_URL}/api/public/info-request",
            json=payload,
            headers={"X-Forwarded-For": ip},
        )

    def test_mx_success_normalizes_phone(self, client):
        ip = f"203.0.113.{int(time.time()) % 200 + 10}"
        r = self._post(client, {
            "name": "Test User", "phone": "5512345678", "country": "MX",
            "consent": True, "page": "/mx",
        }, ip)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        assert "calling" in data

    def test_country_fr_rejected(self, client):
        ip = f"203.0.113.{(int(time.time()) + 1) % 200 + 10}"
        r = self._post(client, {
            "name": "Test", "phone": "612345678", "country": "FR",
            "consent": True, "page": "/",
        }, ip)
        assert r.status_code == 422
        detail = r.json().get("detail", "")
        assert "España" in detail or "Latinoamérica" in detail

    def test_do_wrong_prefix(self, client):
        ip = f"203.0.113.{(int(time.time()) + 2) % 200 + 10}"
        r = self._post(client, {
            "name": "Test", "phone": "5551234567", "country": "DO",
            "consent": True, "page": "/",
        }, ip)
        assert r.status_code == 422
        assert "809" in r.json().get("detail", "")

    def test_short_invalid_number(self, client):
        ip = f"203.0.113.{(int(time.time()) + 3) % 200 + 10}"
        r = self._post(client, {
            "name": "Test", "phone": "12345", "country": "MX",
            "consent": True, "page": "/",
        }, ip)
        assert r.status_code == 422

    def test_consent_required(self, client):
        ip = f"203.0.113.{(int(time.time()) + 4) % 200 + 10}"
        r = self._post(client, {
            "name": "Test", "phone": "5512345678", "country": "MX",
            "consent": False, "page": "/",
        }, ip)
        assert r.status_code == 400

    def test_rate_limit_3_per_ip(self, client):
        ip = f"203.0.113.{(int(time.time()) + 5) % 200 + 10}"
        for i in range(3):
            r = self._post(client, {
                "name": f"RL User {i}", "phone": f"551234567{i}", "country": "MX",
                "consent": True, "page": "/",
            }, ip)
            assert r.status_code == 200, f"attempt {i}: {r.status_code} {r.text}"
        r = self._post(client, {
            "name": "RL Over", "phone": "5512345670", "country": "MX",
            "consent": True, "page": "/",
        }, ip)
        assert r.status_code == 429, r.text
