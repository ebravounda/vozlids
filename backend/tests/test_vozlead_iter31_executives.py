# Iter31: multi-executive rotation (Executives on agents) - validation, persistence, plan gating
import os
import uuid
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN = {"email": "admin@vozlead.es", "password": "VozLead2026!"}
RESTRICTED = {"max_agents": 3, "max_concurrent": 1, "recording_days": 90, "outbound": True, "api": False, "widget": False,
              "agenda_pro": False, "premium_voices": False, "ambience": False}
FIELDS = ["name", "business_name", "product", "objective", "questions", "country", "voice", "ambience", "ambience_volume",
          "greeting", "extra_instructions", "executives", "active"]


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json=creds)
    assert r.status_code == 200, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return s


def body(**kw):
    b = {"name": "TEST_Marta", "business_name": "TEST Biz", "product": "Producto", "objective": "agendar", "country": "ES",
         "voice": "p_marta", "ambience": "none", "greeting": "Hola {nombre}, soy TEST_Marta de {empresa}", "questions": []}
    b.update(kw)
    return b


@pytest.fixture(scope="module")
def admin():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def tmp_agent(admin):
    r = admin.post(f"{BASE}/api/agents", json=body())
    if r.status_code != 200:
        pytest.skip(f"cannot create agent: {r.text}")
    a = r.json()
    yield a
    admin.delete(f"{BASE}/api/agents/{a['id']}")


# --- Validation on PUT
class TestExecValidation:
    def test_save_and_persist(self, admin, tmp_agent):
        ex = [{"voice": "p_marta", "name": "Marta"}, {"voice": "p_gonzalo", "name": "Pablo"}, {"voice": "p_nuria", "name": "Lucía"}]
        r = admin.put(f"{BASE}/api/agents/{tmp_agent['id']}", json=body(executives=ex))
        assert r.status_code == 200, r.text
        assert r.json()["executives"] == ex
        g = admin.get(f"{BASE}/api/agents/{tmp_agent['id']}").json()
        assert g["executives"] == ex

    def test_duplicate_voice_422(self, admin, tmp_agent):
        ex = [{"voice": "p_marta", "name": "Marta"}, {"voice": "p_marta", "name": "Ana"}]
        r = admin.put(f"{BASE}/api/agents/{tmp_agent['id']}", json=body(executives=ex))
        assert r.status_code == 422
        assert "Cada ejecutivo debe tener una voz distinta" in r.text

    def test_more_than_5_422(self, admin, tmp_agent):
        vs = ["p_marta", "p_gonzalo", "p_nuria", "p_isabel", "p_elena", "p_blanca"]
        r = admin.put(f"{BASE}/api/agents/{tmp_agent['id']}", json=body(executives=[{"voice": v, "name": f"N{i}"} for i, v in enumerate(vs)]))
        assert r.status_code == 422

    def test_other_country_voice_422(self, admin, tmp_agent):
        r = admin.put(f"{BASE}/api/agents/{tmp_agent['id']}", json=body(executives=[{"voice": "p_marta", "name": "M"}, {"voice": "l_fernanda", "name": "F"}]))
        assert r.status_code == 422
        assert "voz no está disponible" in r.text

    def test_empty_name_422(self, admin, tmp_agent):
        r = admin.put(f"{BASE}/api/agents/{tmp_agent['id']}", json=body(executives=[{"voice": "p_marta", "name": ""}]))
        assert r.status_code == 422

    def test_create_with_dup_422(self, admin):
        r = admin.post(f"{BASE}/api/agents", json=body(executives=[{"voice": "p_marta", "name": "A"}, {"voice": "p_marta", "name": "B"}]))
        assert r.status_code == 422
        if r.status_code == 200:
            admin.delete(f"{BASE}/api/agents/{r.json()['id']}")


# --- Plan gating: premium voices
@pytest.fixture(scope="module")
def restricted(admin):
    email = f"test_iter31_{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(f"{BASE}/api/auth/register", json={"name": "TEST Cli", "business_name": "TEST Biz", "email": email, "password": "TestPass123!"})
    assert r.status_code in (200, 201), r.text
    client = _login({"email": email, "password": "TestPass123!"})
    uid = client.get(f"{BASE}/api/auth/me").json()["id"]
    plan = admin.post(f"{BASE}/api/admin/plans", json={"name": "TEST_R31", "minutes": 100, "price_eur": 50, "price_clp": 50000,
                                                       "public": False, "limits": RESTRICTED}).json()
    assert admin.put(f"{BASE}/api/admin/users/{uid}", json={"plan_id": plan["id"]}).status_code == 200
    yield client
    admin.delete(f"{BASE}/api/admin/users/{uid}")
    admin.delete(f"{BASE}/api/admin/plans/{plan['id']}")


class TestExecPlanGating:
    def test_create_with_hd_exec_rejected(self, restricted):
        r = restricted.post(f"{BASE}/api/agents", json=body(executives=[{"voice": "p_marta", "name": "M"}, {"voice": "e_sarah", "name": "Sara"}]))
        assert r.status_code == 403, r.text

    def test_put_with_hd_exec_rejected(self, restricted):
        a = restricted.post(f"{BASE}/api/agents", json=body())
        assert a.status_code == 200, a.text
        aid = a.json()["id"]
        ok = restricted.put(f"{BASE}/api/agents/{aid}", json=body(executives=[{"voice": "p_marta", "name": "M"}, {"voice": "p_gonzalo", "name": "P"}]))
        assert ok.status_code == 200, ok.text
        r = restricted.put(f"{BASE}/api/agents/{aid}", json=body(executives=[{"voice": "p_marta", "name": "M"}, {"voice": "e_sarah", "name": "Sara"}]))
        assert r.status_code == 403, r.text
        assert restricted.get(f"{BASE}/api/agents/{aid}").json()["executives"][1]["voice"] == "p_gonzalo"
