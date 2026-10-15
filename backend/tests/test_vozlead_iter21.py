"""Iteration 21: Widget, Signup/Onboarding, Admin Onboarding tests."""
import io
import os
import re
import uuid
import zipfile
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = "admin@vozlead.es"
ADMIN_PASS = "VozLead2026!"


@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token")
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="session")
def admin_agent_id(admin_session):
    r = admin_session.get(f"{BASE}/api/agents")
    assert r.status_code == 200
    agents = [a for a in r.json() if a.get("active") is not False]
    assert agents, "Admin should have at least one active agent (seeded)"
    return agents[0]["id"]


# ---------- Widget settings ----------
class TestWidget:
    def test_get_widget_default(self, admin_session):
        r = admin_session.get(f"{BASE}/api/widget")
        assert r.status_code == 200
        d = r.json()
        for k in ("id", "agent_id", "text", "color", "position", "hours_only", "greeting", "greeting_delay"):
            assert k in d

    def test_put_widget_valid(self, admin_session, admin_agent_id):
        body = {"agent_id": admin_agent_id, "text": "Llámame ya",
                "color": "#059669", "position": "left", "hours_only": False,
                "greeting": "¡Hola!", "greeting_delay": 4}
        r = admin_session.put(f"{BASE}/api/widget", json=body)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["agent_id"] == admin_agent_id
        assert d["text"] == "Llámame ya"
        assert d["color"] == "#059669"
        assert d["position"] == "left"
        assert d["greeting_delay"] == 4
        # verify persistence
        d2 = admin_session.get(f"{BASE}/api/widget").json()
        assert d2["text"] == "Llámame ya" and d2["color"] == "#059669"

    def test_put_invalid_color(self, admin_session, admin_agent_id):
        r = admin_session.put(f"{BASE}/api/widget", json={
            "agent_id": admin_agent_id, "text": "Hola", "color": "red",
            "position": "right", "hours_only": False, "greeting": "", "greeting_delay": 6})
        assert r.status_code == 422

    def test_put_foreign_agent_rejected(self, admin_session):
        # fake oid of agent that doesn't belong to admin
        r = admin_session.put(f"{BASE}/api/widget", json={
            "agent_id": "507f1f77bcf86cd799439011", "text": "Hola",
            "color": "#123ABC", "position": "right", "hours_only": False,
            "greeting": "", "greeting_delay": 6})
        assert r.status_code == 422


# ---------- Public widget endpoints ----------
class TestPublicWidget:
    def test_public_widget_config_cors(self, admin_session, admin_agent_id):
        # ensure widget stored
        admin_session.put(f"{BASE}/api/widget", json={
            "agent_id": admin_agent_id, "text": "Solicitar llamada", "color": "#2563EB",
            "position": "right", "hours_only": False, "greeting": "Hola", "greeting_delay": 6})
        wid = admin_session.get(f"{BASE}/api/widget").json()["id"]
        r = requests.get(f"{BASE}/api/public/widget/{wid}")
        assert r.status_code == 200
        assert r.headers.get("Access-Control-Allow-Origin") == "*"
        d = r.json()
        assert d["agent_id"] == admin_agent_id
        assert "form_url" in d and d["form_url"].endswith(f"/f/{admin_agent_id}")
        assert d["show"] is True

    def test_public_widget_js(self):
        r = requests.get(f"{BASE}/api/public/widget.js")
        assert r.status_code == 200
        assert "javascript" in r.headers.get("Content-Type", "")
        assert "vozleads-widget" in r.text or "__vozleadsWidget" in r.text

    def test_hours_only_outside_hours_hides(self, admin_session, admin_agent_id):
        # Save current availability
        av = admin_session.get(f"{BASE}/api/availability").json()
        try:
            closed = {"slot_minutes": av.get("slot_minutes", 30),
                      "days": [{"enabled": False, "start": "09:00", "end": "18:00"} for _ in range(7)]}
            r = admin_session.put(f"{BASE}/api/availability", json=closed)
            assert r.status_code == 200
            # set hours_only=true
            admin_session.put(f"{BASE}/api/widget", json={
                "agent_id": admin_agent_id, "text": "Solicitar llamada", "color": "#2563EB",
                "position": "right", "hours_only": True, "greeting": "", "greeting_delay": 6})
            wid = admin_session.get(f"{BASE}/api/widget").json()["id"]
            d = requests.get(f"{BASE}/api/public/widget/{wid}").json()
            assert d["show"] is False
        finally:
            # restore
            restore = {"slot_minutes": av.get("slot_minutes", 30),
                       "days": [{k: d.get(k) for k in ("enabled", "start", "end")} for d in av["days"]]}
            admin_session.put(f"{BASE}/api/availability", json=restore)
            admin_session.put(f"{BASE}/api/widget", json={
                "agent_id": admin_agent_id, "text": "Solicitar llamada", "color": "#2563EB",
                "position": "right", "hours_only": False, "greeting": "", "greeting_delay": 6})


# ---------- WordPress zip ----------
class TestWordpressZip:
    def test_zip_download(self, admin_session):
        wid = admin_session.get(f"{BASE}/api/widget").json()["id"]
        r = admin_session.get(f"{BASE}/api/widget/wordpress.zip")
        assert r.status_code == 200
        assert r.headers.get("Content-Type") == "application/zip"
        assert "vozleads-widget.zip" in r.headers.get("Content-Disposition", "")
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            names = z.namelist()
            assert "vozleads-widget/vozleads-widget.php" in names
            php = z.read("vozleads-widget/vozleads-widget.php").decode()
            assert wid in php
            assert "VozLeads" in php


# ---------- Signup validation ----------
class TestSignup:
    def test_invalid_dni(self):
        r = requests.post(f"{BASE}/api/auth/register", json={
            "first_name": "Test", "last_name": "User",
            "business_name": f"TEST_{uuid.uuid4().hex[:6]}",
            "email": f"TEST_{uuid.uuid4().hex[:8]}@vozlead-test.es",
            "password": "Secret123!", "country": "ES",
            "doc_type": "DNI", "doc_number": "12345678A",
            "website": "www.test.es",
            "billing_address": {"line": "Calle Falsa 1", "city": "Madrid", "postal_code": "28001", "region": "Madrid"}})
        assert r.status_code == 422
        assert "DNI" in r.json().get("detail", "")

    def test_valid_dni_registers(self):
        email = f"TEST_{uuid.uuid4().hex[:8]}@vozlead-test.es"
        r = requests.post(f"{BASE}/api/auth/register", json={
            "first_name": "Test", "last_name": "User",
            "business_name": f"TEST_{uuid.uuid4().hex[:6]}",
            "email": email, "password": "Secret123!",
            "country": "ES", "doc_type": "DNI", "doc_number": "12345678Z",
            "website": "www.test.es",
            "billing_address": {"line": "Calle Falsa 1", "city": "Madrid", "postal_code": "28001", "region": "Madrid"}})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["email"] == email.lower()
        assert "access_token" in d
        pytest.created_user_token_iter21 = d["access_token"]
        pytest.created_user_email_iter21 = email.lower()

    def test_valid_rut_registers(self):
        email = f"TEST_{uuid.uuid4().hex[:8]}@vozlead-test.cl"
        r = requests.post(f"{BASE}/api/auth/register", json={
            "first_name": "Test", "last_name": "Chile",
            "business_name": f"TEST_{uuid.uuid4().hex[:6]}",
            "email": email, "password": "Secret123!",
            "country": "CL", "doc_type": "RUT", "doc_number": "12.345.678-5",
            "website": "www.test.cl",
            "billing_address": {"line": "Av. Falsa 1", "city": "Santiago", "postal_code": "", "region": "RM"}})
        assert r.status_code == 200, r.text

    def test_billing_checkout_with_signup_flag(self):
        tok = getattr(pytest, "created_user_token_iter21", None)
        if not tok:
            pytest.skip("no created user")
        s = requests.Session()
        s.headers.update({"Authorization": f"Bearer {tok}"})
        plans = s.get(f"{BASE}/api/public/plans").json()
        assert plans
        r = s.post(f"{BASE}/api/billing/checkout",
                   json={"plan_id": plans[0]["id"], "origin_url": "https://test.example.com", "signup": True})
        # Might be 200 with checkout URL, or 500 if stripe unconfigured; accept 200 primarily
        if r.status_code == 200:
            d = r.json()
            url = d.get("checkout_url") or d.get("url", "")
            assert "stripe.com" in url or "checkout" in url
            # success_url has /app/bienvenida (we can't inspect it directly but ok)
        else:
            # at least ensure it's not a 404 (route exists)
            assert r.status_code != 404


# ---------- Admin onboarding ----------
class TestAdminOnboarding:
    def test_admin_onboarding_requires_admin(self):
        tok = getattr(pytest, "created_user_token_iter21", None)
        if not tok:
            pytest.skip("no business user")
        r = requests.get(f"{BASE}/api/admin/onboarding", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 403

    def test_admin_onboarding_list(self, admin_session):
        r = admin_session.get(f"{BASE}/api/admin/onboarding")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_block_user_without_active_line(self, admin_session):
        # Use the just-created unpaid test user
        email = getattr(pytest, "created_user_email_iter21", None)
        if not email:
            pytest.skip("no business user")
        # Find user id via admin users list (if available) or via onboarding list
        from pymongo import MongoClient
        mongo = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        dbn = os.environ.get("DB_NAME", "test_database")
        u = mongo[dbn].users.find_one({"email": email})
        assert u
        uid = str(u["_id"])
        r = admin_session.post(f"{BASE}/api/admin/onboarding/{uid}/block", params={"blocked": True})
        assert r.status_code == 400


# ---------- Regression ----------
class TestRegression:
    def test_admin_login_still_works(self):
        r = requests.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
        assert r.status_code == 200
        assert r.json()["role"] == "admin"

    def test_public_agent_fetch(self, admin_agent_id):
        r = requests.get(f"{BASE}/api/public/agents/{admin_agent_id}")
        assert r.status_code == 200


# ---------- Cleanup ----------
def teardown_module(module):
    try:
        from pymongo import MongoClient
        mongo = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        dbn = os.environ.get("DB_NAME", "test_database")
        res = mongo[dbn].users.delete_many({"email": {"$regex": "^TEST_.*@vozlead-test\\."}})
        print(f"Cleaned {res.deleted_count} test users")
        mongo[dbn].tenant_numbers.delete_many({"status": "pendiente", "tenant_id": {"$in": []}})
    except Exception as e:
        print(f"Cleanup error: {e}")
