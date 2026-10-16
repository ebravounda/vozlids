# Iteration 30: Cartesia premium voices, voice-preview sources, real costs / profit panel, pricing persistence
import os
import uuid
from datetime import datetime, timezone

import pytest
import requests
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ES_NEW = ["p_blanca", "p_eva", "p_lara", "p_alicia", "p_maite", "p_lucia", "p_octavio", "p_rafael", "p_dario"]
CL_NEW = ["l_catalina", "l_veronica", "l_rodrigo", "l_santiago"]


@pytest.fixture(scope="module")
def s():
    x = requests.Session()
    r = x.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@vozlead.es", "password": "VozLead2026!"})
    if r.status_code != 200:
        pytest.skip("login failed")
    x.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return x


@pytest.fixture(scope="module")
def mdb():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _agent_body(country, voice):
    return {"name": "TEST_cart", "business_name": "TEST biz", "product": "Producto test", "objective": "agendar",
            "questions": [], "country": country, "voice": voice, "ambience": "none", "ambience_volume": 35,
            "greeting": "Hola", "extra_instructions": "", "active": False}


# ---- Agents accept new Cartesia voices
class TestAgentVoices:
    def test_es_and_cl_new_voices(self, s):
        ids = []
        try:
            r = s.post(f"{BASE_URL}/api/agents", json=_agent_body("ES", "elvira"))
            assert r.status_code == 200, r.text
            aid = r.json()["id"]
            ids.append(aid)
            for v in ES_NEW:
                r = s.put(f"{BASE_URL}/api/agents/{aid}", json=_agent_body("ES", v))
                assert r.status_code == 200, f"{v}: {r.text}"
                assert r.json()["voice"] == v
            assert s.get(f"{BASE_URL}/api/agents/{aid}").json()["voice"] == ES_NEW[-1]
            # CL voice on ES agent rejected
            r = s.put(f"{BASE_URL}/api/agents/{aid}", json=_agent_body("ES", "l_rodrigo"))
            assert r.status_code == 422
            r = s.post(f"{BASE_URL}/api/agents", json=_agent_body("CL", "cl_catalina"))
            assert r.status_code == 200, r.text
            cid = r.json()["id"]
            ids.append(cid)
            for v in CL_NEW:
                r = s.put(f"{BASE_URL}/api/agents/{cid}", json=_agent_body("CL", v))
                assert r.status_code == 200, f"{v}: {r.text}"
            r = s.put(f"{BASE_URL}/api/agents/{cid}", json=_agent_body("CL", "p_blanca"))
            assert r.status_code == 422
        finally:
            for i in ids:
                s.delete(f"{BASE_URL}/api/agents/{i}")


# ---- Voice preview sources
class TestPreview:
    @pytest.mark.parametrize("voice,src", [("p_blanca", "cartesia"), ("l_santiago", "cartesia"),
                                           ("elvira", "azure"), ("e_sarah", "elevenlabs")])
    def test_source(self, s, voice, src):
        r = s.get(f"{BASE_URL}/api/voice-preview", params={"voice": voice, "text": "Hola", "ambience_id": "none"}, timeout=90)
        assert r.status_code == 200, r.text[:300]
        assert r.headers.get("x-voice-source") == src
        assert r.headers.get("content-type", "").startswith("audio")
        assert len(r.content) > 1000


# ---- Costs / profit
class TestCosts:
    def test_costs_shape(self, s):
        r = s.get(f"{BASE_URL}/api/admin/costs", params={"days": 30}, timeout=90)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("revenue", "variable", "per_client_fixed", "fixed", "net", "margin_pct"):
            assert k in d["profit"]
        p = d["profit"]
        assert abs(p["net"] - (p["revenue"] - p["variable"] - p["per_client_fixed"] - p["fixed"])) < 1e-6
        assert isinstance(d["fixed"], list) and "zadarma_sync" in d and "eleven_usage" in d
        for t in d["tenants"]:
            for k in ("plan", "revenue", "number_fee", "stripe_fee", "profit", "margin_pct"):
                assert k in t
        for c in d["calls"]:
            assert isinstance(c["line_real"], bool)

    def test_requires_admin(self):
        assert requests.get(f"{BASE_URL}/api/admin/costs").status_code in (401, 403)

    def test_eleven_own_voice_cost(self, s, mdb):
        admin = mdb.users.find_one({"email": "admin@vozlead.es"})
        agent = mdb.agents.find_one({"tenant_id": str(admin["_id"])})
        lid = ObjectId()
        mdb.leads.insert_one({"_id": lid, "tenant_id": str(admin["_id"]), "agent_id": str(agent["_id"]),
                              "name": "TEST_eleven", "phone": "+34600000000", "status": "completado",
                              "vapi_call_id": f"TEST_{uuid.uuid4().hex}", "voice_provider": "11labs",
                              "duration_seconds": 60, "cost": 0.10, "line_cost_usd": 0.02,
                              "cost_breakdown": {"tts": 0, "ttsCharacters": 1000, "stt": 0.01, "llm": 0.02, "vapi": 0.05},
                              "created_at": datetime.now(timezone.utc).isoformat()})
        try:
            d = s.get(f"{BASE_URL}/api/admin/costs", params={"days": 30}, timeout=90).json()
            c = next(c for c in d["calls"] if c["id"] == str(lid))
            pr = d["pricing"]
            exp = 1000 * pr["eleven_credits_per_char"] * pr["eleven_plan_usd"] / pr["eleven_plan_credits"]
            assert abs(c["voz"] - exp) < 1e-6, (c["voz"], exp)
            assert abs(exp - 0.11) < 1e-9 or pr["eleven_plan_usd"] != 22
            assert c["line_real"] is True and abs(c["linea"] - 0.02) < 1e-9
            assert abs(c["total"] - (0.10 + exp + 0.02)) < 1e-6
            assert c["otros"] == pytest.approx(0.02, abs=1e-6)
        finally:
            mdb.leads.delete_one({"_id": lid})


# ---- Pricing persistence
class TestPricing:
    def test_put_get_restore(self, s):
        orig = s.get(f"{BASE_URL}/api/admin/pricing").json()
        new = {**orig, "eleven_plan_usd": 99.0, "eleven_plan_credits": 500000, "eleven_credits_per_char": 1.0,
               "number_es_usd_month": 4.5, "number_cl_usd_month": 9.5, "stripe_pct": 2.0, "stripe_fixed_eur": 0.3,
               "fixed_costs": [{"name": "TEST_fixed", "usd": 50.0}]}
        try:
            before = s.get(f"{BASE_URL}/api/admin/costs", params={"days": 30}, timeout=90).json()["profit"]
            r = s.put(f"{BASE_URL}/api/admin/pricing", json=new)
            assert r.status_code == 200, r.text
            g = s.get(f"{BASE_URL}/api/admin/pricing").json()
            for k in ("eleven_plan_usd", "eleven_plan_credits", "eleven_credits_per_char", "number_es_usd_month",
                      "number_cl_usd_month", "stripe_pct", "stripe_fixed_eur", "fixed_costs"):
                assert g[k] == new[k], k
            after = s.get(f"{BASE_URL}/api/admin/costs", params={"days": 30}, timeout=90).json()
            assert after["profit"]["fixed"] == pytest.approx(50.0)
            assert after["fixed"][0]["name"] == "TEST_fixed"
            # invalid
            assert s.put(f"{BASE_URL}/api/admin/pricing", json={**new, "eleven_plan_credits": 0}).status_code == 422
            assert s.put(f"{BASE_URL}/api/admin/pricing", json={**new, "fixed_costs": [{"name": "", "usd": 1}]}).status_code == 422
            print("profit before", before, "after", after["profit"])
        finally:
            assert s.put(f"{BASE_URL}/api/admin/pricing", json=orig).status_code == 200
            assert s.get(f"{BASE_URL}/api/admin/pricing").json() == orig


# ---- Sync
class TestSync:
    def test_sync(self, s):
        r = s.post(f"{BASE_URL}/api/admin/costs/sync", timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("updated", "pending", "line_matched", "line_error"):
            assert k in d
        print("sync:", d)
