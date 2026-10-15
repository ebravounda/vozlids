"""Iter-17: Super Admin monitoring endpoints and Resend settings regression."""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ai-voice-caller-2.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_EMAIL = "admin@vozlead.es"
ADMIN_PASS = "VozLead2026!"


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def user_headers():
    suffix = uuid.uuid4().hex[:8]
    email = f"TEST_iter17_{suffix}@example.com"
    r = requests.post(f"{API}/auth/register", json={
        "name": "Iter17", "business_name": "Iter17 Co", "email": email, "password": "SuperStrong!23"}, timeout=30)
    assert r.status_code in (200, 201), r.text
    tok = r.json().get("access_token")
    assert tok
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ---------- auth guards ----------
class TestAuthGuards:
    @pytest.mark.parametrize("path", [
        "/admin/monitor/balances", "/admin/monitor/live", "/admin/monitor/margins",
        "/admin/monitor/alerts", "/admin/monitor/sip-calls", "/admin/resend", "/admin/costs",
    ])
    def test_requires_auth(self, path):
        r = requests.get(f"{API}{path}", timeout=30)
        assert r.status_code in (401, 403), f"{path} -> {r.status_code}"

    @pytest.mark.parametrize("path", [
        "/admin/monitor/balances", "/admin/monitor/live", "/admin/monitor/margins",
        "/admin/monitor/alerts", "/admin/monitor/sip-calls", "/admin/resend",
    ])
    def test_non_admin_forbidden(self, user_headers, path):
        r = requests.get(f"{API}{path}", headers=user_headers, timeout=30)
        assert r.status_code == 403, f"{path} -> {r.status_code}"


# ---------- monitor read endpoints ----------
class TestMonitorRead:
    def test_balances_structure(self, admin_headers):
        r = requests.get(f"{API}/admin/monitor/balances", headers=admin_headers, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("sip", "voice", "ai", "stripe", "checked_at"):
            assert k in d, f"missing {k}"
        assert isinstance(d["sip"].get("connected"), bool)
        assert isinstance(d["voice"].get("connected"), bool)
        # Zadarma not configured in preview -> expect disconnected (connected False)
        assert d["sip"]["connected"] is False or "balance" in d["sip"] or "error" in d["sip"]

    def test_balances_fresh(self, admin_headers):
        r = requests.get(f"{API}/admin/monitor/balances?fresh=true", headers=admin_headers, timeout=60)
        assert r.status_code == 200
        assert "checked_at" in r.json()

    def test_live(self, admin_headers):
        r = requests.get(f"{API}/admin/monitor/live", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "active" in d and isinstance(d["active"], list)
        assert "limit" in d and isinstance(d["limit"], int)
        assert "checked_at" in d

    def test_margins(self, admin_headers):
        r = requests.get(f"{API}/admin/monitor/margins", headers=admin_headers, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "rows" in d and isinstance(d["rows"], list)
        assert "since" in d
        for row in d["rows"]:
            for k in ("tenant_id", "business", "calls", "minutes", "cost", "revenue", "margin"):
                assert k in row

    def test_sip_calls_graceful_without_zadarma(self, admin_headers):
        r = requests.get(f"{API}/admin/monitor/sip-calls?days=7", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "calls" in d and "total" in d and "count" in d
        # Zadarma not configured -> should contain "error" field, no crash
        if not d["calls"]:
            # tolerant: either empty + error or empty + 0 count
            assert d["count"] == 0


# ---------- alerts ----------
class TestAlerts:
    def test_get_alerts(self, admin_headers):
        r = requests.get(f"{API}/admin/monitor/alerts", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "settings" in d and "recent" in d
        for k in ("email", "enabled", "sip_min", "voice_min_pct"):
            assert k in d["settings"]

    def test_put_alerts_invalid_email(self, admin_headers):
        r = requests.put(f"{API}/admin/monitor/alerts", headers=admin_headers,
                         json={"email": "not-an-email", "enabled": True, "sip_min": 2.0, "voice_min_pct": 2.0}, timeout=30)
        assert r.status_code == 422, r.text

    def test_put_alerts_valid_persists(self, admin_headers):
        payload = {"email": "alerts-test@example.com", "enabled": True, "sip_min": 3.5, "voice_min_pct": 7.0}
        r = requests.put(f"{API}/admin/monitor/alerts", headers=admin_headers, json=payload, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["email"] == payload["email"]
        assert d["sip_min"] == 3.5
        assert d["voice_min_pct"] == 7.0
        assert d["enabled"] is True
        # verify via GET
        g = requests.get(f"{API}/admin/monitor/alerts", headers=admin_headers, timeout=30).json()
        assert g["settings"]["email"] == payload["email"]
        assert g["settings"]["sip_min"] == 3.5
        # restore default-ish
        requests.put(f"{API}/admin/monitor/alerts", headers=admin_headers,
                     json={"email": "", "enabled": True, "sip_min": 2.0, "voice_min_pct": 2.0}, timeout=30)

    def test_put_alerts_bounds(self, admin_headers):
        # voice_min_pct > 100 should 422
        r = requests.put(f"{API}/admin/monitor/alerts", headers=admin_headers,
                         json={"email": "", "enabled": True, "sip_min": 2.0, "voice_min_pct": 200}, timeout=30)
        assert r.status_code == 422

    def test_check_runs(self, admin_headers):
        r = requests.post(f"{API}/admin/monitor/check", headers=admin_headers, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "settings" in d and "recent" in d


# ---------- resend ----------
class TestResend:
    def test_initial_status(self, admin_headers):
        r = requests.get(f"{API}/admin/resend", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        # Never returns full key
        assert "api_key" not in d
        assert set(d.keys()) >= {"connected", "key_last4", "from_email", "reply_to"}

    def test_save_bad_key(self, admin_headers):
        r = requests.put(f"{API}/admin/resend", headers=admin_headers,
                         json={"api_key": "wrong_prefix_123456", "from_email": "a@b.com", "reply_to": ""}, timeout=30)
        assert r.status_code == 422
        assert "re_" in r.text

    def test_save_bad_from(self, admin_headers):
        r = requests.put(f"{API}/admin/resend", headers=admin_headers,
                         json={"api_key": "re_test_12345678", "from_email": "no-at-sign", "reply_to": ""}, timeout=30)
        assert r.status_code == 422

    def test_save_valid_then_test_then_delete(self, admin_headers):
        # Save valid-shape (fake) key
        r = requests.put(f"{API}/admin/resend", headers=admin_headers,
                         json={"api_key": "re_test_12345678", "from_email": "avisos@example.com", "reply_to": ""},
                         timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["connected"] is True
        assert d["key_last4"] == "5678"
        assert d["from_email"] == "avisos@example.com"
        assert "api_key" not in d
        # GET also hides full key
        g = requests.get(f"{API}/admin/resend", headers=admin_headers, timeout=30).json()
        assert g["connected"] is True
        assert g["key_last4"] == "5678"
        assert "api_key" not in g
        # POST test should 502 with Resend error (fake key)
        t = requests.post(f"{API}/admin/resend/test", headers=admin_headers, timeout=60)
        assert t.status_code == 502, t.text
        # DELETE disconnect
        d = requests.delete(f"{API}/admin/resend", headers=admin_headers, timeout=30)
        assert d.status_code == 200
        g2 = requests.get(f"{API}/admin/resend", headers=admin_headers, timeout=30).json()
        assert g2["connected"] is False


# ---------- regression ----------
class TestRegression:
    def test_admin_costs_new_fields(self, admin_headers):
        r = requests.get(f"{API}/admin/costs?days=7", headers=admin_headers, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "calls" in d and isinstance(d["calls"], list)
        # If any calls, ensure new fields exist on each row
        for row in d["calls"][:50]:
            for k in ("phone", "direction", "ended_reason", "tenant_id"):
                assert k in row, f"missing {k} in call row"
            assert row["direction"] in ("entrante", "saliente")

    def test_admin_costs_tenant_filter(self, admin_headers):
        # Grab an id from margins or costs, if any
        c = requests.get(f"{API}/admin/costs?days=30", headers=admin_headers, timeout=60).json()
        tid = (c.get("tenants") or [{}])[0].get("tenant_id")
        if not tid:
            pytest.skip("no tenants with calls")
        r = requests.get(f"{API}/admin/costs?days=30&tenant_id={tid}", headers=admin_headers, timeout=60)
        assert r.status_code == 200
        for row in r.json().get("calls", []):
            assert row["tenant_id"] == tid

    @pytest.mark.parametrize("path", [
        "/api/ambience/oficina_real/35.wav",
        "/api/ambience/call_center/35.wav",
    ])
    def test_ambience(self, path):
        r = requests.get(f"{BASE_URL}{path}", timeout=30)
        assert r.status_code == 200, f"{path} -> {r.status_code}"
        assert r.headers.get("content-type", "").startswith("audio/")
