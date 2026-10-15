"""Iter-24: API Phase 2 - per-key request log, RGPD export/erase (API + dashboard), transcript retention + purge."""
import asyncio
import os
import sys
import time
import uuid

import pytest
import requests
from bson import ObjectId
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
V1 = f"{BASE_URL}/api/v1"
API = f"{BASE_URL}/api"
ADMIN = {"email": "admin@vozlead.es", "password": "VozLead2026!"}
ALL = ["agents:read", "calls:read", "calls:write", "account:read", "webhooks:manage", "dnc:manage", "privacy:manage"]
SUF = str(int(time.time()))[-4:]
PH1 = f"+3461122{SUF}"          # sandbox call subject
PH_DNC = f"+3461123{SUF}"       # dnc-kept subject
EMAIL1 = f"test_rgpd_{SUF}@example.com"


def _db():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture(scope="module")
def admin():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, r.text
    return {"hdr": {"Authorization": f"Bearer {r.json()['access_token']}"}, "id": r.json().get("id") or r.json().get("user", {}).get("id")}


@pytest.fixture(scope="module")
def t2():
    s = uuid.uuid4().hex[:8]
    r = requests.post(f"{API}/auth/register", timeout=15, json={"name": "T2", "business_name": f"TEST biz {s}",
                      "email": f"TEST_iter24_{s}@vozlead-test.es", "password": "Password123!", "country": "ES"})
    assert r.status_code == 200, r.text
    yield {"hdr": {"Authorization": f"Bearer {r.json()['access_token']}"}, "id": r.json()["id"]}
    d = _db()
    d.leads.delete_many({"tenant_id": r.json()["id"]})
    d.api_keys.delete_many({"tenant_id": r.json()["id"]})
    d.privacy_log.delete_many({"tenant_id": r.json()["id"]})
    d.users.delete_many({"email": {"$regex": "^TEST_iter24_", "$options": "i"}})


@pytest.fixture(scope="module")
def keys(admin, t2):
    out = {}
    for name, hdr, scopes in (("full", admin["hdr"], ALL), ("nopriv", admin["hdr"], ALL[:-1]), ("t2", t2["hdr"], ALL)):
        r = requests.post(f"{API}/developer/keys", headers=hdr, timeout=15, json={"name": f"iter24-{name}", "env": "test", "scopes": scopes})
        assert r.status_code == 200, r.text
        out[name] = r.json()
    yield out
    d = _db()
    for k in out.values():
        d.api_keys.delete_one({"_id": ObjectId(k["id"])})
    requests.put(f"{API}/privacy/retention", headers=admin["hdr"], json={"days": 0}, timeout=10)


def H(keys, n="full"):
    return {"X-API-Key": keys[n]["key"]}


# ---- scope & request log ----
def test_scope_privacy_manage_exists(admin):
    r = requests.get(f"{API}/developer/overview", headers=admin["hdr"], timeout=10)
    assert r.status_code == 200
    assert "privacy:manage" in str(r.json())


def test_request_log_recorded_with_masking(keys, admin):
    h = H(keys)
    assert requests.get(f"{V1}/agents", headers=h, timeout=10).status_code == 200
    assert requests.get(f"{V1}/calls/{'0'*24}", headers=h, timeout=10).status_code == 404
    r = requests.delete(f"{V1}/dnc/+34611223344", headers=h, timeout=10)
    assert r.status_code == 204
    time.sleep(1.5)
    r = requests.get(f"{API}/privacy/keys/{keys['full']['id']}/requests", headers=admin["hdr"], timeout=10)
    assert r.status_code == 200, r.text
    d = r.json()
    s = d["summary"]
    assert s["days"] == 30 and s["total"] >= 3 and s["errors"] >= 1 and isinstance(s["avg_ms"], int)
    row = d["data"][0]
    for f in ("method", "path", "status", "duration_ms", "ip", "request_id", "at"):
        assert f in row
    paths = [x["path"] for x in d["data"]]
    assert any(p.endswith("/dnc/***") for p in paths), paths
    assert not any("611223344" in p for p in paths)
    assert any(x["status"] == 404 for x in d["data"])


def test_request_log_errors_only(keys, admin):
    r = requests.get(f"{API}/privacy/keys/{keys['full']['id']}/requests", headers=admin["hdr"], params={"errors_only": "true"}, timeout=10)
    assert r.status_code == 200
    assert r.json()["data"] and all(x["status"] >= 400 for x in r.json()["data"])


def test_request_log_missing_scope_logged(keys, admin):
    r = requests.post(f"{V1}/privacy/export", headers=H(keys, "nopriv"), json={"phone": PH1}, timeout=10)
    assert r.status_code == 403 and r.json()["code"] == "missing_scope"
    assert r.headers["content-type"].startswith("application/problem+json")
    time.sleep(1.5)
    d = requests.get(f"{API}/privacy/keys/{keys['nopriv']['id']}/requests", headers=admin["hdr"], timeout=10).json()
    assert any(x["status"] == 403 for x in d["data"])


def test_request_log_cross_tenant_empty(keys, t2):
    r = requests.get(f"{API}/privacy/keys/{keys['full']['id']}/requests", headers=t2["hdr"], timeout=10)
    assert r.status_code == 200
    assert r.json()["data"] == [] and r.json()["summary"]["total"] == 0


def test_request_log_requires_session():
    assert requests.get(f"{API}/privacy/keys/{'0'*24}/requests", timeout=10).status_code == 401


# ---- export validation ----
def test_export_subject_required(keys):
    r = requests.post(f"{V1}/privacy/export", headers=H(keys), json={}, timeout=10)
    assert r.status_code == 422 and r.json()["code"] == "subject_required"
    assert r.headers["content-type"].startswith("application/problem+json")


def test_export_invalid_phone(keys):
    r = requests.post(f"{V1}/privacy/export", headers=H(keys), json={"phone": "12"}, timeout=10)
    assert r.status_code == 422 and r.json()["code"] == "invalid_phone", r.text


def test_export_extra_field(keys):
    r = requests.post(f"{V1}/privacy/export", headers=H(keys), json={"phone": PH1, "foo": 1}, timeout=10)
    assert r.status_code == 422 and r.json()["code"] == "validation_error"


# ---- full export/erase flow ----
def test_export_erase_flow(keys, t2):
    h = H(keys)
    agent = requests.get(f"{V1}/agents", headers=h, timeout=10).json()["data"][0]["id"]
    body = {"agent_id": agent, "name": "TEST RGPD", "phone": PH1, "email": EMAIL1, "type": "recordatorio", "legal_basis": "contract"}
    r = requests.post(f"{V1}/calls", headers=h, json=body, timeout=15)
    assert r.status_code == 202, r.text
    cid = r.json()["id"]
    for _ in range(15):
        if requests.get(f"{V1}/calls/{cid}", headers=h, timeout=10).json()["status"] == "completed":
            break
        time.sleep(1)
    # national format with country
    r = requests.post(f"{V1}/privacy/export", headers=h, json={"phone": PH1[3:], "country": "ES"}, timeout=10)
    assert r.status_code == 200, r.text
    e = r.json()
    for k in ("calls", "appointments", "scheduled_calls", "support_tickets", "do_not_call"):
        assert isinstance(e[k], list)
    assert len(e["calls"]) == 1 and e["calls"][0]["id"] == cid
    assert "tenant_id" not in e["calls"][0]
    # by email
    assert len(requests.post(f"{V1}/privacy/export", headers=h, json={"email": EMAIL1.upper()}, timeout=10).json()["calls"]) == 1
    # other tenant cannot see / erase it
    r = requests.post(f"{V1}/privacy/erase", headers=H(keys, "t2"), json={"phone": PH1}, timeout=10)
    assert r.status_code == 200 and r.json()["deleted"]["calls"] == 0
    # erase
    r = requests.post(f"{V1}/privacy/erase", headers=h, json={"phone": PH1}, timeout=10)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["erased"] is True and d["deleted"]["calls"] == 1
    for k in ("appointments", "scheduled_calls", "support_tickets", "webhook_deliveries", "recordings"):
        assert k in d["deleted"]
    assert len(requests.post(f"{V1}/privacy/export", headers=h, json={"phone": PH1}, timeout=10).json()["calls"]) == 0
    assert requests.get(f"{V1}/calls/{cid}", headers=h, timeout=10).status_code == 404


def test_erase_keeps_dnc(keys):
    h = H(keys)
    r = requests.post(f"{V1}/dnc", headers=h, json={"phone": PH_DNC, "reason": "test"}, timeout=10)
    assert r.status_code in (200, 201), r.text
    r = requests.post(f"{V1}/privacy/erase", headers=h, json={"phone": PH_DNC}, timeout=10)
    assert r.status_code == 200
    e = requests.post(f"{V1}/privacy/export", headers=h, json={"phone": PH_DNC}, timeout=10).json()
    assert len(e["do_not_call"]) == 1
    requests.delete(f"{V1}/dnc/{PH_DNC}", headers=h, timeout=10)


def test_dashboard_export_erase_and_history_no_pii(admin):
    r = requests.post(f"{API}/privacy/export", headers=admin["hdr"], json={"email": EMAIL1}, timeout=10)
    assert r.status_code == 200 and r.json()["calls"] == []
    r = requests.post(f"{API}/privacy/export", headers=admin["hdr"], json={}, timeout=10)
    assert r.status_code == 422
    r = requests.post(f"{API}/privacy/erase", headers=admin["hdr"], json={"email": EMAIL1}, timeout=10)
    assert r.status_code == 200 and r.json()["erased"] is True
    s = requests.get(f"{API}/privacy/settings", headers=admin["hdr"], timeout=10).json()
    assert {"retention_days", "choices", "history", "purged_calls"} <= set(s)
    h = s["history"]
    assert h and {"action", "subject_ref", "counts", "created_at"} <= set(h[0])
    assert {x["action"] for x in h} >= {"export", "erase"}
    txt = str(h)
    assert EMAIL1 not in txt and PH1 not in txt and PH1[3:] not in txt


# ---- retention ----
def test_retention_api(keys):
    h = H(keys)
    r = requests.get(f"{V1}/account/retention", headers=h, timeout=10)
    assert r.status_code == 200 and r.json()["choices"] == [0, 30, 90, 180, 365]
    for bad in (7, 31, -1, "x"):
        r = requests.put(f"{V1}/account/retention", headers=h, json={"days": bad}, timeout=10)
        assert r.status_code == 422, (bad, r.text)
    assert requests.put(f"{V1}/account/retention", headers=h, json={"days": 90, "x": 1}, timeout=10).status_code == 422
    r = requests.put(f"{V1}/account/retention", headers=h, json={"days": 90}, timeout=10)
    assert r.status_code == 200 and r.json()["days"] == 90
    assert requests.get(f"{V1}/account/retention", headers=h, timeout=10).json()["days"] == 90
    assert requests.put(f"{V1}/account/retention", headers=H(keys, "nopriv"), json={"days": 30}, timeout=10).status_code == 403


def test_retention_dashboard(admin):
    r = requests.put(f"{API}/privacy/retention", headers=admin["hdr"], json={"days": 45}, timeout=10)
    assert r.status_code == 422
    r = requests.put(f"{API}/privacy/retention", headers=admin["hdr"], json={"days": 180}, timeout=10)
    assert r.status_code == 200 and r.json()["retention_days"] == 180
    assert requests.get(f"{API}/privacy/settings", headers=admin["hdr"], timeout=10).json()["retention_days"] == 180
    r = requests.put(f"{API}/privacy/retention", headers=admin["hdr"], json={"days": 0}, timeout=10)
    assert r.json()["retention_days"] == 0


# ---- purge ----
def test_purge_expired_unit(t2, admin):
    d = _db()
    d.users.update_one({"_id": ObjectId(t2["id"])}, {"$set": {"transcript_retention_days": 30}})
    base = {"agent_id": "x", "name": "TEST old", "phone": "+34611229999", "status": "completada", "messages": [{"role": "user", "text": "hola"}],
            "transcript": "hola", "recording_url": "https://x/rec.mp3", "summary": "keep", "created_at": "2020-01-01T00:00:00+00:00"}
    old = d.leads.insert_one({**base, "tenant_id": t2["id"]}).inserted_id
    new = d.leads.insert_one({**base, "tenant_id": t2["id"], "created_at": "2099-01-01T00:00:00+00:00"}).inserted_id
    sched = d.leads.insert_one({**base, "tenant_id": t2["id"], "status": "programada"}).inserted_id
    sys.path.insert(0, "/app/backend")
    import privacy as PV
    n = asyncio.run(PV.purge_expired())
    assert n >= 1
    o = d.leads.find_one({"_id": old})
    assert o["messages"] == [] and o["transcript"] == "" and o["recording_url"] == "" and o["transcript_purged_at"]
    assert o["summary"] == "keep" and o["status"] == "completada"
    assert d.leads.find_one({"_id": new})["transcript"] == "hola"
    assert d.leads.find_one({"_id": sched})["transcript"] == "hola"
    # lead endpoint exposes transcript_purged_at
    r = requests.get(f"{API}/leads/{old}", headers=t2["hdr"], timeout=10)
    assert r.status_code == 200, r.text
    assert r.json()["transcript_purged_at"]
    assert requests.get(f"{API}/privacy/settings", headers=t2["hdr"], timeout=10).json()["purged_calls"] == 1


def test_lead_detail_has_purged_field_admin(admin):
    leads = requests.get(f"{API}/leads", headers=admin["hdr"], timeout=10).json()
    assert leads
    r = requests.get(f"{API}/leads/{leads[0]['id']}", headers=admin["hdr"], timeout=10)
    assert r.status_code == 200 and "transcript_purged_at" in r.json()


def test_openapi_has_privacy_paths():
    p = requests.get(f"{V1}/openapi.json", timeout=10).json()["paths"]
    assert "/privacy/export" in p and "/privacy/erase" in p and "/account/retention" in p
