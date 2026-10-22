# Iteration 43: browser dialer (Teléfono) - plan gating, session, history, regressions
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN = {"email": "admin@vozlead.es", "password": "VozLead2026!"}


def login(creds):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=creds)
    assert r.status_code == 200, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return s


@pytest.fixture(scope="module")
def admin():
    return login(ADMIN)


@pytest.fixture(scope="module")
def plans(admin):
    r = admin.get(f"{BASE_URL}/api/admin/plans")
    assert r.status_code == 200
    return r.json()


@pytest.fixture(scope="module")
def client_user(admin, plans):
    email = f"test_dialer_{uuid.uuid4().hex[:8]}@example.com"
    creds = {"email": email, "password": "TestPass123!"}
    r = requests.post(f"{BASE_URL}/api/auth/register", json={**creds, "name": "TEST Dialer", "business_name": "TEST Biz"})
    assert r.status_code in (200, 201), r.text
    s = login(creds)
    uid = s.get(f"{BASE_URL}/api/auth/me").json()["id"]
    yield {"s": s, "id": uid, "creds": creds}
    admin.delete(f"{BASE_URL}/api/admin/users/{uid}")


# Admin dialer
class TestAdminDialer:
    def test_info(self, admin):
        r = admin.get(f"{BASE_URL}/api/dialer")
        assert r.status_code == 200
        d = r.json()
        assert d["enabled"] is True
        assert "+34919932652" in d["numbers"]

    def test_session_zadarma_not_configured(self, admin):
        r = admin.post(f"{BASE_URL}/api/dialer/session", json={"number": "+34919932652"})
        assert r.status_code == 400, r.text
        assert "No se pudo preparar el teléfono" in r.json()["detail"]
        assert "Zadarma" in r.json()["detail"]

    def test_session_unknown_number_falls_back(self, admin):
        r = admin.post(f"{BASE_URL}/api/dialer/session", json={"number": "+000"})
        assert r.status_code == 400

    def test_history(self, admin):
        r = admin.get(f"{BASE_URL}/api/dialer/history")
        assert r.status_code == 200
        d = r.json()
        assert d["calls"] == [] and d["minutes"] == 0

    def test_unauth(self):
        assert requests.get(f"{BASE_URL}/api/dialer").status_code == 401


# Client gating via plan
class TestClientGating:
    def test_no_plan_user_dialer_state(self, client_user):
        # report: new users w/o plan get DEFAULT (all True) -> dialer enabled?
        r = client_user["s"].get(f"{BASE_URL}/api/dialer")
        assert r.status_code == 200
        print("NO-PLAN user dialer enabled:", r.json())
        assert r.json()["enabled"] is False, "User without plan has dialer enabled (DEFAULT all True)"

    def test_plan_without_dialer_locked(self, admin, plans, client_user):
        plan = next(p for p in plans if not (p.get("limits") or {}).get("dialer"))
        assert admin.put(f"{BASE_URL}/api/admin/users/{client_user['id']}", json={"plan_id": plan["id"]}).status_code == 200
        s = client_user["s"]
        assert s.get(f"{BASE_URL}/api/dialer").json()["enabled"] is False
        r = s.get(f"{BASE_URL}/api/dialer/history")
        assert r.status_code == 403 and "teléfono en el panel" in r.json()["detail"]
        r = s.post(f"{BASE_URL}/api/dialer/session", json={})
        assert r.status_code == 403
        u = s.get(f"{BASE_URL}/api/account/usage").json()
        assert u["limits"]["dialer"] is False

    def test_plan_toggle_dialer_persists(self, admin, plans, client_user):
        plan = next(p for p in plans if not (p.get("limits") or {}).get("dialer"))
        orig_limits = dict(plan.get("limits") or {})
        body = {k: v for k, v in plan.items() if k not in ("id", "created_at")}
        try:
            body["limits"] = {**orig_limits, "dialer": True}
            r = admin.put(f"{BASE_URL}/api/admin/plans/{plan['id']}", json=body)
            assert r.status_code == 200, r.text
            got = next(p for p in admin.get(f"{BASE_URL}/api/admin/plans").json() if p["id"] == plan["id"])
            assert got["limits"]["dialer"] is True
            s = client_user["s"]
            assert s.get(f"{BASE_URL}/api/dialer").json()["enabled"] is True
            r = s.get(f"{BASE_URL}/api/dialer/history")
            assert r.status_code == 200
            r = s.post(f"{BASE_URL}/api/dialer/session", json={})
            assert r.status_code == 400 and "número activo" in r.json()["detail"]
            body["limits"] = {**orig_limits, "dialer": False}
            assert admin.put(f"{BASE_URL}/api/admin/plans/{plan['id']}", json=body).status_code == 200
            got = next(p for p in admin.get(f"{BASE_URL}/api/admin/plans").json() if p["id"] == plan["id"])
            assert got["limits"]["dialer"] is False
        finally:
            body["limits"] = orig_limits
            # restore exactly original limits dict (may be {})
            from pymongo import MongoClient  # noqa
        admin.put(f"{BASE_URL}/api/admin/users/{client_user['id']}", json={"plan_id": None})


# Regressions
class TestRegression:
    def test_zadarma_compare(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/costs/zadarma-compare")
        assert r.status_code == 200

    def test_usage_limits_has_dialer(self, admin):
        r = admin.get(f"{BASE_URL}/api/account/usage")
        assert r.status_code == 200 and "dialer" in r.json()["limits"]
