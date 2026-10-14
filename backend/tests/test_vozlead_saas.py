"""VozLead SaaS iteration-4 regression tests: plans, impersonation, usage,
support tickets, outbound templates+scheduler, cron auth, public v1 API.

Safety: never place real calls. Spain is live; we only use CL agents (CL unconfigured)
and public endpoints with scheduled_at future.
"""
import os
import uuid
from datetime import datetime, timedelta

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else \
    os.environ["PUBLIC_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = "admin@vozlead.es"
ADMIN_PASSWORD = "VozLead2026!"
WEBHOOK_SECRET = os.environ["VAPI_WEBHOOK_SECRET"]
CRON_SECRET = os.environ["WEBHOOK_CRON_SECRET"]
VAPI_PHONE = os.environ.get("VAPI_PHONE_NUMBER_ID", "")


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    data = r.json()
    s.headers.update({"Authorization": f"Bearer {data['access_token']}"})
    return s, data


@pytest.fixture(scope="module")
def test_business():
    """Fresh CL tenant with one CL agent (CL has no number configured → safe)."""
    s = requests.Session()
    email = f"tb_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{BASE}/api/auth/register", json={
        "name": "Biz User", "business_name": "TEST Biz CL", "email": email,
        "password": "Password123!", "country": "CL"})
    assert r.status_code == 200, r.text
    data = r.json()
    s.headers.update({"Authorization": f"Bearer {data['access_token']}"})
    agent_payload = {
        "name": "TEST Saas CL Agent", "business_name": "TEST Biz CL",
        "product": "demo", "objective": "agendar",
        "questions": ["¿Qué necesitas?"], "country": "CL", "voice": "l_fernanda",
        "ambience": "oficina", "ambience_volume": 35,
        "greeting": "Hola {nombre}, llamada de prueba.", "extra_instructions": "",
        "active": True,
    }
    r = s.post(f"{BASE}/api/agents", json=agent_payload)
    assert r.status_code == 200, r.text
    agent = r.json()
    uid = data["id"] if "id" in data else data.get("user_id")
    # fetch /me to get id reliably
    me = s.get(f"{BASE}/api/auth/me").json()
    yield {"session": s, "email": email, "uid": me["id"], "agent": agent}
    # cleanup
    s.delete(f"{BASE}/api/agents/{agent['id']}")


# ---------- Plans CRUD / 403 for non-admin ----------
class TestPlans:
    def test_create_list_assign_blocked_delete(self, admin, test_business):
        s, _ = admin
        body = {"name": f"TEST Plan {uuid.uuid4().hex[:4]}", "minutes": 10,
                "price": 29.0, "currency": "EUR", "overage_price": 0.5}
        r = s.post(f"{BASE}/api/admin/plans", json=body)
        assert r.status_code == 200, r.text
        plan = r.json()
        pid = plan["id"]
        assert plan["minutes"] == 10 and plan["currency"] == "EUR"

        plans = s.get(f"{BASE}/api/admin/plans").json()
        assert any(p["id"] == pid for p in plans)

        # Assign to test business
        r = s.put(f"{BASE}/api/admin/users/{test_business['uid']}",
                  json={"plan_id": pid, "allow_overage": False, "suspended": False})
        assert r.status_code == 200

        # Deleting assigned plan -> 400
        r = s.delete(f"{BASE}/api/admin/plans/{pid}")
        assert r.status_code == 400

        # Unassign
        r = s.put(f"{BASE}/api/admin/users/{test_business['uid']}",
                  json={"plan_id": None, "allow_overage": False, "suspended": False})
        assert r.status_code == 200

        # Now delete OK
        r = s.delete(f"{BASE}/api/admin/plans/{pid}")
        assert r.status_code == 200

    def test_non_admin_forbidden(self, test_business):
        s = test_business["session"]
        assert s.get(f"{BASE}/api/admin/users").status_code == 403
        assert s.get(f"{BASE}/api/admin/plans").status_code == 403
        assert s.post(f"{BASE}/api/admin/plans",
                      json={"name": "X", "minutes": 10, "price": 1.0}).status_code == 403


# ---------- admin users / quota / suspend ----------
class TestAdminUsersAndQuota:
    def test_admin_users_list_contains_test_business(self, admin, test_business):
        s, _ = admin
        rows = s.get(f"{BASE}/api/admin/users").json()
        row = next((u for u in rows if u["id"] == test_business["uid"]), None)
        assert row is not None
        assert row["email"] == test_business["email"]
        assert "minutes_used" in row and isinstance(row["minutes_used"], (int, float))
        assert "agents" in row and row["agents"] >= 1

    def test_my_usage(self, test_business):
        s = test_business["session"]
        r = s.get(f"{BASE}/api/account/usage")
        assert r.status_code == 200
        d = r.json()
        assert "minutes_used" in d
        assert "allow_overage" in d
        # No plan assigned yet
        assert d["plan"] is None

    def test_assign_1min_plan_and_usage(self, admin, test_business):
        s, _ = admin
        body = {"name": "TEST 1min", "minutes": 1, "price": 0, "currency": "EUR"}
        plan = s.post(f"{BASE}/api/admin/plans", json=body).json()
        try:
            s.put(f"{BASE}/api/admin/users/{test_business['uid']}",
                  json={"plan_id": plan["id"], "allow_overage": False, "suspended": False})
            u = test_business["session"].get(f"{BASE}/api/account/usage").json()
            assert u["plan"]["name"] == "TEST 1min"
            assert u["plan"]["minutes"] == 1
            assert u["minutes_used"] == 0  # no calls → should proceed
        finally:
            s.put(f"{BASE}/api/admin/users/{test_business['uid']}",
                  json={"plan_id": None, "allow_overage": False, "suspended": False})
            s.delete(f"{BASE}/api/admin/plans/{plan['id']}")

    def test_suspend_blocks_test_call(self, admin, test_business):
        s, _ = admin
        s.put(f"{BASE}/api/admin/users/{test_business['uid']}",
              json={"plan_id": None, "allow_overage": False, "suspended": True})
        try:
            # CL agent, no CL number anyway → safe. Should fail with 'Cuenta suspendida'.
            bs = test_business["session"]
            r = bs.post(f"{BASE}/api/agents/{test_business['agent']['id']}/test-call",
                        json={"phone": "+56912345678"})
            assert r.status_code == 200, r.text
            lead = r.json()
            assert lead["status"] == "fallida"
            err = (lead.get("error") or "") + " " + (lead.get("call_error") or "")
            assert "suspend" in err.lower() or "Cuenta suspendida" in err, err
        finally:
            s.put(f"{BASE}/api/admin/users/{test_business['uid']}",
                  json={"plan_id": None, "allow_overage": False, "suspended": False})


# ---------- Impersonation ----------
class TestImpersonation:
    def test_impersonate_and_stop(self, admin, test_business):
        # Use a fresh cookie-based session so impersonation cookies take effect
        s = requests.Session()
        r = s.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200
        r = s.post(f"{BASE}/api/admin/users/{test_business['uid']}/impersonate")
        assert r.status_code == 200, r.text
        me = s.get(f"{BASE}/api/auth/me")
        assert me.status_code == 200
        d = me.json()
        assert d["email"] == test_business["email"]
        assert d["role"] != "admin"
        # stop
        r = s.post(f"{BASE}/api/auth/stop-impersonation")
        assert r.status_code == 200
        me = s.get(f"{BASE}/api/auth/me").json()
        assert me["role"] == "admin"
        assert me["email"] == ADMIN_EMAIL


# ---------- Templates & scheduled calls ----------
class TestOutbound:
    def test_default_templates_autocreated(self, test_business):
        s = test_business["session"]
        r = s.get(f"{BASE}/api/templates")
        assert r.status_code == 200
        tpls = r.json()
        names = {t["name"] for t in tpls}
        # 5 defaults
        for n in ("Seguimiento de producto", "Cobro de pago pendiente",
                  "Información sobre producto", "Recordatorio de cita o evento",
                  "Encuesta de satisfacción"):
            assert n in names, f"missing default template: {n}; got {names}"

    def test_create_update_delete_template(self, test_business):
        s = test_business["session"]
        body = {"name": "TEST Tpl", "call_type": "info", "purpose": "Explicar producto",
                "greeting": "Hola {nombre}"}
        r = s.post(f"{BASE}/api/templates", json=body)
        assert r.status_code == 200
        tid = r.json()["id"]
        r = s.put(f"{BASE}/api/templates/{tid}", json={**body, "name": "TEST Tpl2"})
        assert r.status_code == 200 and r.json()["name"] == "TEST Tpl2"
        r = s.delete(f"{BASE}/api/templates/{tid}")
        assert r.status_code == 200

    def test_schedule_future_and_cancel(self, test_business):
        s = test_business["session"]
        tpls = s.get(f"{BASE}/api/templates").json()
        tpl = tpls[0]
        future = (datetime.utcnow() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
        body = {"agent_id": test_business["agent"]["id"], "template_id": tpl["id"],
                "contacts": [{"name": "Ana", "phone": "+56912345678", "email": ""}],
                "run_at": future}
        r = s.post(f"{BASE}/api/scheduled-calls", json=body)
        assert r.status_code == 200, r.text
        assert r.json()["count"] == 1
        rows = s.get(f"{BASE}/api/scheduled-calls").json()
        job = next(j for j in rows if j["name"] == "Ana" and j["status"] == "pendiente")
        assert job["country"] == "CL"
        assert job["phone"] == "+56912345678"
        r = s.delete(f"{BASE}/api/scheduled-calls/{job['id']}")
        assert r.status_code == 200
        rows = s.get(f"{BASE}/api/scheduled-calls").json()
        job2 = next(j for j in rows if j["id"] == job["id"])
        assert job2["status"] == "cancelada"


# ---------- Cron ----------
class TestCron:
    def test_cron_unauthorized(self):
        r = requests.post(f"{BASE}/api/cron/dispatch")
        assert r.status_code == 401

    def test_cron_wrong_secret(self):
        r = requests.post(f"{BASE}/api/cron/dispatch",
                          headers={"Authorization": "Bearer wrong"})
        assert r.status_code == 401

    def test_cron_authorized(self):
        r = requests.post(f"{BASE}/api/cron/dispatch",
                          headers={"Authorization": f"Bearer {CRON_SECRET}"})
        assert r.status_code == 200
        assert r.json().get("ok") is True


# ---------- Support tickets ----------
class TestSupport:
    def test_support_list_empty_or_list(self, test_business):
        s = test_business["session"]
        r = s.get(f"{BASE}/api/support-tickets")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_webhook_request_support_creates_ticket(self, admin):
        """Use admin tenant seed leads so no new lead needed. Carlos Ruiz has a seeded id."""
        s, _ = admin
        leads = s.get(f"{BASE}/api/leads").json()
        lead = leads[0]
        payload = {"message": {"type": "tool-calls",
                               "call": {"metadata": {"lead_id": lead["id"]}},
                               "toolCallList": [{"id": "sup1",
                                                 "function": {"name": "request_support",
                                                              "arguments": {"issue": "TEST problema de instalación"}}}]}}
        r = requests.post(f"{BASE}/api/vapi/webhook?token={WEBHOOK_SECRET}", json=payload)
        assert r.status_code == 200, r.text
        tickets = s.get(f"{BASE}/api/support-tickets").json()
        tk = next((t for t in tickets if t.get("lead_id") == lead["id"]
                   and "TEST problema" in t.get("issue", "")), None)
        assert tk is not None, tickets
        # resolve
        r = s.put(f"{BASE}/api/support-tickets/{tk['id']}/resolve")
        assert r.status_code == 200
        tickets2 = s.get(f"{BASE}/api/support-tickets").json()
        tk2 = next(t for t in tickets2 if t["id"] == tk["id"])
        assert tk2["status"] == "resuelta"


# ---------- Public v1 API ----------
class TestPublicV1:
    def test_api_key_crud_and_calls(self, test_business):
        s = test_business["session"]
        # create key
        r = s.post(f"{BASE}/api/api-keys", json={"name": "TEST Key"})
        assert r.status_code == 200, r.text
        d = r.json()
        key = d["key"]
        kid = d["id"]
        assert key.startswith("vl_live_")

        # List hides the raw key (prefix only)
        rows = s.get(f"{BASE}/api/api-keys").json()
        assert any(k["id"] == kid for k in rows)

        # v1/agents OK
        r = requests.get(f"{BASE}/api/v1/agents", headers={"X-API-Key": key})
        assert r.status_code == 200, r.text
        agents = r.json()
        assert any(a["id"] == test_business["agent"]["id"] for a in agents)

        # invalid key
        r = requests.get(f"{BASE}/api/v1/agents", headers={"X-API-Key": "bogus"})
        assert r.status_code == 401

        # v1/calls consent=false → 400
        r = requests.post(f"{BASE}/api/v1/calls",
                          headers={"X-API-Key": key},
                          json={"agent_id": test_business["agent"]["id"],
                                "name": "Ana", "phone": "+56912345678",
                                "type": "info", "consent": False})
        assert r.status_code == 400

        # v1/calls scheduled_at future for CL → pendiente (safe)
        future = (datetime.utcnow() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")
        r = requests.post(f"{BASE}/api/v1/calls",
                          headers={"X-API-Key": key},
                          json={"agent_id": test_business["agent"]["id"],
                                "name": "Ana", "phone": "+56912345678",
                                "type": "info", "consent": True,
                                "scheduled_at": future})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "pendiente"
        sid = d["scheduled_id"]

        # cleanup scheduled
        s.delete(f"{BASE}/api/scheduled-calls/{sid}")

        # revoke key
        r = s.delete(f"{BASE}/api/api-keys/{kid}")
        assert r.status_code == 200
        # now invalid
        r = requests.get(f"{BASE}/api/v1/agents", headers={"X-API-Key": key})
        assert r.status_code == 401
