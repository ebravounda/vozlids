"""Backend tests for VozLeads platform-inbound (admin) + Vapi assistant-request webhook."""
import os
import sys
import pytest

SKIP_LIVE = pytest.mark.skip(reason="re-points the shared Vapi number to preview; run only on purpose")
import requests
from pathlib import Path

# load backend .env
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

BASE_URL = os.environ["PUBLIC_BACKEND_URL"].rstrip("/")
VAPI_SECRET = os.environ["VAPI_WEBHOOK_SECRET"]
ADMIN_EMAIL = os.environ["ADMIN_EMAIL"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]

ES_AGENT_ID = "6acfac3a346c4c1ebc71ff58"
ES_PHONE_ID = "69c05ec5-d39d-4948-a76d-33329aa4ada5"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def anon_session():
    return requests.Session()


# --- GET /api/admin/platform-inbound ---
def test_get_platform_inbound_admin(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/admin/platform-inbound")
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list) and len(data) >= 1
    es = next((x for x in data if x["country"] == "ES"), None)
    assert es is not None, f"no ES row: {data}"
    assert es["number"] == "+34919932652"
    assert es["enabled"] is True
    assert es["agent_id"] == ES_AGENT_ID
    assert es["sip_uri"] == "34919932652@8aa11b2f-c982-434a-b6c6-1e9fded14d7e.sip.vapi.ai"
    assert "routed" in es


def test_get_platform_inbound_non_admin(anon_session):
    r = anon_session.get(f"{BASE_URL}/api/admin/platform-inbound")
    assert r.status_code in (401, 403)


# --- PUT /api/admin/platform-inbound ---
@SKIP_LIVE
def test_put_platform_inbound_invalid_agent(admin_session):
    r = admin_session.put(f"{BASE_URL}/api/admin/platform-inbound",
                          json={"country": "ES", "agent_id": "000000000000000000000000"})
    assert r.status_code == 404


def test_put_platform_inbound_country_cl_no_line(admin_session):
    r = admin_session.put(f"{BASE_URL}/api/admin/platform-inbound",
                          json={"country": "CL", "agent_id": ES_AGENT_ID})
    assert r.status_code == 400
    msg = r.json().get("detail", "")
    # Should be Spanish, mentioning line/country
    assert any(w in msg.lower() for w in ["línea", "linea", "país", "conecta"]), msg


@SKIP_LIVE
def test_put_platform_inbound_es_idempotent(admin_session):
    r = admin_session.put(f"{BASE_URL}/api/admin/platform-inbound",
                          json={"country": "ES", "agent_id": ES_AGENT_ID})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("ok") is True
    assert data.get("sip_uri") == "34919932652@8aa11b2f-c982-434a-b6c6-1e9fded14d7e.sip.vapi.ai"


# --- Vapi webhook assistant-request ---
def _cleanup_tst_leads():
    """Delete leads with vapi_call_id starting 'tst-' via direct Mongo."""
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    async def _run():
        res = await db.leads.delete_many({"vapi_call_id": {"$regex": "^tst-"}})
        return res.deleted_count
    n = asyncio.get_event_loop().run_until_complete(_run()) if not asyncio.get_event_loop().is_running() else 0
    client.close()
    return n


def test_webhook_assistant_request_known_phone(anon_session):
    import uuid
    call_id = f"tst-{uuid.uuid4().hex[:10]}"
    body = {
        "message": {
            "type": "assistant-request",
            "call": {
                "id": call_id,
                "phoneNumberId": ES_PHONE_ID,
                "customer": {"number": "+34600111222"},
            },
        }
    }
    r = anon_session.post(
        f"{BASE_URL}/api/vapi/webhook?token={VAPI_SECRET}",
        json=body,
        headers={"x-vapi-secret": VAPI_SECRET},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assistant = data.get("assistant") or {}
    first = assistant.get("firstMessage", "")
    assert first.startswith("Hola, OpenFactura.es, te atiende Marta"), first
    assert "asistente virtual" not in first.lower()


def test_webhook_assistant_request_unknown_phone(anon_session):
    import uuid
    call_id = f"tst-{uuid.uuid4().hex[:10]}"
    body = {
        "message": {
            "type": "assistant-request",
            "call": {
                "id": call_id,
                "phoneNumberId": "00000000-0000-0000-0000-000000000000",
                "customer": {"number": "+34600111222"},
            },
        }
    }
    r = anon_session.post(
        f"{BASE_URL}/api/vapi/webhook?token={VAPI_SECRET}",
        json=body,
        headers={"x-vapi-secret": VAPI_SECRET},
    )
    assert r.status_code == 200, r.text
    first = (r.json().get("assistant") or {}).get("firstMessage", "")
    assert "no podemos atenderte" in first.lower(), first


def test_zz_cleanup_tst_leads():
    # Last test: clean up leads with vapi_call_id starting 'tst-'
    import pymongo
    client = pymongo.MongoClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    res = db.leads.delete_many({"vapi_call_id": {"$regex": "^tst-"}})
    client.close()
    print(f"Cleaned up {res.deleted_count} test leads")
    assert res.deleted_count >= 1  # we created at least 1 above
