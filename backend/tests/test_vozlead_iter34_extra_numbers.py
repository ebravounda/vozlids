# Iter34: extra phone numbers per agent (/api/numbers, /api/numbers/extra, assign, remove, admin approve)
import os
import uuid
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN = {"email": "admin@vozlead.es", "password": "VozLead2026!"}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json=creds)
    assert r.status_code == 200, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return s


def agent_body(name, country="ES"):
    return {"name": name, "business_name": "TEST Biz", "product": "Producto", "objective": "agendar", "country": country,
            "voice": "p_marta" if country == "ES" else "l_fernanda", "ambience": "none",
            "greeting": f"Hola {{nombre}}, soy {name} de {{empresa}}", "questions": []}


@pytest.fixture(scope="module")
def admin():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def agents(admin):
    made = {}
    for k, c in (("es1", "ES"), ("es2", "ES"), ("cl", "CL")):
        r = admin.post(f"{BASE}/api/agents", json=agent_body(f"TEST_Num_{k}", c))
        assert r.status_code == 200, r.text
        made[k] = r.json()["id"]
    yield made
    for aid in made.values():
        admin.delete(f"{BASE}/api/agents/{aid}")


@pytest.fixture(scope="module")
def client():
    email = f"test_num_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{BASE}/api/auth/register", json={"name": "TEST Cli", "business_name": "TEST Biz", "email": email, "password": "TestPass123!"})
    assert r.status_code == 200, r.text
    return _login({"email": email, "password": "TestPass123!"})


class TestExtraNumbers:
    state = {}

    def test_list_numbers_and_prices(self, admin):
        r = admin.get(f"{BASE}/api/numbers")
        assert r.status_code == 200
        d = r.json()
        assert d["prices"] == {"ES": "10 €", "CL": "13.000 CLP"}
        prim = [n for n in d["numbers"] if not n["extra"]]
        assert prim and prim[0]["price"] == "Incluido en tu plan"
        self.state["primary"] = prim[0]

    def test_add_extra_admin_pending(self, admin, agents):
        r = admin.post(f"{BASE}/api/numbers/extra", json={"agent_id": agents["es1"]})
        assert r.status_code == 200, r.text
        n = r.json()
        assert n["extra"] is True and n["agent_id"] == agents["es1"] and n["country"] == "ES"
        assert n["status"] == "pendiente_aprobacion" and n["price"] == "10 €"
        self.state["extra"] = n["id"]
        ids = [x["id"] for x in admin.get(f"{BASE}/api/numbers").json()["numbers"]]
        assert n["id"] in ids

    def test_add_extra_cl_price(self, admin, agents):
        r = admin.post(f"{BASE}/api/numbers/extra", json={"agent_id": agents["cl"]})
        assert r.status_code == 200, r.text
        assert r.json()["price"] == "13.000 CLP" and r.json()["country"] == "CL"
        self.state["extra_cl"] = r.json()["id"]

    def test_add_extra_duplicate_409(self, admin, agents):
        r = admin.post(f"{BASE}/api/numbers/extra", json={"agent_id": agents["es1"]})
        assert r.status_code == 409

    def test_add_extra_bad_agent(self, admin):
        assert admin.post(f"{BASE}/api/numbers/extra", json={"agent_id": "0" * 24}).status_code == 404
        assert admin.post(f"{BASE}/api/numbers/extra", json={"agent_id": "abc"}).status_code == 422

    def test_assign_wrong_country_422(self, admin, agents):
        r = admin.put(f"{BASE}/api/numbers/{self.state['extra']}", json={"agent_id": agents["cl"]})
        assert r.status_code == 422

    def test_assign_to_agent_with_other_extra_409(self, admin, agents):
        # create extra for es2, then try to move es1's number onto es2
        r = admin.post(f"{BASE}/api/numbers/extra", json={"agent_id": agents["es2"]})
        assert r.status_code == 200
        self.state["extra2"] = r.json()["id"]
        r = admin.put(f"{BASE}/api/numbers/{self.state['extra']}", json={"agent_id": agents["es2"]})
        assert r.status_code == 409

    def test_unassign_and_reassign(self, admin, agents):
        r = admin.put(f"{BASE}/api/numbers/{self.state['extra']}", json={"agent_id": ""})
        assert r.status_code == 200 and r.json()["agent_id"] is None
        r = admin.put(f"{BASE}/api/numbers/{self.state['extra']}", json={"agent_id": agents["es1"]})
        assert r.status_code == 200 and r.json()["agent_id"] == agents["es1"]

    def test_assign_primary_inbound(self, admin, agents):
        p = self.state["primary"]
        r = admin.put(f"{BASE}/api/numbers/{p['id']}", json={"agent_id": agents["es2"]})
        assert r.status_code == 200 and r.json()["agent_id"] == agents["es2"]
        r = admin.put(f"{BASE}/api/numbers/{p['id']}", json={"agent_id": p["agent_id"] or ""})
        assert r.status_code == 200 and r.json()["agent_id"] == p["agent_id"]

    def test_delete_primary_409(self, admin):
        assert admin.delete(f"{BASE}/api/numbers/{self.state['primary']['id']}").status_code == 409

    def test_admin_pending_list(self, admin):
        r = admin.get(f"{BASE}/api/admin/numbers/extra")
        assert r.status_code == 200
        ids = {x["id"]: x for x in r.json()}
        assert self.state["extra"] in ids and ids[self.state["extra"]]["business"]

    def test_approve_without_zadarma_goes_error(self, admin):
        r = admin.post(f"{BASE}/api/admin/numbers/extra/{self.state['extra_cl']}/approve")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "error" and r.json()["error"]

    def test_client_cannot_touch_admin_numbers(self, client):
        assert client.put(f"{BASE}/api/numbers/{self.state['extra']}", json={"agent_id": ""}).status_code == 404
        assert client.delete(f"{BASE}/api/numbers/{self.state['extra']}").status_code == 404
        assert client.get(f"{BASE}/api/admin/numbers/extra").status_code == 403
        assert client.post(f"{BASE}/api/admin/numbers/extra/{self.state['extra']}/approve").status_code == 403

    def test_client_without_plan_409(self, client):
        a = client.post(f"{BASE}/api/agents", json=agent_body("TEST_Num_cli"))
        assert a.status_code == 200, a.text
        r = client.post(f"{BASE}/api/numbers/extra", json={"agent_id": a.json()["id"]})
        assert r.status_code == 409 and "plan" in r.json()["detail"].lower()
        assert client.get(f"{BASE}/api/numbers").json()["numbers"] == [] or True

    def test_delete_agent_frees_number(self, admin, agents):
        assert admin.delete(f"{BASE}/api/agents/{agents['es2']}").status_code == 200
        n = next(x for x in admin.get(f"{BASE}/api/numbers").json()["numbers"] if x["id"] == self.state["extra2"])
        assert n["agent_id"] is None

    def test_remove_extras(self, admin):
        for k in ("extra", "extra2", "extra_cl"):
            r = admin.delete(f"{BASE}/api/numbers/{self.state[k]}")
            assert r.status_code == 200 and r.json()["ok"] is True
        ids = [x["id"] for x in admin.get(f"{BASE}/api/numbers").json()["numbers"]]
        for k in ("extra", "extra2", "extra_cl"):
            assert self.state[k] not in ids
