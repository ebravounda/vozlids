# Iteration-8: Landing (public info-request + admin landing config) tests
import os
import uuid
import time

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or os.environ["PUBLIC_BACKEND_URL"]).rstrip("/")
ADMIN_EMAIL = "admin@vozlead.es"
ADMIN_PASSWORD = "VozLead2026!"

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


@pytest.fixture(autouse=True)
def _clean_info_requests(mongo):
    """Rate-limit is per IP (and preview ingress forwards a shared one). Clear before every test."""
    mongo.info_requests.delete_many({})
    yield


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def member_session():
    s = requests.Session()
    email = f"tb_land_{uuid.uuid4().hex[:10]}@example.com"
    r = s.post(f"{BASE}/api/auth/register",
               json={"name": "T", "business_name": "Biz", "email": email, "password": "Testing2026!"},
               timeout=30)
    assert r.status_code in (200, 201), r.text
    return s


@pytest.fixture(scope="module")
def _reset_landing(admin_session, mongo):
    """Make sure landing config starts empty; clean up at end."""
    admin_session.put(f"{BASE}/api/admin/landing",
                      json={"agent_es": "", "agent_cl": "", "notify_email": ""}, timeout=30)
    yield
    admin_session.put(f"{BASE}/api/admin/landing",
                      json={"agent_es": "", "agent_cl": "", "notify_email": ""}, timeout=30)


# ---------- POST /api/public/info-request ----------
def test_info_request_rejects_without_consent(_reset_landing):
    r = requests.post(f"{BASE}/api/public/info-request",
                      json={"name": "Juan Test", "phone": "+34600000001", "country": "ES",
                            "consent": False, "page": "/"}, timeout=20)
    assert r.status_code == 400, r.text


def test_info_request_rejects_bad_country(_reset_landing):
    r = requests.post(f"{BASE}/api/public/info-request",
                      json={"name": "Juan", "phone": "+34600000002", "country": "US",
                            "consent": True, "page": "/"}, timeout=20)
    assert r.status_code == 422, r.text


def test_info_request_rejects_bad_phone(_reset_landing):
    r = requests.post(f"{BASE}/api/public/info-request",
                      json={"name": "Juan", "phone": "12345", "country": "ES",
                            "consent": True, "page": "/"}, timeout=20)
    # norm_phone raises HTTPException(422)
    assert r.status_code == 422, r.text


def test_info_request_valid_without_agent_saves_sin_agente(_reset_landing, mongo):
    r = requests.post(f"{BASE}/api/public/info-request",
                      json={"name": "Juan  Perez", "phone": "+34600000003", "country": "ES",
                            "consent": True, "page": "/"}, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["calling"] is False
    doc = mongo.info_requests.find_one({"phone": "+34600000003"})
    assert doc is not None
    assert doc["call_status"] == "sin_agente"
    assert doc["country"] == "ES"
    assert doc["name"] == "Juan Perez"  # whitespace normalized


def test_info_request_valid_cl(_reset_landing, mongo):
    r = requests.post(f"{BASE}/api/public/info-request",
                      json={"name": "Pedro CL", "phone": "+56912345678", "country": "CL",
                            "consent": True, "page": "/cl"}, timeout=30)
    assert r.status_code == 200, r.text
    doc = mongo.info_requests.find_one({"phone": "+56912345678"})
    assert doc and doc["country"] == "CL" and doc["page"] == "/cl"


def test_info_request_duplicate_within_24h_marked_repetida(_reset_landing, mongo):
    payload = {"name": "Ana R", "phone": "+34600000004", "country": "ES",
               "consent": True, "page": "/"}
    r1 = requests.post(f"{BASE}/api/public/info-request", json=payload, timeout=20)
    assert r1.status_code == 200, r1.text
    r2 = requests.post(f"{BASE}/api/public/info-request", json=payload, timeout=20)
    assert r2.status_code == 200, r2.text
    docs = list(mongo.info_requests.find({"phone": "+34600000004"}))
    assert len(docs) == 2
    statuses = sorted(d["call_status"] for d in docs)
    assert "repetida" in statuses


def test_info_request_rate_limit_4th_in_10min_returns_429(_reset_landing):
    # 3 different phones should pass; 4th hits rate limit per IP
    phones = ["+34600000011", "+34600000012", "+34600000013", "+34600000014"]
    codes = []
    for i, ph in enumerate(phones):
        r = requests.post(f"{BASE}/api/public/info-request",
                          json={"name": f"User {i}", "phone": ph, "country": "ES",
                                "consent": True, "page": "/"}, timeout=20)
        codes.append(r.status_code)
    assert codes[:3] == [200, 200, 200], codes
    assert codes[3] == 429, codes


# ---------- GET /api/admin/info-requests ----------
def test_admin_info_requests_requires_admin(member_session):
    r = member_session.get(f"{BASE}/api/admin/info-requests", timeout=20)
    assert r.status_code == 403, r.text


def test_admin_info_requests_lists(admin_session, _reset_landing, mongo):
    requests.post(f"{BASE}/api/public/info-request",
                  json={"name": "Lista Test", "phone": "+34600000021", "country": "ES",
                        "consent": True, "page": "/"}, timeout=20)
    r = admin_session.get(f"{BASE}/api/admin/info-requests", timeout=20)
    assert r.status_code == 200, r.text
    items = r.json()
    assert isinstance(items, list)
    assert any(x["phone"] == "+34600000021" for x in items)
    # No ip field exposed, no mongo _id, has id
    for x in items:
        assert "ip" not in x
        assert "_id" not in x
        assert "id" in x


# ---------- /api/admin/landing GET/PUT ----------
def test_admin_landing_get_requires_admin(member_session):
    r = member_session.get(f"{BASE}/api/admin/landing", timeout=20)
    assert r.status_code == 403, r.text


def test_admin_landing_get_default_empty(admin_session, _reset_landing):
    r = admin_session.get(f"{BASE}/api/admin/landing", timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data == {"agent_es": "", "agent_cl": "", "notify_email": ""}


def test_admin_landing_put_rejects_mismatched_country(admin_session, _reset_landing):
    # create a CL agent and try to assign it as agent_es -> expect 422
    agent_body = {
        "name": "Agent CL Test", "business_name": "Biz CL", "product": "p",
        "objective": "agendar", "questions": [], "country": "CL",
        "voice": "cl_catalina", "ambience": "oficina", "ambience_volume": 35,
        "greeting": "Hola", "extra_instructions": "", "active": True,
    }
    cr = admin_session.post(f"{BASE}/api/agents", json=agent_body, timeout=30)
    assert cr.status_code in (200, 201), cr.text
    cl_agent_id = cr.json()["id"]
    try:
        r = admin_session.put(f"{BASE}/api/admin/landing",
                              json={"agent_es": cl_agent_id, "agent_cl": "", "notify_email": ""},
                              timeout=20)
        assert r.status_code == 422, r.text
        # And correct assignment works
        r2 = admin_session.put(f"{BASE}/api/admin/landing",
                               json={"agent_es": "", "agent_cl": cl_agent_id,
                                     "notify_email": "admin@vozlead.es"},
                               timeout=20)
        assert r2.status_code == 200, r2.text
        get_r = admin_session.get(f"{BASE}/api/admin/landing", timeout=20)
        assert get_r.json()["agent_cl"] == cl_agent_id
        assert get_r.json()["notify_email"] == "admin@vozlead.es"
    finally:
        admin_session.delete(f"{BASE}/api/agents/{cl_agent_id}", timeout=20)


def test_info_request_with_agent_configured_creates_lead(admin_session, _reset_landing, mongo):
    """When an active agent is configured for ES, submitting an info-request creates a Lead."""
    agent_body = {
        "name": "Agent ES Landing", "business_name": "Biz ES", "product": "p",
        "objective": "agendar", "questions": [], "country": "ES",
        "voice": "elvira", "ambience": "oficina", "ambience_volume": 35,
        "greeting": "Hola", "extra_instructions": "", "active": True,
    }
    cr = admin_session.post(f"{BASE}/api/agents", json=agent_body, timeout=30)
    assert cr.status_code in (200, 201), cr.text
    es_agent_id = cr.json()["id"]
    tenant_id = cr.json()["tenant_id"]
    try:
        pr = admin_session.put(f"{BASE}/api/admin/landing",
                               json={"agent_es": es_agent_id, "agent_cl": "", "notify_email": ""},
                               timeout=20)
        assert pr.status_code == 200, pr.text

        phone = "+34600000099"
        r = requests.post(f"{BASE}/api/public/info-request",
                          json={"name": "Lead Landing", "phone": phone, "country": "ES",
                                "consent": True, "page": "/"}, timeout=60)
        assert r.status_code == 200, r.text
        # Give dial some time to run (async). It may end 'fallida' (no VAPI number) — that's ok.
        time.sleep(2)
        ir = mongo.info_requests.find_one({"phone": phone})
        assert ir is not None
        # call_status should be anything but 'sin_agente' since an agent is now configured.
        assert ir["call_status"] != "sin_agente", ir
        # A Lead should exist with source web_vozleads + max_seconds 45
        lead = mongo.leads.find_one({"phone": phone, "tenant_id": tenant_id})
        assert lead is not None, "Lead was not created"
        assert lead.get("source") == "web_vozleads"
        assert lead.get("max_seconds") == 45
    finally:
        # cleanup lead + agent + reset landing
        mongo.leads.delete_many({"agent_id": es_agent_id})
        admin_session.put(f"{BASE}/api/admin/landing",
                          json={"agent_es": "", "agent_cl": "", "notify_email": ""}, timeout=20)
        admin_session.delete(f"{BASE}/api/agents/{es_agent_id}", timeout=20)


# ---------- static assets (frontend served through same origin) ----------
def test_robots_txt_served():
    r = requests.get(f"{BASE}/robots.txt", timeout=20)
    assert r.status_code == 200, r.status_code
    assert "User-agent" in r.text or "user-agent" in r.text.lower()


def test_sitemap_xml_served():
    r = requests.get(f"{BASE}/sitemap.xml", timeout=20)
    assert r.status_code == 200, r.status_code
    assert "<urlset" in r.text or "<sitemapindex" in r.text
