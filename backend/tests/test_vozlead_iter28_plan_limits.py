# Iter28: plan recommended/promo + per-plan limits enforcement
import os
import time
import uuid
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN = {"email": "admin@vozlead.es", "password": "VozLead2026!"}
PLAN_KEYS = ["name", "minutes", "price_eur", "price_clp", "overage_eur", "overage_clp", "features", "public", "recommended",
             "promo_active", "promo_label", "promo_price_eur", "promo_price_clp", "promo_months", "limits"]
RESTRICTED = {"max_agents": 1, "max_concurrent": 1, "recording_days": 90, "outbound": False, "api": False, "widget": False,
              "agenda_pro": False, "premium_voices": False, "ambience": False}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json=creds)
    assert r.status_code == 200, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return s


def agent_body(voice="p_marta", ambience="none"):
    return {"name": "TEST_Ana", "business_name": "TEST biz", "product": "Producto", "objective": "agendar", "country": "ES",
            "voice": voice, "ambience": ambience, "greeting": "Hola", "questions": []}


@pytest.fixture(scope="module")
def ctx():
    admin = _login(ADMIN)
    originals = {p["id"]: p for p in admin.get(f"{BASE}/api/admin/plans").json()}
    email = f"test_iter28_{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(f"{BASE}/api/auth/register", json={"name": "TEST Cli", "business_name": "TEST Biz", "email": email, "password": "TestPass123!"})
    assert r.status_code in (200, 201), r.text
    client = _login({"email": email, "password": "TestPass123!"})
    uid = client.get(f"{BASE}/api/auth/me").json()["id"]
    # key created while still unrestricted (no plan)
    k = client.post(f"{BASE}/api/developer/keys", json={"name": "TEST key", "env": "test", "scopes": ["agents:read"]})
    api_key = k.json().get("key") if k.status_code == 200 else None
    plan = admin.post(f"{BASE}/api/admin/plans", json={"name": "TEST_Restricted", "minutes": 100, "price_eur": 50, "price_clp": 50000,
                                                       "public": False, "limits": RESTRICTED}).json()
    assert admin.put(f"{BASE}/api/admin/users/{uid}", json={"plan_id": plan["id"]}).status_code == 200
    data = {"admin": admin, "client": client, "uid": uid, "plan": plan, "originals": originals, "api_key": api_key, "extra_plans": []}
    yield data
    admin.delete(f"{BASE}/api/admin/users/{uid}")
    for pid in [plan["id"], *data["extra_plans"]]:
        admin.delete(f"{BASE}/api/admin/plans/{pid}")
    for pid, p in originals.items():  # restore recommended/promo flags
        body = {k: p[k] for k in PLAN_KEYS if k in p}
        admin.put(f"{BASE}/api/admin/plans/{pid}", json=body)


# --- Admin plan editor: promo/recommended/limits
class TestPlanAdmin:
    def test_plan_limits_persisted(self, ctx):
        p = next(x for x in ctx["admin"].get(f"{BASE}/api/admin/plans").json() if x["id"] == ctx["plan"]["id"])
        assert p["limits"] == RESTRICTED

    def test_promo_invalid_422(self, ctx):
        base = {"name": "TEST_x", "minutes": 10, "price_eur": 50, "price_clp": 50000, "promo_active": True}
        for extra in ({"promo_price_eur": 60}, {"promo_price_eur": 0, "promo_price_clp": 0}, {"promo_price_eur": 30, "promo_price_clp": 60000}):
            r = ctx["admin"].put(f"{BASE}/api/admin/plans/{ctx['plan']['id']}", json={**base, **extra})
            assert r.status_code == 422, (extra, r.text)
            assert "promoción" in r.text

    def test_recommended_unique(self, ctx):
        r = ctx["admin"].post(f"{BASE}/api/admin/plans", json={"name": "TEST_Reco", "minutes": 77, "price_eur": 99, "price_clp": 90000,
                                                              "public": True, "recommended": True, "promo_active": True,
                                                              "promo_label": "TEST PROMO", "promo_price_eur": 49, "promo_months": 2})
        assert r.status_code == 200, r.text
        pid = r.json()["id"]
        ctx["extra_plans"].append(pid)
        plans = ctx["admin"].get(f"{BASE}/api/admin/plans").json()
        assert [p["id"] for p in plans if p.get("recommended")] == [pid]
        pub = next(p for p in requests.get(f"{BASE}/api/public/plans").json() if p["id"] == pid)
        for k in ("recommended", "promo_active", "promo_label", "promo_price_eur", "promo_price_clp", "promo_months", "limits"):
            assert k in pub
        assert pub["promo_price_eur"] == 49 and pub["promo_months"] == 2

    def test_checkout_promo(self, ctx):
        pid = ctx["extra_plans"][0]
        r = ctx["client"].post(f"{BASE}/api/billing/checkout", json={"plan_id": pid, "origin_url": BASE})
        assert r.status_code == 200, r.text
        assert r.json().get("checkout_url", "").startswith("http")


# --- Enforcement for restricted non-admin tenant
class TestEnforcement:
    def test_usage(self, ctx):
        d = ctx["client"].get(f"{BASE}/api/account/usage").json()
        for k in ("minutes_used", "plan", "limits", "agents", "is_admin"):
            assert k in d
        assert d["is_admin"] is False and d["limits"]["api"] is False and d["plan"]["minutes"] == 100

    def test_premium_voice_403(self, ctx):
        r = ctx["client"].post(f"{BASE}/api/agents", json=agent_body(voice="e_sarah"))
        assert r.status_code == 403, r.text

    def test_ambience_403(self, ctx):
        r = ctx["client"].post(f"{BASE}/api/agents", json=agent_body(ambience="oficina"))
        assert r.status_code == 403, r.text

    def test_max_agents(self, ctx):
        r = ctx["client"].post(f"{BASE}/api/agents", json=agent_body())
        assert r.status_code == 200, r.text
        ctx["agent_id"] = r.json()["id"]
        r2 = ctx["client"].post(f"{BASE}/api/agents", json=agent_body())
        assert r2.status_code == 403 and "agente" in r2.text

    def test_update_agent_premium_403(self, ctx):
        r = ctx["client"].put(f"{BASE}/api/agents/{ctx['agent_id']}", json=agent_body(voice="e_sarah"))
        assert r.status_code == 403

    def test_keys_403(self, ctx):
        r = ctx["client"].post(f"{BASE}/api/developer/keys", json={"name": "k", "env": "test", "scopes": ["agents:read"]})
        assert r.status_code == 403

    def test_v1_plan_feature_missing(self, ctx):
        if not ctx["api_key"]:
            pytest.skip("no key created")
        r = requests.get(f"{BASE}/api/v1/agents", headers={"X-API-Key": ctx["api_key"]})
        assert r.status_code == 403 and "plan_feature_missing" in r.text, r.text

    def test_widget_403(self, ctx):
        r = ctx["client"].put(f"{BASE}/api/widget", json={"agent_id": ctx.get("agent_id", "x")})
        assert r.status_code == 403

    def test_google_connect_403(self, ctx):
        assert ctx["client"].post(f"{BASE}/api/google/connect").status_code == 403

    def test_reminders(self, ctx):
        on = ctx["client"].put(f"{BASE}/api/reminders", json={"call": True, "email": False, "hours_before": 24})
        off = ctx["client"].put(f"{BASE}/api/reminders", json={"call": False, "email": False, "hours_before": 24})
        assert on.status_code == 403 and off.status_code == 200, off.text

    def test_scheduled_calls_403(self, ctx):
        r = ctx["client"].post(f"{BASE}/api/scheduled-calls", json={"agent_id": ctx.get("agent_id", "x"), "template_id": "x",
                                                                   "contacts": [{"name": "A", "phone": "+34600000000"}]})
        assert r.status_code == 403, r.text

    def test_retention(self, ctx):
        g = ctx["client"].get(f"{BASE}/api/privacy/settings").json()
        assert g["plan_cap"] == 90 and g["choices"] == [30, 90]
        assert ctx["client"].put(f"{BASE}/api/privacy/retention", json={"days": 180}).status_code == 422
        assert ctx["client"].put(f"{BASE}/api/privacy/retention", json={"days": 0}).status_code == 422
        assert ctx["client"].put(f"{BASE}/api/privacy/retention", json={"days": 30}).status_code == 200

    def test_admin_unrestricted(self, ctx):
        d = ctx["admin"].get(f"{BASE}/api/account/usage").json()
        assert d["is_admin"] is True and d["limits"]["api"] is True
