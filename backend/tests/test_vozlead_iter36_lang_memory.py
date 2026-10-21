# Iter36: lead language filter/field, call memory (attach_history, memory_block, system_prompt), agent.memory switch, handoff+memory
import os
import sys
import asyncio
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
PHONE = "+34611222333"
LANGS = [{"lang": "en", "voice": "en_jenny", "name": "Jenny"}]


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json=creds)
    assert r.status_code == 200, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return s


def body(**kw):
    b = {"name": "TEST_Mem", "business_name": "TEST biz", "product": "Producto", "objective": "agendar", "country": "ES",
         "voice": "p_marta", "ambience": "none", "greeting": "Hola, soy Ana", "questions": [], "executives": [], "languages": []}
    b.update(kw)
    return b


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture(scope="module")
def ctx():
    admin = _login(ADMIN)
    a = admin.post(f"{BASE}/api/agents", json=body())
    assert a.status_code == 200, a.text
    tid = admin.get(f"{BASE}/api/auth/me").json()["id"]
    d = {"admin": admin, "aid": a.json()["id"], "tid": tid, "leads": []}
    yield d
    admin.delete(f"{BASE}/api/agents/{d['aid']}")
    mdb.leads.delete_many({"_id": {"$in": d["leads"]}})


def mk(ctx, **kw):
    lid = ObjectId()
    doc = {"_id": lid, "tenant_id": ctx["tid"], "agent_id": ctx["aid"], "agent_name": "TEST_Mem", "name": "TEST Lead",
           "phone": PHONE, "status": "calificado", "source": "manual", "summary": "",
           "created_at": "2026-01-01T00:00:00+00:00", "updated_at": "2026-01-01T00:00:00+00:00"}
    doc.update(kw)
    mdb.leads.insert_one(doc)
    ctx["leads"].append(lid)
    return mdb.leads.find_one({"_id": lid})


# --- Lead language filter
class TestLanguageFilter:
    def test_filter(self, ctx):
        en = mk(ctx, language="en", name="TEST_EN")
        es0 = mk(ctx, name="TEST_NOLANG")
        es1 = mk(ctx, language="es", name="TEST_ES")
        es2 = mk(ctx, language="", name="TEST_EMPTY")
        r = ctx["admin"].get(f"{BASE}/api/leads", params={"language": "en", "q": "TEST_"})
        assert r.status_code == 200
        ids = {x["id"] for x in r.json()}
        assert str(en["_id"]) in ids and not ids & {str(x["_id"]) for x in (es0, es1, es2)}
        assert all(x["language"] == "en" for x in r.json())
        r = ctx["admin"].get(f"{BASE}/api/leads", params={"language": "es", "q": "TEST_"})
        ids = {x["id"] for x in r.json()}
        assert {str(x["_id"]) for x in (es0, es1, es2)} <= ids and str(en["_id"]) not in ids
        r = ctx["admin"].get(f"{BASE}/api/leads", params={"q": "TEST_"})
        x = next(x for x in r.json() if x["id"] == str(en["_id"]))
        assert x["language"] == "en" and x["memory_calls"] == 0
        det = ctx["admin"].get(f"{BASE}/api/leads/{en['_id']}").json()
        assert det["language"] == "en" and "memory_calls" in det


    def test_null_language_does_not_500(self, ctx):
        # robustness: a stored language=null must not break the whole list (Lead.language is str)
        n = mk(ctx, language=None, name="TEST_NULL")
        r = ctx["admin"].get(f"{BASE}/api/leads", params={"language": "es", "q": "TEST_NULL"})
        mdb.leads.delete_one({"_id": n["_id"]})
        assert r.status_code == 200, r.text


# --- Agent memory switch
class TestAgentMemory:
    def test_default_and_toggle(self, ctx):
        aid = ctx["admin"].post(f"{BASE}/api/agents", json=body(name="TEST_MemSwitch")).json()["id"]
        try:
            g = ctx["admin"].get(f"{BASE}/api/agents/{aid}").json()
            assert g["memory"] is True
            assert ctx["admin"].put(f"{BASE}/api/agents/{aid}", json=body(memory=False)).status_code == 200
            assert ctx["admin"].get(f"{BASE}/api/agents/{aid}").json()["memory"] is False
            assert ctx["admin"].put(f"{BASE}/api/agents/{aid}", json=body(memory=True)).status_code == 200
            assert ctx["admin"].get(f"{BASE}/api/agents/{aid}").json()["memory"] is True
        finally:
            ctx["admin"].delete(f"{BASE}/api/agents/{aid}")


# --- attach_history + system_prompt (direct python)
class TestAttachHistory:
    def _setup(self, ctx, phone):
        old = [mk(ctx, phone=phone, summary=f"TEST resumen {i}", created_at=f"2026-01-0{i}T10:00:00+00:00",
                  name="Pedro" if i == 2 else "Llamada entrante", executive="Lucía") for i in range(1, 5)]
        mk(ctx, phone=phone, summary="", created_at="2026-01-08T10:00:00+00:00")  # no summary -> excluded
        mk(ctx, phone=phone, summary="OTHER TENANT", tenant_id="other_tenant_x", created_at="2026-01-09T10:00:00+00:00")
        cur = mk(ctx, phone=phone, summary="", created_at="2026-01-10T10:00:00+00:00", status="en_curso")
        return old, cur

    def test_history_and_prompt(self, ctx):
        for k, v in ENV.items():
            os.environ.setdefault(k, v)
        sys.path.insert(0, "/app/backend")
        os.chdir("/app/backend")
        import services as S
        import vapi as V
        phone = "+34699000111"
        old, cur = self._setup(ctx, phone)
        agent = {**mdb.agents.find_one({"_id": ObjectId(ctx["aid"])}), "memory": True}

        async def go():
            # motor client bound to this loop
            out = await S.attach_history(agent, cur)
            return out
        out = run(go())
        h = out["history"]
        assert [r["summary"] for r in h] == ["TEST resumen 4", "TEST resumen 3", "TEST resumen 2"]
        assert all(r["_id"] != cur["_id"] for r in h)
        assert mdb.leads.find_one({"_id": cur["_id"]})["memory_calls"] == 3
        p = V.system_prompt(agent, out, "Hoy es lunes")
        assert "LLAMADAS ANTERIORES CON ESTA PERSONA" in p and "2026-01-04" in p and "TEST resumen 4" in p
        assert "Pedro" in p and "Lucía" in p and "interesado" in p
        p0 = V.system_prompt(agent, cur, "Hoy es lunes")
        assert "LLAMADAS ANTERIORES" not in p0
        # exclusions
        assert "history" not in run(S.attach_history({**agent, "memory": False}, cur))
        assert "history" not in run(S.attach_history(agent, {**cur, "phone": "34699000111"}))
        assert "history" not in run(S.attach_history(agent, {**cur, "is_test": True}))
        assert "history" not in run(S.attach_history(agent, {**cur, "source": "web_vozleads"}))
        # no previous -> empty history, memory_calls untouched
        lone = mk(ctx, phone="+34699000999")
        o = run(S.attach_history(agent, lone))
        assert not o.get("history") and "LLAMADAS ANTERIORES" not in V.system_prompt(agent, o, "Hoy")
        assert mdb.leads.find_one({"_id": lone["_id"]}).get("memory_calls", 0) == 0


# --- Handoff webhook with memory
class TestHandoffMemory:
    def test_handoff_en_memory(self, ctx):
        assert ctx["admin"].put(f"{BASE}/api/agents/{ctx['aid']}", json=body(languages=LANGS, memory=True)).status_code == 200
        assert ctx["admin"].get(f"{BASE}/api/agents/{ctx['aid']}").json()["languages"] == LANGS, "multilang not allowed for admin?"
        phone = "+34699000222"
        mk(ctx, phone=phone, summary="TEST quiere presupuesto de cocina", name="María", created_at="2026-01-02T10:00:00+00:00")
        cur = mk(ctx, phone=phone, status="en_curso", created_at="2026-01-10T10:00:00+00:00")
        r = requests.post(f"{BASE}/api/vapi/webhook", headers={"x-vapi-secret": SECRET}, json={"message": {
            "type": "handoff-destination-request", "parameters": {"language": "en"}, "call": {"metadata": {"lead_id": str(cur["_id"])}}}})
        assert r.status_code == 200, r.text
        a = r.json()["destination"]["assistant"]
        content = " ".join(m.get("content", "") for m in a["model"]["messages"])
        assert "LLAMADAS ANTERIORES CON ESTA PERSONA" in content and "TEST quiere presupuesto de cocina" in content and "María" in content
        db = mdb.leads.find_one({"_id": cur["_id"]})
        assert db["language"] == "en" and db["memory_calls"] == 1
        ld = ctx["admin"].get(f"{BASE}/api/leads/{cur['_id']}").json()
        assert ld["language"] == "en" and ld["memory_calls"] == 1

    def test_handoff_memory_off(self, ctx):
        assert ctx["admin"].put(f"{BASE}/api/agents/{ctx['aid']}", json=body(languages=LANGS, memory=False)).status_code == 200
        phone = "+34699000333"
        mk(ctx, phone=phone, summary="TEST previo", created_at="2026-01-02T10:00:00+00:00")
        cur = mk(ctx, phone=phone, status="en_curso")
        r = requests.post(f"{BASE}/api/vapi/webhook", headers={"x-vapi-secret": SECRET}, json={"message": {
            "type": "handoff-destination-request", "parameters": {"language": "en"}, "call": {"metadata": {"lead_id": str(cur["_id"])}}}})
        assert r.status_code == 200, r.text
        content = " ".join(m.get("content", "") for m in r.json()["destination"]["assistant"]["model"]["messages"])
        assert "LLAMADAS ANTERIORES" not in content
