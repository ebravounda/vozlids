# Iteration 39: Super admin Pagos, OpenAI settings, web scan (limits / SSRF), provisioning status for new clients
import os
import uuid
from datetime import datetime, timezone

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN = {"email": "admin@vozlead.es", "password": "VozLead2026!"}


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return s


@pytest.fixture(scope="module")
def mongo():
    env = dict(l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l)
    c = MongoClient(env["MONGO_URL"].strip('"'))
    return c[env["DB_NAME"].strip('"')]


@pytest.fixture(scope="module")
def admin():
    return _login(**ADMIN)


@pytest.fixture(scope="module")
def client(mongo):
    email = f"test_iter39_{uuid.uuid4().hex[:8]}@example.com"
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/register", json={"email": email, "password": "TestPass123!", "business_name": "TEST_Iter39 Biz",
                                                       "name": "Test Iter39", "country": "ES", "accept_terms": True})
    assert r.status_code == 200, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    s.user_id = r.json()["id"]
    s.email = email
    yield s
    mongo.users.delete_one({"email": email})
    mongo.web_scans.delete_many({"tenant_id": s.user_id})


# --- Pagos ---
class TestPayments:
    def test_payments_admin(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/payments")
        assert r.status_code == 200, r.text
        d = r.json()
        assert set(d) >= {"invoices", "accounts", "errors", "totals"}
        assert isinstance(d["accounts"], list) and len(d["accounts"]) > 0
        assert set(d["totals"]) == {"paid_month", "pending", "overdue"}
        a = d["accounts"][0]
        for k in ("id", "name", "email", "plan", "plan_id", "stripe", "sub_status", "renews"):
            assert k in a
        assert any("Stripe" in e for e in d["errors"].values()), d["errors"]

    def test_payments_non_admin_403(self, client):
        assert client.get(f"{BASE_URL}/api/admin/payments").status_code == 403
        assert client.post(f"{BASE_URL}/api/admin/payments/send-link", json={"user_id": client.user_id, "plan_id": "x"}).status_code == 403

    def test_payments_unauth_401(self):
        assert requests.get(f"{BASE_URL}/api/admin/payments").status_code == 401

    def test_send_link_unknown_account_404(self, admin):
        r = admin.post(f"{BASE_URL}/api/admin/payments/send-link", json={"user_id": "000000000000000000000000", "plan_id": "x"})
        assert r.status_code == 404

    def test_send_link_invalid_plan(self, admin, client):
        r = admin.post(f"{BASE_URL}/api/admin/payments/send-link", json={"user_id": client.user_id, "plan_id": "nope"})
        assert r.status_code == 404, r.text
        assert "Plan" in r.json()["detail"]

    def test_send_link_valid_plan(self, admin, client):
        plans = admin.get(f"{BASE_URL}/api/admin/plans").json()
        pub = [p for p in plans if p.get("public")]
        assert pub
        r = admin.post(f"{BASE_URL}/api/admin/payments/send-link", json={"user_id": client.user_id, "plan_id": pub[0]["id"]})
        print("send-link:", r.status_code, r.text[:300])
        assert r.status_code < 500, r.text
        if r.status_code == 200:
            assert r.json()["url"].startswith("http")

    def test_charge_bad_invoice(self, admin):
        r = admin.post(f"{BASE_URL}/api/admin/payments/invoices/in_doesnotexist/pay?mode=live")
        print("charge:", r.status_code, r.text[:200])
        assert r.status_code == 402


# --- OpenAI settings ---
class TestOpenAI:
    def test_status(self, admin):
        d = admin.get(f"{BASE_URL}/api/admin/openai").json()
        assert d["connected"] is True and d["model"] == "gpt-5.4-mini" and d["per_day"] == 2
        assert d["hint"].startswith("…") and len(d["hint"]) == 5

    def test_status_non_admin(self, client):
        assert client.get(f"{BASE_URL}/api/admin/openai").status_code == 403
        assert client.delete(f"{BASE_URL}/api/admin/openai").status_code == 403

    def test_save_short_key_422(self, admin):
        assert admin.put(f"{BASE_URL}/api/admin/openai", json={"api_key": "short"}).status_code == 422


# --- Web scan (no LLM cost: all rejected before calling AI) ---
class TestWebScan:
    @pytest.mark.parametrize("url", ["http://127.0.0.1:8001", "http://localhost:8001/api", "http://10.0.0.1", "http://169.254.169.254/latest/meta-data", "ftp://python.org"])
    def test_private_rejected(self, client, url):
        r = client.post(f"{BASE_URL}/api/agents/scan-website", json={"url": url})
        assert r.status_code == 400, r.text
        assert "No se pudo leer" in r.json()["detail"]

    def test_unauth(self):
        assert requests.post(f"{BASE_URL}/api/agents/scan-website", json={"url": "https://python.org"}).status_code == 401

    def test_quota_429(self, client, mongo):
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        mongo.web_scans.insert_many([{"tenant_id": client.user_id, "day": day, "url": "seed", "pages": 1, "created_at": "x"} for _ in range(2)])
        r = client.post(f"{BASE_URL}/api/agents/scan-website", json={"url": "https://www.python.org"})
        assert r.status_code == 429
        assert r.json()["detail"].startswith("Ya usaste las 2 lecturas de web de hoy")

    def test_failed_scans_dont_consume(self, client, mongo):
        # private-host failures earlier must not have been recorded
        assert mongo.web_scans.count_documents({"tenant_id": client.user_id, "url": {"$ne": "seed"}}) == 0


# --- Provisioning status for new client ---
class TestProvisioning:
    def test_my_number_status(self, client):
        r = client.get(f"{BASE_URL}/api/my-number")
        assert r.status_code == 200
        assert r.json()["status"] in ["sin_numero", "pendiente", "comprando", "error", "pendiente_documentos"], r.json()
