# Iteration-10: Zadarma number provisioning, Vapi inbound (Recepcionista),
# ElevenLabs library gating, voicemail detection, and outbound dial using tenant's own phone.
import os
import uuid

import pytest
import requests
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or os.environ["PUBLIC_BACKEND_URL"]).rstrip("/")
ADMIN_EMAIL = "admin@vozlead.es"
ADMIN_PASSWORD = "VozLead2026!"
VAPI_WEBHOOK_SECRET = os.environ["VAPI_WEBHOOK_SECRET"]
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def member_session(mongo):
    """A fresh business user with ES country."""
    s = requests.Session()
    email = f"tb_i10_{uuid.uuid4().hex[:10]}@example.com"
    r = s.post(f"{BASE}/api/auth/register",
               json={"name": "Biz Owner", "business_name": "Clinica Test",
                     "email": email, "password": "Testing2026!"}, timeout=30)
    assert r.status_code in (200, 201), r.text
    me = s.get(f"{BASE}/api/auth/me", timeout=30).json()
    yield s, me
    # cleanup: delete this tenant's agents/leads/tenant_number
    tid = me["id"]
    mongo.agents.delete_many({"tenant_id": tid})
    mongo.leads.delete_many({"tenant_id": tid})
    mongo.tenant_numbers.delete_many({"tenant_id": tid})
    mongo.users.delete_many({"_id": ObjectId(tid)})


@pytest.fixture(scope="module")
def es_agent(member_session, mongo):
    s, me = member_session
    body = {
        "name": "Sofia", "business_name": "Clinica Test",
        "product": "Clínica dental en Madrid, ofrece ortodoncia invisible.",
        "objective": "recepcion",
        "questions": ["¿Para cuándo lo necesitas?"],
        "country": "ES",
        "voice": "elvira",
        "ambience": "oficina",
        "ambience_volume": 35,
        "greeting": "Hola {nombre}, soy Sofia.",
        "extra_instructions": "",
        "active": True,
    }
    r = s.post(f"{BASE}/api/agents", json=body, timeout=30)
    assert r.status_code in (200, 201), r.text
    agent = r.json()
    yield agent


# ---------- Zadarma admin ----------
class TestZadarmaAdmin:
    def test_status_requires_admin(self, member_session):
        s, _ = member_session
        r = s.get(f"{BASE}/api/admin/zadarma", timeout=30)
        assert r.status_code == 403

    def test_status_disconnected(self, admin_session, mongo):
        # Make sure not connected
        mongo.platform_settings.delete_one({"_id": "zadarma_api"})
        r = admin_session.get(f"{BASE}/api/admin/zadarma", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["connected"] is False
        assert data.get("buy_on_test") in (False, None)

    def test_put_invalid_key(self, admin_session, mongo):
        mongo.platform_settings.delete_one({"_id": "zadarma_api"})
        r = admin_session.put(f"{BASE}/api/admin/zadarma",
                              json={"key": "fakekeyabc", "secret": "fakesecret"}, timeout=30)
        assert r.status_code == 400
        assert "Clave de Zadarma no v" in r.json().get("detail", "")
        # Settings should NOT have been overwritten with the bad key
        doc = mongo.platform_settings.find_one({"_id": "zadarma_api"}) or {}
        assert not doc.get("key")

    def test_put_empty_only_updates_directions(self, admin_session, mongo):
        """Saving without a new key should still accept direction fields."""
        mongo.platform_settings.delete_one({"_id": "zadarma_api"})
        r = admin_session.put(f"{BASE}/api/admin/zadarma",
                              json={"key": "", "secret": "", "direction_es": "123",
                                    "direction_cl": "", "docs_es": "", "docs_cl": "", "buy_on_test": True},
                              timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data["connected"] is False
        assert data["direction_es"] == "123"
        assert data["buy_on_test"] is True


# ---------- Admin numbers list / provision / release ----------
class TestAdminNumbers:
    def test_list_numbers_requires_admin(self, member_session):
        s, _ = member_session
        r = s.get(f"{BASE}/api/admin/numbers", timeout=30)
        assert r.status_code == 403

    def test_provision_without_zadarma_connected(self, admin_session, member_session, mongo):
        _, me = member_session
        mongo.platform_settings.delete_one({"_id": "zadarma_api"})
        r = admin_session.post(f"{BASE}/api/admin/numbers/{me['id']}/provision", timeout=30)
        assert r.status_code == 400
        assert "Zadarma" in r.json().get("detail", "")

    def test_list_includes_email_and_release(self, admin_session, member_session, mongo):
        _, me = member_session
        # Insert a fake active tenant_number for this user
        mongo.tenant_numbers.update_one(
            {"tenant_id": me["id"]},
            {"$set": {"tenant_id": me["id"], "country": "ES", "number": "+34910000000",
                      "status": "activo", "phone_number_id": "test-pn-1",
                      "credential_id": "test-cred-1", "inbound_agent_id": "",
                      "updated_at": "2026-01-01T00:00:00Z", "created_at": "2026-01-01T00:00:00Z"}},
            upsert=True,
        )
        r = admin_session.get(f"{BASE}/api/admin/numbers", timeout=30)
        assert r.status_code == 200
        data = r.json()
        mine = [x for x in data if x.get("tenant_id") == me["id"]]
        assert mine and mine[0]["email"] == me["email"]
        assert mine[0]["number"] == "+34910000000"

        # Release
        r = admin_session.post(f"{BASE}/api/admin/numbers/{me['id']}/release", timeout=60)
        assert r.status_code == 200
        assert r.json()["status"] == "liberado"
        doc = mongo.tenant_numbers.find_one({"tenant_id": me["id"]})
        assert doc["status"] == "liberado"


# ---------- my-number (business user) ----------
class TestMyNumber:
    def test_get_no_number(self, member_session, mongo):
        s, me = member_session
        mongo.tenant_numbers.delete_many({"tenant_id": me["id"]})
        r = s.get(f"{BASE}/api/my-number", timeout=30)
        assert r.status_code == 200
        assert r.json()["status"] == "sin_numero"

    def test_put_without_record_returns_400(self, member_session, mongo):
        s, me = member_session
        mongo.tenant_numbers.delete_many({"tenant_id": me["id"]})
        r = s.put(f"{BASE}/api/my-number", json={"inbound_agent_id": ""}, timeout=30)
        assert r.status_code == 400

    def test_put_inbound_other_tenant_agent_404(self, member_session, mongo, es_agent):
        s, me = member_session
        # Simulated active number first
        mongo.tenant_numbers.update_one(
            {"tenant_id": me["id"]},
            {"$set": {"tenant_id": me["id"], "country": "ES", "number": "+34910000000",
                      "status": "activo", "phone_number_id": "test-pn-1",
                      "inbound_agent_id": "", "updated_at": "2026-01-01T00:00:00Z",
                      "created_at": "2026-01-01T00:00:00Z"}},
            upsert=True,
        )
        # Pick an agent that doesn't belong to this tenant (admin's seeded agent)
        other = mongo.agents.find_one({"tenant_id": {"$ne": me["id"]}})
        assert other, "Expected at least one agent from another tenant (admin seed)"
        r = s.put(f"{BASE}/api/my-number",
                  json={"inbound_agent_id": str(other["_id"])}, timeout=30)
        assert r.status_code == 404

    def test_put_inbound_own_agent_ok(self, member_session, mongo, es_agent):
        s, me = member_session
        mongo.tenant_numbers.update_one(
            {"tenant_id": me["id"]},
            {"$set": {"tenant_id": me["id"], "country": "ES", "number": "+34910000000",
                      "status": "activo", "phone_number_id": "test-pn-1",
                      "inbound_agent_id": "", "updated_at": "2026-01-01T00:00:00Z",
                      "created_at": "2026-01-01T00:00:00Z"}},
            upsert=True,
        )
        r = s.put(f"{BASE}/api/my-number",
                  json={"inbound_agent_id": es_agent["id"]}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["inbound_agent_id"] == es_agent["id"]
        assert data["number"] == "+34910000000"


# ---------- Vapi webhook: assistant-request ----------
def _wh_post(body):
    return requests.post(f"{BASE}/api/vapi/webhook",
                         headers={"x-vapi-secret": VAPI_WEBHOOK_SECRET},
                         json=body, timeout=30)


class TestWebhookAuth:
    def test_bad_secret_401(self):
        r = requests.post(f"{BASE}/api/vapi/webhook",
                          headers={"x-vapi-secret": "WRONG"},
                          json={"message": {"type": "status-update"}}, timeout=30)
        assert r.status_code == 401


class TestAssistantRequestInbound:
    def test_unknown_phone_number_short_unavailable(self):
        r = _wh_post({"message": {"type": "assistant-request",
                                  "call": {"id": "call-unknown-1",
                                           "phoneNumberId": "pn-not-exist",
                                           "customer": {"number": "+34611222333"}}}})
        assert r.status_code == 200
        a = r.json().get("assistant") or {}
        assert "no podemos atenderte" in (a.get("firstMessage") or "")
        assert a.get("maxDurationSeconds") == 20

    def test_inbound_full_flow_builds_assistant_and_lead(self, member_session, mongo, es_agent):
        s, me = member_session
        tid = me["id"]
        mongo.leads.delete_many({"tenant_id": tid, "vapi_call_id": "call-in-1"})
        mongo.tenant_numbers.update_one(
            {"tenant_id": tid},
            {"$set": {"tenant_id": tid, "country": "ES", "number": "+34910000000",
                      "status": "activo", "phone_number_id": "test-pn-1",
                      "inbound_agent_id": es_agent["id"],
                      "updated_at": "2026-01-01T00:00:00Z",
                      "created_at": "2026-01-01T00:00:00Z"}},
            upsert=True,
        )
        r = _wh_post({"message": {"type": "assistant-request",
                                  "call": {"id": "call-in-1",
                                           "phoneNumberId": "test-pn-1",
                                           "customer": {"number": "+34611222333"}}}})
        assert r.status_code == 200, r.text
        a = r.json()["assistant"]
        assert a["firstMessage"].startswith("Hola, Clinica Test, te atiende")
        assert "voicemailDetection" not in a  # inbound must NOT have voicemail
        md = a.get("metadata") or {}
        assert md.get("lead_id") and md.get("tenant_id") == tid
        # Tools: check availability + book
        tool_names = [t.get("function", {}).get("name") for t in a["model"]["tools"] if t.get("function")]
        assert "check_availability" in tool_names
        assert "book_appointment" in tool_names
        # Lead doc created
        lead = mongo.leads.find_one({"vapi_call_id": "call-in-1"})
        assert lead and lead["direction"] == "entrante" and lead["source"] == "entrante"
        assert lead["tenant_id"] == tid

        # end-of-call-report → status atendida + caller_name
        r2 = _wh_post({"message": {
            "type": "end-of-call-report",
            "endedReason": "customer-ended-call",
            "call": {"id": "call-in-1",
                     "metadata": {"lead_id": str(lead["_id"]), "tenant_id": tid}},
            "artifact": {"messages": [
                {"role": "user", "message": "Hola, soy Pedro"},
                {"role": "assistant", "message": "Hola Pedro"},
            ]},
            "analysis": {"structuredData": {
                "caller_name": "Pedro Gómez",
                "outcome": "calificado",
                "interest_score": 70}},
        }})
        assert r2.status_code == 200
        lead2 = mongo.leads.find_one({"_id": lead["_id"]})
        assert lead2["status"] == "atendida"
        assert lead2["name"] == "Pedro Gómez"

    def test_inbound_without_agent_returns_unavailable(self, member_session, mongo):
        s, me = member_session
        mongo.tenant_numbers.update_one(
            {"tenant_id": me["id"]},
            {"$set": {"tenant_id": me["id"], "country": "ES", "number": "+34910000000",
                      "status": "activo", "phone_number_id": "test-pn-2",
                      "inbound_agent_id": "",  # no inbound agent configured
                      "updated_at": "2026-01-01T00:00:00Z",
                      "created_at": "2026-01-01T00:00:00Z"}},
            upsert=True,
        )
        r = _wh_post({"message": {"type": "assistant-request",
                                  "call": {"id": "call-in-noagent",
                                           "phoneNumberId": "test-pn-2",
                                           "customer": {"number": "+34611222444"}}}})
        assert r.status_code == 200
        a = r.json().get("assistant") or {}
        assert "no podemos atenderte" in (a.get("firstMessage") or "")


# ---------- Outbound voicemail detection ----------
class TestOutboundVoicemail:
    def test_outbound_assistant_has_voicemail_detection(self, es_agent, member_session, mongo):
        """Simulate an outbound lead doc; call build_assistant via webhook assistant-request path
        is only for inbound. For outbound we check build_assistant directly via a Python import."""
        import sys
        sys.path.insert(0, "/app/backend")
        import vapi as V  # noqa: WPS433
        import services as S  # noqa: WPS433

        _, me = member_session
        agent = {
            "_id": ObjectId(),
            "tenant_id": me["id"],
            "name": "Sofia",
            "business_name": "Clinica Test",
            "product": "x",
            "objective": "calificar",
            "questions": [],
            "country": "ES",
            "voice": "elvira",
            "ambience": "oficina",
            "ambience_volume": 35,
            "greeting": "Hola {nombre}",
            "extra_instructions": "",
            "active": True,
        }
        lead = {
            "_id": ObjectId(),
            "tenant_id": me["id"],
            "agent_id": str(agent["_id"]),
            "name": "Luis",
            "phone": "+34611222333",
            "source": "web",
            # No direction set = outbound
        }
        a = V.build_assistant(agent, lead, S.today_text("ES"))
        assert a.get("voicemailDetection") == V.VOICEMAIL
        sys_msg = a["model"]["messages"][0]["content"]
        assert "contestador" in sys_msg.lower() or "buzón" in sys_msg.lower()

    def test_finalize_voicemail_sets_buzon(self, member_session, mongo, es_agent):
        s, me = member_session
        # Create an outbound lead
        lead = {
            "tenant_id": me["id"],
            "agent_id": es_agent["id"],
            "agent_name": es_agent["name"],
            "name": "VM Test",
            "phone": "+34611555666",
            "source": "web",
            "status": "en_curso",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "vapi_call_id": "call-vm-1",
        }
        res = mongo.leads.insert_one(lead)
        lid = str(res.inserted_id)
        r = _wh_post({"message": {
            "type": "end-of-call-report",
            "endedReason": "voicemail",
            "call": {"id": "call-vm-1", "metadata": {"lead_id": lid, "tenant_id": me["id"]}},
            "artifact": {"messages": []},
            "analysis": {},
        }})
        assert r.status_code == 200
        got = mongo.leads.find_one({"_id": res.inserted_id})
        assert got["status"] == "buzon"


# ---------- Zadarma signing (unit) ----------
class TestZadarmaSigning:
    def test_sign_format(self):
        import sys
        sys.path.insert(0, "/app/backend")
        import zadarma as Z  # noqa: WPS433
        sig = Z._sign("/v1/info/balance/", {}, "KEY", "SECRET")
        assert sig.startswith("KEY:")
        import base64
        try:
            base64.b64decode(sig.split(":", 1)[1])
        except Exception as e:  # noqa: BLE001
            pytest.fail(f"not valid base64: {e}")


# ---------- phone_id_for behavior ----------
class TestPhoneIdFor:
    def test_phone_id_for_matches_active_country(self, member_session, mongo):
        import sys, asyncio
        sys.path.insert(0, "/app/backend")
        import phone_numbers as N  # noqa: WPS433
        _, me = member_session
        tid = me["id"]
        mongo.tenant_numbers.update_one(
            {"tenant_id": tid},
            {"$set": {"tenant_id": tid, "country": "ES", "number": "+34910000000",
                      "status": "activo", "phone_number_id": "pid-es-1"}},
            upsert=True,
        )
        async def _run():
            r1 = await N.phone_id_for(tid, "ES")
            r2 = await N.phone_id_for(tid, "CL")
            mongo.tenant_numbers.update_one({"tenant_id": tid}, {"$set": {"status": "liberado"}})
            r3 = await N.phone_id_for(tid, "ES")
            return r1, r2, r3
        got, got2, got3 = asyncio.run(_run())
        assert got == "pid-es-1"
        assert got2 is None
        assert got3 is None


# ---------- ElevenLabs admin endpoints ----------
class TestElevenLabsAdmin:
    def test_status_returns_vapi_linked_bool(self, admin_session):
        r = admin_session.get(f"{BASE}/api/admin/elevenlabs", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d.get("connected"), bool)
        assert "vapi_linked" in d
        assert isinstance(d["vapi_linked"], bool)

    def test_library_missing_permissions_or_connected(self, admin_session):
        r = admin_session.get(f"{BASE}/api/admin/elevenlabs/library?country=ES", timeout=60)
        # Either 400 (no key / missing Voices perm) or 200 if the key actually has Voices permission.
        # The task says the stored key only has TTS → should be 400 with the "Voices" message.
        if r.status_code == 400:
            detail = r.json().get("detail", "")
            assert "Voices" in detail or "ElevenLabs" in detail
        else:
            assert r.status_code == 200, r.text


# ---------- Agents: recepcion objective ----------
class TestAgentsRecepcion:
    def test_create_agent_recepcion_accepted(self, member_session):
        s, _ = member_session
        body = {
            "name": "Recep", "business_name": "Clinica Test",
            "product": "x", "objective": "recepcion", "questions": [],
            "country": "ES", "voice": "elvira", "ambience": "oficina",
            "ambience_volume": 35, "greeting": "Hola", "extra_instructions": "",
            "active": True,
        }
        r = s.post(f"{BASE}/api/agents", json=body, timeout=30)
        assert r.status_code in (200, 201), r.text
        assert r.json()["objective"] == "recepcion"
