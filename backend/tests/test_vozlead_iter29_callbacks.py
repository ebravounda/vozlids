# Iteration 29: 'Llámame más tarde' automatic callbacks (API + backend logic)
# SAFETY: all test callbacks are scheduled far in the future (Nov 2026) and cancelled at teardown.
import asyncio
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
import requests
from dotenv import load_dotenv

sys.path.insert(0, "/app/backend")
load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
TENANT = "6acfac3a346c4c1ebc71ff57"
AGENT = "6acfac3a346c4c1ebc71ff58"
MAD = ZoneInfo("Europe/Madrid")


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@vozlead.es", "password": "VozLead2026!"})
    assert r.status_code == 200, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return s


@pytest.fixture(scope="module")
def other():
    s = requests.Session()
    email = f"test_cb_{datetime.now().timestamp():.0f}@example.com"
    r = s.post(f"{BASE_URL}/api/auth/register", json={"name": "TEST CB", "business_name": "TEST CB SL",
                                                      "email": email, "password": "TestPass2026!"})
    if r.status_code not in (200, 201):
        pytest.skip(f"register failed {r.status_code} {r.text[:200]}")
    tok = r.json().get("access_token")
    if not tok:
        r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "TestPass2026!"})
        tok = r.json()["access_token"]
    s.headers["Authorization"] = f"Bearer {tok}"
    return s


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------- pure logic: target / fit_window ----------
class TestWindowLogic:
    def test_fit_window_rules(self):
        import callbacks as C
        assert C.fit_window(datetime(2026, 10, 16, 10, 0, tzinfo=MAD)) == datetime(2026, 10, 16, 10, 0, tzinfo=MAD)
        assert C.fit_window(datetime(2026, 10, 16, 21, 30, tzinfo=MAD)) == datetime(2026, 10, 19, 9, 0, tzinfo=MAD)  # Fri late -> Mon 9
        assert C.fit_window(datetime(2026, 10, 17, 12, 0, tzinfo=MAD)) == datetime(2026, 10, 19, 9, 0, tzinfo=MAD)  # Sat -> Mon
        assert C.fit_window(datetime(2026, 10, 19, 7, 15, tzinfo=MAD)) == datetime(2026, 10, 19, 9, 0, tzinfo=MAD)  # early -> 9
        assert C.fit_window(datetime(2026, 10, 19, 20, 59, tzinfo=MAD)).hour == 20

    def test_target_rules(self):
        import callbacks as C
        now = datetime(2026, 10, 14, 11, 0, tzinfo=MAD)  # Wednesday
        assert C.target({}, now) == datetime(2026, 10, 14, 13, 0, tzinfo=MAD)  # default +2h
        assert C.target({"time": "18:00"}, now) == datetime(2026, 10, 14, 18, 0, tzinfo=MAD)
        assert C.target({"time": "10:00"}, now) == datetime(2026, 10, 15, 10, 0, tzinfo=MAD)  # past today -> tomorrow
        assert C.target({"time": "23:00"}, now) == datetime(2026, 10, 15, 9, 0, tzinfo=MAD)  # out of window
        assert C.target({"date": "2026-10-17", "time": "12:00"}, now) == datetime(2026, 10, 19, 9, 0, tzinfo=MAD)  # Sat -> Mon
        assert C.target({"time": "garbage"}, now) == datetime(2026, 10, 14, 13, 0, tzinfo=MAD)
        late = datetime(2026, 10, 16, 20, 0, tzinfo=MAD)  # Fri 20:00 +2h -> Mon 9
        assert C.target({}, late) == datetime(2026, 10, 19, 9, 0, tzinfo=MAD)

    def test_tools_outbound_only(self):
        import vapi
        agent = {"objective": "calificar"}
        out = [t.get("function", {}).get("name") for t in vapi.tools(agent, {}, {"direction": "saliente"})]
        inn = [t.get("function", {}).get("name") for t in vapi.tools(agent, {}, {"direction": "entrante"})]
        assert "schedule_callback" in out
        assert "schedule_callback" not in inn


# ---------- backend logic: handle_tool_calls / finalize_call ----------
class TestToolLogic:
    def test_schedule_reschedule_max_and_finalize(self):
        run(self._flow())

    async def _flow(self):
        import services as S
        from db import db
        from bson import ObjectId
        from models import Lead
        created = []
        try:
            orig = Lead(tenant_id=TENANT, agent_id=AGENT, agent_name="Marta", name="TEST_Rellamada Orig",
                        phone="+34600000098", is_test=True, status="en_curso").to_mongo()
            orig["direction"] = "saliente"
            oid = (await db.leads.insert_one(orig)).inserted_id
            created.append(oid)
            lead = await db.leads.find_one({"_id": oid})
            msg = {"toolCallList": [{"id": "tc1", "function": {"name": "schedule_callback",
                                                                "arguments": {"date": "2026-11-04", "time": "10:30"}}}]}
            res = await S.handle_tool_calls(msg, lead)
            assert '"ok": true' in res["results"][0]["result"], res
            cbs = await db.leads.find({"callback_of": str(oid)}).to_list(10)
            created += [c["_id"] for c in cbs]
            assert len(cbs) == 1
            cb = cbs[0]
            assert cb["status"] == "programada" and cb["callback_count"] == 1
            assert cb["run_at"] == "2026-11-04T09:30:00+00:00" and cb["callback_at"] == "2026-11-04T10:30"
            assert cb["is_test"] is True
            lead = await db.leads.find_one({"_id": oid})
            assert lead["callback_id"] == str(cb["_id"])
            # again -> reschedule, no duplicate
            msg["toolCallList"][0]["function"]["arguments"] = {"date": "2026-11-05", "time": "12:00"}
            res = await S.handle_tool_calls(msg, lead)
            assert '"ok": true' in res["results"][0]["result"]
            cbs = await db.leads.find({"callback_of": str(oid)}).to_list(10)
            assert len(cbs) == 1 and cbs[0]["callback_at"] == "2026-11-05T12:00"
            assert cbs[0]["run_at"] == "2026-11-05T11:00:00+00:00"
            # max reached
            maxed = {**lead, "_id": cb["_id"], "callback_count": 2, "callback_id": None}
            res = await S.handle_tool_calls(msg, maxed)
            assert '"ok": false' in res["results"][0]["result"]
            assert await db.leads.count_documents({"callback_of": str(cb["_id"])}) == 0
            # finalize -> rellamada
            lead = await db.leads.find_one({"_id": oid})
            await S.finalize_call({"endedReason": "customer-ended-call", "artifact": {"messages": [
                {"role": "user", "message": "Llámame más tarde"}]}, "analysis": {"structuredData": {"interest_score": 70}}}, lead)
            assert (await db.leads.find_one({"_id": oid}))["status"] == "rellamada"
            # finalize no_llamar -> cancels pending callback
            await db.leads.update_one({"_id": oid}, {"$set": {"status": "no_llamar"}})
            lead = await db.leads.find_one({"_id": oid})
            await S.finalize_call({"endedReason": "customer-ended-call", "artifact": {"messages": []}}, lead)
            assert (await db.leads.find_one({"_id": oid}))["status"] == "no_llamar"
            assert (await db.leads.find_one({"_id": cb["_id"]}))["status"] == "cancelada"
        finally:
            await db.leads.update_many({"_id": {"$in": created}, "status": "programada"}, {"$set": {"status": "cancelada"}})
            await db.leads.update_many({"_id": {"$in": created}}, {"$set": {"is_test": True}})
            await db.dnc.delete_many({"tenant_id": TENANT, "phone": "+34600000098"})


# ---------- API: /api/callbacks ----------
@pytest.fixture(scope="module")
def api_cb():
    """Create an isolated test callback (far future) via the tool flow, cancel at teardown."""
    async def mk():
        import services as S
        from db import db
        from models import Lead
        orig = Lead(tenant_id=TENANT, agent_id=AGENT, agent_name="Marta", name="TEST_API Rellamada",
                    phone="+34600000097", is_test=True, status="en_curso").to_mongo()
        orig["direction"] = "saliente"
        oid = (await db.leads.insert_one(orig)).inserted_id
        lead = await db.leads.find_one({"_id": oid})
        await S.handle_tool_calls({"toolCallList": [{"id": "x", "function": {
            "name": "schedule_callback", "arguments": {"date": "2026-11-10", "time": "11:00"}}}]}, lead)
        lead = await db.leads.find_one({"_id": oid})
        return str(oid), lead["callback_id"]

    async def clean(ids):
        from db import db
        from bson import ObjectId
        await db.leads.update_many({"_id": {"$in": [ObjectId(i) for i in ids]}, "status": "programada"},
                                   {"$set": {"status": "cancelada"}})
    oid, cid = run(mk())
    yield oid, cid
    run(clean([oid, cid]))


class TestCallbacksAPI:
    def test_requires_auth(self):
        assert requests.get(f"{BASE_URL}/api/callbacks").status_code == 401

    def test_list(self, admin, api_cb):
        oid, cid = api_cb
        r = admin.get(f"{BASE_URL}/api/callbacks", params={"start": "2026-11-09", "end": "2026-11-16"})
        assert r.status_code == 200
        items = {i["id"]: i for i in r.json()}
        assert cid in items
        it = items[cid]
        assert it["kind"] == "callback" and it["start"] == "2026-11-10T11:00"
        assert it["lead_name"] == "TEST_API Rellamada" and it["lead_phone"] == "+34600000097"
        assert it["lead_id"] == oid and it["callback_count"] == 1
        assert "_id" not in it

    def test_list_range_excludes(self, admin, api_cb):
        r = admin.get(f"{BASE_URL}/api/callbacks", params={"start": "2026-11-11", "end": "2026-11-16"})
        assert api_cb[1] not in [i["id"] for i in r.json()]

    def test_other_tenant_isolation(self, other, api_cb):
        cid = api_cb[1]
        r = other.get(f"{BASE_URL}/api/callbacks", params={"start": "2026-11-01", "end": "2026-12-01"})
        assert r.status_code == 200 and cid not in [i["id"] for i in r.json()]
        assert other.patch(f"{BASE_URL}/api/callbacks/{cid}", json={"start": "2026-11-11T10:00"}).status_code == 404
        assert other.delete(f"{BASE_URL}/api/callbacks/{cid}").status_code == 404

    @pytest.mark.parametrize("start", ["2026-10-01T10:00", "2026-11-14T10:00", "2026-11-11T08:30",
                                       "2026-11-11T21:00", "2026-11-11T21:30", "bad", "2026-11-11T25:00"])
    def test_patch_invalid(self, admin, api_cb, start):
        r = admin.patch(f"{BASE_URL}/api/callbacks/{api_cb[1]}", json={"start": start})
        assert r.status_code == 422, (start, r.status_code, r.text)

    def test_patch_unknown(self, admin):
        assert admin.patch(f"{BASE_URL}/api/callbacks/0123456789abcdef01234567",
                           json={"start": "2026-11-11T10:00"}).status_code == 404
        assert admin.patch(f"{BASE_URL}/api/callbacks/notanid", json={"start": "2026-11-11T10:00"}).status_code == 404

    def test_patch_valid_updates_original(self, admin, api_cb):
        oid, cid = api_cb
        r = admin.patch(f"{BASE_URL}/api/callbacks/{cid}", json={"start": "2026-11-12T20:45"})
        assert r.status_code == 200 and r.json()["start"] == "2026-11-12T20:45"
        items = admin.get(f"{BASE_URL}/api/callbacks", params={"start": "2026-11-12", "end": "2026-11-13"}).json()
        assert cid in [i["id"] for i in items]

        async def chk():
            from db import db
            from bson import ObjectId
            o = await db.leads.find_one({"_id": ObjectId(oid)})
            c = await db.leads.find_one({"_id": ObjectId(cid)})
            return o, c
        o, c = run(chk())
        assert o["callback_at"] == "2026-11-12T20:45"
        assert c["run_at"] == "2026-11-12T19:45:00+00:00"

    def test_delete(self, admin, api_cb):
        oid, cid = api_cb
        r = admin.delete(f"{BASE_URL}/api/callbacks/{cid}")
        assert r.status_code == 200 and r.json()["ok"] is True
        items = admin.get(f"{BASE_URL}/api/callbacks", params={"start": "2026-11-01", "end": "2026-12-01"}).json()
        assert cid not in [i["id"] for i in items]
        assert admin.delete(f"{BASE_URL}/api/callbacks/{cid}").status_code == 404

        async def chk():
            from db import db
            from bson import ObjectId
            return await db.leads.find_one({"_id": ObjectId(oid)}), await db.leads.find_one({"_id": ObjectId(cid)})
        o, c = run(chk())
        assert c["status"] == "cancelada" and o["callback_id"] is None

    def test_lead_detail_endpoint(self, admin, api_cb):
        r = admin.get(f"{BASE_URL}/api/leads/{api_cb[0]}")
        assert r.status_code == 200, r.text
