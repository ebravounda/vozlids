"""Backend tests for VozLeads platform-inbound (admin) + Vapi assistant-request webhook.

Iter-16: covers the new Vapi free-SIP inbound target (dc43e89e-...) that was
created to work around Zadarma INVITEs being rejected by the BYO-SIP IP whitelist.
PUT /api/admin/platform-inbound is intentionally skipped: it would re-point the
shared live number to this preview env.
"""
import os
import sys
import uuid
import pytest
import requests

SKIP_LIVE = pytest.mark.skip(
    reason="re-points the shared live Vapi number to preview; skipped on purpose"
)

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

BASE_URL = os.environ["PUBLIC_BACKEND_URL"].rstrip("/")
VAPI_SECRET = os.environ["VAPI_WEBHOOK_SECRET"]
ADMIN_EMAIL = os.environ["ADMIN_EMAIL"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]

ES_AGENT_ID = "6acfac3a346c4c1ebc71ff58"
# BYO-SIP phone-number id (Zadarma trunk) — must still resolve via inbound_phone_number_id OR phone_number_id
BYO_PHONE_ID = "69c05ec5-d39d-4948-a76d-33329aa4ada5"
# Vapi free-SIP phone-number id used as actual inbound target (sip:34919932652@sip.vapi.ai)
SIP_PHONE_ID = "dc43e89e-276b-44fa-bd5d-de43e6de85af"
EXPECTED_SIP_URI = "34919932652@sip.vapi.ai"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def anon_session():
    return requests.Session()


# --------------------- GET /api/admin/platform-inbound ---------------------
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
    assert es["sip_uri"] == EXPECTED_SIP_URI, es
    assert "routed" in es


def test_get_platform_inbound_non_admin(anon_session):
    r = anon_session.get(f"{BASE_URL}/api/admin/platform-inbound")
    assert r.status_code in (401, 403)


# --------------------- PUT /api/admin/platform-inbound (all skipped) ---------------------
@SKIP_LIVE
def test_put_platform_inbound_invalid_agent(admin_session):
    r = admin_session.put(f"{BASE_URL}/api/admin/platform-inbound",
                          json={"country": "ES", "agent_id": "000000000000000000000000"})
    assert r.status_code == 404


@SKIP_LIVE
def test_put_platform_inbound_country_cl_no_line(admin_session):
    r = admin_session.put(f"{BASE_URL}/api/admin/platform-inbound",
                          json={"country": "CL", "agent_id": ES_AGENT_ID})
    assert r.status_code == 400


@SKIP_LIVE
def test_put_platform_inbound_es_idempotent(admin_session):
    r = admin_session.put(f"{BASE_URL}/api/admin/platform-inbound",
                          json={"country": "ES", "agent_id": ES_AGENT_ID})
    assert r.status_code == 200, r.text


# --------------------- Vapi webhook assistant-request ---------------------
def _webhook(anon_session: requests.Session, phone_id: str, customer: dict | None):
    call = {"id": f"tst-{uuid.uuid4().hex[:10]}", "phoneNumberId": phone_id}
    if customer is not None:
        call["customer"] = customer
    body = {"message": {"type": "assistant-request", "call": call}}
    r = anon_session.post(
        f"{BASE_URL}/api/vapi/webhook",
        json=body,
        headers={"x-vapi-secret": VAPI_SECRET},
    )
    return r


def test_webhook_assistant_request_vapi_sip_phone(anon_session):
    """New free-SIP phone id (actual inbound target) must resolve to the ES Marta agent."""
    r = _webhook(anon_session, SIP_PHONE_ID, {"number": "+34600111222"})
    assert r.status_code == 200, r.text
    first = (r.json().get("assistant") or {}).get("firstMessage", "")
    assert first.startswith("Hola, OpenFactura.es, te atiende Marta"), first
    assert "asistente virtual" not in first.lower()


def test_webhook_assistant_request_byo_phone_still_works(anon_session):
    """Legacy BYO-SIP phone id must still resolve (via phone_number_id)."""
    r = _webhook(anon_session, BYO_PHONE_ID, {"number": "+34600111222"})
    assert r.status_code == 200, r.text
    first = (r.json().get("assistant") or {}).get("firstMessage", "")
    assert first.startswith("Hola, OpenFactura.es, te atiende Marta"), first


def test_webhook_assistant_request_unknown_phone(anon_session):
    r = _webhook(anon_session, "00000000-0000-0000-0000-000000000000", {"number": "+34600111222"})
    assert r.status_code == 200, r.text
    first = (r.json().get("assistant") or {}).get("firstMessage", "")
    assert "no podemos atenderte" in first.lower(), first


def test_webhook_assistant_request_missing_customer_number(anon_session):
    """customer.number absent must not 500 (phone falls back to 'oculto')."""
    r = _webhook(anon_session, SIP_PHONE_ID, {})
    assert r.status_code == 200, r.text
    first = (r.json().get("assistant") or {}).get("firstMessage", "")
    assert first.startswith("Hola, OpenFactura.es, te atiende Marta"), first


def test_webhook_assistant_request_missing_customer_object(anon_session):
    """customer object absent must not 500."""
    r = _webhook(anon_session, SIP_PHONE_ID, None)
    assert r.status_code == 200, r.text
    first = (r.json().get("assistant") or {}).get("firstMessage", "")
    assert first.startswith("Hola, OpenFactura.es, te atiende Marta"), first


def test_webhook_assistant_request_sip_format_number(anon_session):
    """customer.number as sip URI must not 500."""
    r = _webhook(anon_session, SIP_PHONE_ID, {"number": "sip:anon@sip.vapi.ai"})
    assert r.status_code == 200, r.text
    first = (r.json().get("assistant") or {}).get("firstMessage", "")
    assert first.startswith("Hola, OpenFactura.es, te atiende Marta"), first


# --------------------- Cleanup ---------------------
def test_zz_cleanup_tst_leads():
    import pymongo
    client = pymongo.MongoClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    res = db.leads.delete_many({"vapi_call_id": {"$regex": "^tst-"}})
    client.close()
    print(f"Cleaned up {res.deleted_count} test leads")
    assert res.deleted_count >= 1
