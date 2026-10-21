# Iter35: multi-language executives (languages on agents), voice validation, handoff webhook, voice preview lang, multilang plan feature
import os
import uuid
import pytest
import requests
from bson import ObjectId
from pymongo import MongoClient
from dotenv import dotenv_values

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ENV = dotenv_values("/app/backend/.env")
SECRET = ENV["VAPI_WEBHOOK_SECRET"]
ADMIN = {"email": "admin@vozlead.es", "password": "VozLead2026!"}
mdb = MongoClient(ENV["MONGO_URL"])[ENV["DB_NAME"]]


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json=creds)
    assert r.status_code == 200, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return s


def body(**kw):
    b = {"name": "TEST_Ana", "business_name": "TEST biz", "product": "Producto", "objective": "agendar", "country": "ES",
         "voice": "p_marta", "ambience": "none", "greeting": "Hola, soy Ana", "questions": [], "executives": [], "languages": []}
    b.update(kw)
    return b


@pytest.fixture(scope="module")
def ctx():
    admin = _login(ADMIN)
    a = admin.post(f"{BASE}/api/agents", json=body())
    assert a.status_code == 200, a.text
    aid = a.json()["id"]
    email = f"test_iter35_{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(f"{BASE}/api/auth/register", json={"name": "TEST Cli", "business_name": "TEST Biz", "email": email, "password": "TestPass123!"})
    assert r.status_code in (200, 201), r.text
    client = _login({"email": email, "password": "TestPass123!"})
    uid = client.get(f"{BASE}/api/auth/me").json()["id"]
    plan = admin.post(f"{BASE}/api/admin/plans", json={"name": "TEST_NoMultilang", "minutes": 100, "price_eur": 50, "price_clp": 50000,
                                                       "public": False}).json()
    assert admin.put(f"{BASE}/api/admin/users/{uid}", json={"plan_id": plan["id"]}).status_code == 200
    d = {"admin": admin, "aid": aid, "client": client, "uid": uid, "plan": plan, "leads": []}
    yield d
    admin.delete(f"{BASE}/api/agents/{aid}")
    admin.delete(f"{BASE}/api/admin/users/{uid}")
    admin.delete(f"{BASE}/api/admin/plans/{plan['id']}")
    for lid in d["leads"]:
        mdb.leads.delete_one({"_id": lid})


# --- Agent save with languages
class TestAgentLanguages:
    def test_save_languages_persist(self, ctx):
        langs = [{"lang": "en", "voice": "en_jenny", "name": "Jenny"}, {"lang": "ca", "voice": "ca_joana", "name": "Joana"},
                 {"lang": "de", "voice": "e_sarah", "name": "Emma"}]
        r = ctx["admin"].put(f"{BASE}/api/agents/{ctx['aid']}", json=body(languages=langs))
        assert r.status_code == 200, r.text
        g = ctx["admin"].get(f"{BASE}/api/agents/{ctx['aid']}").json()
        assert g["languages"] == langs

    def test_voice_not_speaking_lang_422(self, ctx):
        r = ctx["admin"].put(f"{BASE}/api/agents/{ctx['aid']}", json=body(languages=[{"lang": "ca", "voice": "e_sarah", "name": "Emma"}]))
        assert r.status_code == 422 and "no habla catalán" in r.text, r.text
        r = ctx["admin"].put(f"{BASE}/api/agents/{ctx['aid']}", json=body(languages=[{"lang": "en", "voice": "p_marta", "name": "Marta"}]))
        assert r.status_code == 422, r.text
        r = ctx["admin"].put(f"{BASE}/api/agents/{ctx['aid']}", json=body(languages=[{"lang": "fr", "voice": "en_jenny", "name": "J"}]))
        assert r.status_code == 422, r.text

    def test_duplicate_lang_422(self, ctx):
        r = ctx["admin"].put(f"{BASE}/api/agents/{ctx['aid']}", json=body(languages=[
            {"lang": "en", "voice": "en_jenny", "name": "Jenny"}, {"lang": "en", "voice": "en_guy", "name": "Guy"}]))
        assert r.status_code == 422, r.text

    def test_invalid_lang_code_422(self, ctx):
        r = ctx["admin"].put(f"{BASE}/api/agents/{ctx['aid']}", json=body(languages=[{"lang": "ja", "voice": "en_jenny", "name": "J"}]))
        assert r.status_code == 422

    def test_main_voice_must_be_spanish(self, ctx):
        r = ctx["admin"].put(f"{BASE}/api/agents/{ctx['aid']}", json=body(voice="en_jenny"))
        assert r.status_code == 422, r.text
        r = ctx["admin"].put(f"{BASE}/api/agents/{ctx['aid']}", json=body(executives=[{"voice": "p_marta", "name": "Marta"}, {"voice": "en_guy", "name": "Guy"}]))
        assert r.status_code == 422, r.text

    def test_cross_accent_executives_and_country(self, ctx):
        # Every Spanish voice of any accent/tier allowed regardless of country
        ex = [{"voice": "p_marta", "name": "Marta"}, {"voice": "l_mateo", "name": "Mateo"}, {"voice": "cl_catalina", "name": "Catalina"},
              {"voice": "e_sarah", "name": "Sara"}]
        for country in ("ES", "CL"):
            r = ctx["admin"].put(f"{BASE}/api/agents/{ctx['aid']}", json=body(country=country, executives=ex))
            assert r.status_code == 200, (country, r.text)
            g = ctx["admin"].get(f"{BASE}/api/agents/{ctx['aid']}").json()
            assert g["country"] == country and [e["voice"] for e in g["executives"]] == [e["voice"] for e in ex]


# --- Plan feature: multilang
class TestMultilangPlan:
    def test_new_plan_defaults_multilang_off(self, ctx):
        p = next(x for x in ctx["admin"].get(f"{BASE}/api/admin/plans").json() if x["id"] == ctx["plan"]["id"])
        assert (p.get("limits") or {}).get("multilang", False) is False
        assert "premium_voices" not in (p.get("limits") or {})

    def test_usage_limits_multilang_false(self, ctx):
        u = ctx["client"].get(f"{BASE}/api/account/usage").json()
        assert u["limits"]["multilang"] is False

    def test_client_without_multilang_strips_languages(self, ctx):
        r = ctx["client"].post(f"{BASE}/api/agents", json=body(languages=[{"lang": "en", "voice": "en_jenny", "name": "Jenny"}]))
        assert r.status_code == 200, r.text
        assert r.json()["languages"] == []

    def test_client_can_use_hd_voice_any_plan(self, ctx):
        r = ctx["client"].post(f"{BASE}/api/agents", json=body(voice="e_sarah", executives=[{"voice": "e_sarah", "name": "Sara"}, {"voice": "l_mateo", "name": "Mateo"}]))
        assert r.status_code == 200, r.text
        ctx["client"].delete(f"{BASE}/api/agents/{r.json()['id']}")

    def test_enable_multilang_allows(self, ctx):
        p = ctx["plan"]
        r = ctx["admin"].put(f"{BASE}/api/admin/plans/{p['id']}", json={"name": p["name"], "minutes": 100, "price_eur": 50, "price_clp": 50000,
                                                                       "public": False, "limits": {"multilang": True}})
        assert r.status_code == 200, r.text
        r = ctx["client"].post(f"{BASE}/api/agents", json=body(languages=[{"lang": "en", "voice": "en_jenny", "name": "Jenny"}]))
        assert r.status_code == 200, r.text
        aid = r.json()["id"]
        # downgrade: agent keeps languages stored -> what happens when saving without touching languages?
        ctx["admin"].put(f"{BASE}/api/admin/plans/{p['id']}", json={"name": p["name"], "minutes": 100, "price_eur": 50, "price_clp": 50000,
                                                                   "public": False, "limits": {"multilang": False}})
        g = ctx["client"].get(f"{BASE}/api/agents/{aid}").json()
        r2 = ctx["client"].put(f"{BASE}/api/agents/{aid}", json=body(name="TEST_Renamed", languages=g["languages"]))
        ctx["downgrade_status"] = r2.status_code
        ctx["client"].delete(f"{BASE}/api/agents/{aid}")
        print("downgrade save status", r2.status_code, r2.text[:200])


# --- Vapi webhook handoff
class TestHandoffWebhook:
    def _lead(self, ctx):
        lid = ObjectId()
        tid = ctx["admin"].get(f"{BASE}/api/auth/me").json()["id"]
        mdb.leads.insert_one({"_id": lid, "tenant_id": tid, "agent_id": ctx["aid"], "name": "TEST Lead", "phone": "+34600000000",
                              "status": "en_curso", "source": "manual", "created_at": "2026-01-01T00:00:00+00:00",
                              "updated_at": "2026-01-01T00:00:00+00:00"})
        ctx["leads"].append(lid)
        return lid

    def _post(self, payload, secret=SECRET):
        return requests.post(f"{BASE}/api/vapi/webhook", json={"message": payload}, headers={"x-vapi-secret": secret})

    def test_handoff_en(self, ctx):
        langs = [{"lang": "en", "voice": "en_jenny", "name": "Jenny"}, {"lang": "ca", "voice": "ca_joana", "name": "Joana"},
                 {"lang": "de", "voice": "e_sarah", "name": "Emma"}]
        assert ctx["admin"].put(f"{BASE}/api/agents/{ctx['aid']}", json=body(languages=langs)).status_code == 200
        lid = self._lead(ctx)
        r = self._post({"type": "handoff-destination-request", "parameters": {"language": "en", "destination": "dynamic"},
                        "call": {"metadata": {"lead_id": str(lid)}}})
        assert r.status_code == 200, r.text
        a = r.json()["destination"]["assistant"]
        assert r.json()["destination"]["type"] == "assistant"
        assert "Jenny" in a["firstMessage"] and "English" in a["firstMessage"]
        assert a["voice"] == {"provider": "azure", "voiceId": "en-US-JennyNeural"}
        assert a["transcriber"]["language"] == "en"
        assert not any(t.get("type") == "handoff" for t in a["model"]["tools"])
        assert mdb.leads.find_one({"_id": lid})["language"] == "en"

    def test_handoff_ca_and_eleven_de(self, ctx):
        lid = self._lead(ctx)
        r = self._post({"type": "handoff-destination-request", "parameters": {"language": "ca"}, "call": {"metadata": {"lead_id": str(lid)}}})
        a = r.json()["destination"]["assistant"]
        assert a["voice"]["voiceId"] == "ca-ES-JoanaNeural" and a["transcriber"]["language"] == "ca" and "català" in a["firstMessage"]
        r = self._post({"type": "handoff-destination-request", "parameters": {"language": "de"}, "call": {"metadata": {"lead_id": str(lid)}}})
        a = r.json()["destination"]["assistant"]
        assert a["voice"]["provider"] == "11labs" and a["voice"]["language"] == "de"
        assert a["voice"]["fallbackPlan"]["voices"][0]["voiceId"] == "de-DE-KatjaNeural"
        assert "Deutsch" in a["firstMessage"]

    def test_handoff_not_enabled_error(self, ctx):
        lid = self._lead(ctx)
        r = self._post({"type": "handoff-destination-request", "parameters": {"language": "fr"}, "call": {"metadata": {"lead_id": str(lid)}}})
        assert r.status_code == 200 and "error" in r.json() and "destination" not in r.json()

    def test_handoff_no_lead_error(self, ctx):
        r = self._post({"type": "handoff-destination-request", "parameters": {"language": "en"}, "call": {"metadata": {"lead_id": str(ObjectId())}}})
        assert r.status_code == 200 and "error" in r.json()

    def test_webhook_bad_secret_401(self, ctx):
        r = self._post({"type": "handoff-destination-request", "parameters": {"language": "en"}}, secret="bad")
        assert r.status_code == 401


# --- Voice preview with lang
class TestVoicePreview:
    def test_preview_en_jenny(self, ctx):
        r = ctx["admin"].get(f"{BASE}/api/voice-preview", params={"voice": "en_jenny", "lang": "en", "text": "Hello"}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert r.headers["content-type"].startswith("audio") and len(r.content) > 1000

    def test_preview_wrong_lang_422(self, ctx):
        r = ctx["admin"].get(f"{BASE}/api/voice-preview", params={"voice": "e_sarah", "lang": "ca", "text": "Hola"})
        assert r.status_code == 422
        r = ctx["admin"].get(f"{BASE}/api/voice-preview", params={"voice": "en_jenny", "lang": "es", "text": "Hola"})
        assert r.status_code == 422

    def test_preview_eleven_fr(self, ctx):
        r = ctx["admin"].get(f"{BASE}/api/voice-preview", params={"voice": "e_sarah", "lang": "fr", "text": "Bonjour"}, timeout=60)
        assert r.status_code == 200, r.text[:300]
