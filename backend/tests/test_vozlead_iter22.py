"""Iter-22: Stripe test-mode admin endpoints + checkout mode routing.

Covers:
- GET /api/admin/stripe shape (test_scope, test_emails, test_key_last4 fields)
- PUT /api/admin/stripe/test-mode (off, all, emails scopes + validation)
- PUT /api/admin/stripe/test-key invalid key -> 422
- Business user checkout uses sk_test_emergent proxy when scope=all -> returns checkout_url
- Non-admin users forbidden on admin endpoints
"""
import os
import re
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN = {"email": "admin@vozlead.es", "password": "VozLead2026!"}

# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return s


@pytest.fixture(scope="module")
def business_client():
    """Register a throwaway business user and return an authenticated session."""
    s = requests.Session()
    suffix = uuid.uuid4().hex[:8]
    email = f"TEST_stripe_{suffix}@vozlead-test.es"
    payload = {
        "name": "Test User",
        "first_name": "Test",
        "last_name": "User",
        "business_name": f"TEST biz {suffix}",
        "email": email,
        "password": "Password123!",
        "country": "ES",
        "doc_type": "DNI",
        "doc_number": "12345678Z",
        "billing_address": {"line": "C/ Test 1", "street": "C/ Test 1", "city": "Madrid", "postal_code": "28001", "country": "ES"},
    }
    r = s.post(f"{BASE_URL}/api/auth/register", json=payload, timeout=15)
    assert r.status_code == 200, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    s.test_email = email
    return s


@pytest.fixture(scope="module", autouse=True)
def restore_stripe_settings(admin_client):
    """Snapshot platform_settings/stripe before tests and restore after."""
    cli = MongoClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    original = db.platform_settings.find_one({"_id": "stripe"})
    yield
    if original is not None:
        db.platform_settings.replace_one({"_id": "stripe"}, original, upsert=True)
    else:
        db.platform_settings.delete_one({"_id": "stripe"})
    # cleanup test users
    db.users.delete_many({"email": {"$regex": "^TEST_stripe_"}})
    cli.close()


# ---------- admin status ----------
def test_admin_stripe_status_shape(admin_client):
    r = admin_client.get(f"{BASE_URL}/api/admin/stripe", timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    for k in ("connected", "mode", "test_connected", "test_scope", "test_emails"):
        assert k in body, f"missing key {k}: {body}"
    assert isinstance(body["test_emails"], list)
    assert body["test_scope"] in ("off", "all", "emails")


def test_admin_stripe_requires_admin(business_client):
    r = business_client.get(f"{BASE_URL}/api/admin/stripe", timeout=10)
    assert r.status_code in (401, 403)


# ---------- test-mode scope ----------
def test_set_test_mode_off(admin_client):
    r = admin_client.put(f"{BASE_URL}/api/admin/stripe/test-mode",
                         json={"scope": "off", "emails": []}, timeout=10)
    assert r.status_code == 200, r.text
    assert r.json()["test_scope"] == "off"


def test_set_test_mode_emails_requires_list(admin_client):
    r = admin_client.put(f"{BASE_URL}/api/admin/stripe/test-mode",
                         json={"scope": "emails", "emails": []}, timeout=10)
    assert r.status_code == 422
    assert "pruebas" in r.text.lower() or "email" in r.text.lower()


def test_set_test_mode_emails_persisted_and_lowercased(admin_client):
    r = admin_client.put(f"{BASE_URL}/api/admin/stripe/test-mode",
                         json={"scope": "emails", "emails": ["QA@Example.com", "ignored-no-at", "QA@Example.com"]},
                         timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["test_scope"] == "emails"
    assert body["test_emails"] == ["qa@example.com"]
    # GET returns same
    g = admin_client.get(f"{BASE_URL}/api/admin/stripe").json()
    assert g["test_emails"] == ["qa@example.com"]


def test_set_test_mode_all(admin_client):
    r = admin_client.put(f"{BASE_URL}/api/admin/stripe/test-mode",
                         json={"scope": "all", "emails": []}, timeout=10)
    assert r.status_code == 200
    assert r.json()["test_scope"] == "all"


def test_test_mode_invalid_scope(admin_client):
    r = admin_client.put(f"{BASE_URL}/api/admin/stripe/test-mode",
                         json={"scope": "bogus", "emails": []}, timeout=10)
    assert r.status_code == 422


def test_test_mode_requires_admin(business_client):
    r = business_client.put(f"{BASE_URL}/api/admin/stripe/test-mode",
                            json={"scope": "off", "emails": []}, timeout=10)
    assert r.status_code in (401, 403)


# ---------- test-key endpoint ----------
def test_test_key_rejects_live_key(admin_client):
    r = admin_client.put(f"{BASE_URL}/api/admin/stripe/test-key",
                         json={"secret_key": "sk_live_abcdefghijkl"}, timeout=15)
    assert r.status_code == 422
    assert "sk_test_" in r.text


def test_test_key_rejects_too_short(admin_client):
    r = admin_client.put(f"{BASE_URL}/api/admin/stripe/test-key",
                         json={"secret_key": "short"}, timeout=10)
    assert r.status_code == 422


def test_test_key_requires_admin(business_client):
    r = business_client.put(f"{BASE_URL}/api/admin/stripe/test-key",
                            json={"secret_key": "sk_test_" + "x" * 20}, timeout=10)
    assert r.status_code in (401, 403)


# ---------- checkout routing via proxy ----------
def test_checkout_uses_test_mode_proxy_when_scope_all(admin_client, business_client):
    """With scope=all and no own Stripe key, checkout uses sk_test_emergent proxy and returns a URL."""
    # Ensure scope=all
    assert admin_client.put(f"{BASE_URL}/api/admin/stripe/test-mode",
                            json={"scope": "all", "emails": []}, timeout=10).status_code == 200
    # Find a public plan priced in EUR
    plans = requests.get(f"{BASE_URL}/api/public/plans?country=ES", timeout=10).json()
    assert isinstance(plans, list) and plans, plans
    plan_id = plans[0]["id"]
    r = business_client.post(f"{BASE_URL}/api/billing/checkout",
                             json={"plan_id": plan_id, "origin_url": BASE_URL, "signup": False},
                             timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("checkout_url", "").startswith("https://"), body
    assert body.get("session_id", "").startswith("cs_"), body


def test_checkout_scope_emails_matches_user(admin_client, business_client):
    """When scope=emails includes our user, checkout succeeds via test proxy."""
    email = business_client.test_email
    r = admin_client.put(f"{BASE_URL}/api/admin/stripe/test-mode",
                         json={"scope": "emails", "emails": [email]}, timeout=10)
    assert r.status_code == 200
    plans = requests.get(f"{BASE_URL}/api/public/plans?country=ES", timeout=10).json()
    plan_id = plans[0]["id"]
    r2 = business_client.post(f"{BASE_URL}/api/billing/checkout",
                              json={"plan_id": plan_id, "origin_url": BASE_URL},
                              timeout=20)
    assert r2.status_code == 200, r2.text
    assert r2.json()["session_id"].startswith("cs_")
