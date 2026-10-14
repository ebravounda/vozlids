"""Iteration-5 tests: multi-currency plans (EUR/CLP) per country.

Covers:
- GET /api/public/plans excludes private plans
- Super admin CRUD /api/admin/plans with EUR+CLP + features + public flag
- Non-admin gets 403 on /api/admin/plans
- GET /api/account/usage returns currency+price in CLP for CL users, EUR for ES
- Seeded sample plans are intact and expose price_eur/price_clp/overage_eur/overage_clp
"""
import os
import uuid

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else \
    os.environ["PUBLIC_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = "admin@vozlead.es"
ADMIN_PASSWORD = "VozLead2026!"


# ---------------- fixtures ----------------
@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    s.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    return s


def _register(country: str) -> requests.Session:
    s = requests.Session()
    email = f"tb_{country.lower()}_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{BASE}/api/auth/register", json={
        "name": "Biz", "business_name": f"TEST Biz {country}",
        "email": email, "password": "Password123!", "country": country})
    assert r.status_code == 200, r.text
    s.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    return s


@pytest.fixture(scope="module")
def cl_user():
    return _register("CL")


@pytest.fixture(scope="module")
def es_user():
    return _register("ES")


# ---------------- public plans ----------------
class TestPublicPlans:
    def test_public_plans_shape(self):
        r = requests.get(f"{BASE}/api/public/plans")
        assert r.status_code == 200
        plans = r.json()
        assert isinstance(plans, list) and len(plans) >= 3, f"expected >=3 seeded plans, got {len(plans)}"
        for p in plans:
            for k in ("id", "name", "minutes", "price_eur", "price_clp", "overage_eur", "overage_clp", "features"):
                assert k in p, f"public plan missing field {k}: {p}"
            assert isinstance(p["features"], list)
            assert p.get("public") is True

    def test_public_plans_sorted_by_minutes(self):
        plans = requests.get(f"{BASE}/api/public/plans").json()
        mins = [p["minutes"] for p in plans]
        assert mins == sorted(mins)


# ---------------- admin plan CRUD ----------------
class TestAdminPlansCRUD:
    def test_non_admin_forbidden(self, cl_user):
        r = cl_user.get(f"{BASE}/api/admin/plans")
        assert r.status_code == 403

    def test_create_update_delete_plan(self, admin):
        payload = {
            "name": "TEST_PlanCurrency", "minutes": 150,
            "price_eur": 59, "price_clp": 59000,
            "overage_eur": 0.5, "overage_clp": 500,
            "features": ["uno", "dos"], "public": True,
        }
        # CREATE
        r = admin.post(f"{BASE}/api/admin/plans", json=payload)
        assert r.status_code == 200, r.text
        pid = r.json()["id"]
        try:
            # GET verify persisted + visible on public
            all_plans = admin.get(f"{BASE}/api/admin/plans").json()
            created = next((p for p in all_plans if p["id"] == pid), None)
            assert created and created["price_eur"] == 59 and created["price_clp"] == 59000
            assert created["overage_eur"] == 0.5 and created["overage_clp"] == 500
            assert created["features"] == ["uno", "dos"]
            assert created["public"] is True
            pub = requests.get(f"{BASE}/api/public/plans").json()
            assert any(p["id"] == pid for p in pub), "public plan missing from /api/public/plans"

            # UPDATE -> public=False, change prices
            upd = {**payload, "price_eur": 69, "price_clp": 69000, "public": False, "features": ["solo"]}
            r = admin.put(f"{BASE}/api/admin/plans/{pid}", json=upd)
            assert r.status_code == 200, r.text
            fetched = next(p for p in admin.get(f"{BASE}/api/admin/plans").json() if p["id"] == pid)
            assert fetched["price_eur"] == 69 and fetched["public"] is False
            # Private plan hidden from public endpoint
            pub = requests.get(f"{BASE}/api/public/plans").json()
            assert not any(p["id"] == pid for p in pub), "private plan still visible on public endpoint"
        finally:
            r = admin.delete(f"{BASE}/api/admin/plans/{pid}")
            assert r.status_code == 200

    def test_create_plan_validation(self, admin):
        # negative price rejected
        bad = {"name": "x", "minutes": 10, "price_eur": -1, "price_clp": 100,
               "overage_eur": 0, "overage_clp": 0, "features": [], "public": True}
        r = admin.post(f"{BASE}/api/admin/plans", json=bad)
        assert r.status_code == 422


# ---------------- /api/account/usage currency ----------------
class TestAccountUsageCurrency:
    def _assign_plan(self, admin, user_session, currency_country):
        me = user_session.get(f"{BASE}/api/auth/me").json()
        uid = me["id"]
        # create a plan
        plan = admin.post(f"{BASE}/api/admin/plans", json={
            "name": f"TEST_Usage_{currency_country}", "minutes": 100,
            "price_eur": 49, "price_clp": 49000, "overage_eur": 0.4, "overage_clp": 400,
            "features": [], "public": False,
        }).json()
        r = admin.put(f"{BASE}/api/admin/users/{uid}", json={
            "plan_id": plan["id"], "allow_overage": False, "suspended": False})
        assert r.status_code == 200, r.text
        return plan, uid

    def test_cl_user_gets_clp(self, admin, cl_user):
        plan, uid = self._assign_plan(admin, cl_user, "CL")
        try:
            r = cl_user.get(f"{BASE}/api/account/usage")
            assert r.status_code == 200
            data = r.json()
            assert data["plan"] is not None
            assert data["plan"]["currency"] == "CLP"
            assert data["plan"]["price"] == 49000
            assert data["plan"]["overage_price"] == 400
        finally:
            admin.put(f"{BASE}/api/admin/users/{uid}", json={"plan_id": None, "allow_overage": False, "suspended": False})
            admin.delete(f"{BASE}/api/admin/plans/{plan['id']}")

    def test_es_user_gets_eur(self, admin, es_user):
        plan, uid = self._assign_plan(admin, es_user, "ES")
        try:
            r = es_user.get(f"{BASE}/api/account/usage")
            assert r.status_code == 200
            data = r.json()
            assert data["plan"]["currency"] == "EUR"
            assert data["plan"]["price"] == 49
            assert data["plan"]["overage_price"] == 0.4
        finally:
            admin.put(f"{BASE}/api/admin/users/{uid}", json={"plan_id": None, "allow_overage": False, "suspended": False})
            admin.delete(f"{BASE}/api/admin/plans/{plan['id']}")

    def test_usage_without_plan(self, es_user):
        # ensure no plan
        r = es_user.get(f"{BASE}/api/account/usage")
        assert r.status_code == 200
        data = r.json()
        assert data["plan"] is None
