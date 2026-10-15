"""Iter-25: Appointments calendar API (list range/create/patch/delete) + RGPD erase keeps consumed minutes."""
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = {"email": "admin@vozlead.es", "password": "VozLead2026!"}
SUF = str(int(time.time()))[-4:]
# far-future dates to avoid colliding with real data
D1 = "2031-03-10"
D2 = "2031-03-11"


def _db():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture(scope="module")
def admin():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    yield {"hdr": {"Authorization": f"Bearer {j['access_token']}"}, "id": j.get("id") or j.get("user", {}).get("id")}
    _db().appointments.delete_many({"lead_name": {"$regex": "^TEST_iter25"}})


@pytest.fixture(scope="module")
def t2():
    s = uuid.uuid4().hex[:8]
    r = requests.post(f"{API}/auth/register", timeout=15, json={"name": "T2", "business_name": f"TEST biz {s}",
                      "email": f"TEST_iter25_{s}@vozlead-test.es", "password": "Password123!", "country": "ES"})
    assert r.status_code == 200, r.text
    yield {"hdr": {"Authorization": f"Bearer {r.json()['access_token']}"}, "id": r.json()["id"]}
    d = _db()
    d.appointments.delete_many({"tenant_id": r.json()["id"]})
    d.users.delete_many({"email": {"$regex": "^TEST_iter25_", "$options": "i"}})


def _create(admin, start, name="TEST_iter25 A", **kw):
    return requests.post(f"{API}/appointments", headers=admin["hdr"], timeout=10,
                         json={"start": start, "lead_name": name, **kw})


# ---- create ----
def test_create_manual_and_list_range(admin):
    r = _create(admin, f"{D1}T10:00", lead_phone="612345678", notes="hola", duration_minutes=45)
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["source"] == "manual" and a["start"] == f"{D1}T10:00" and a["duration_minutes"] == 45
    assert a["lead_phone"].startswith("+34") and a["notes"] == "hola" and "_id" not in a
    r = requests.get(f"{API}/appointments", headers=admin["hdr"], params={"start": D1, "end": D2}, timeout=10)
    assert r.status_code == 200
    ids = [x["id"] for x in r.json()]
    assert a["id"] in ids
    # end exclusive: [D2, D2+1) should not include D1 appt
    r = requests.get(f"{API}/appointments", headers=admin["hdr"], params={"start": D2, "end": "2031-03-12"}, timeout=10)
    assert a["id"] not in [x["id"] for x in r.json()]
    # range ending at D1 (exclusive) excludes it
    r = requests.get(f"{API}/appointments", headers=admin["hdr"], params={"start": "2031-03-09", "end": D1}, timeout=10)
    assert a["id"] not in [x["id"] for x in r.json()]


def test_list_default_from_today(admin):
    r = requests.get(f"{API}/appointments", headers=admin["hdr"], timeout=10)
    assert r.status_code == 200
    today = datetime.now().strftime("%Y-%m-%d")
    yday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    assert all(x["start"] >= yday for x in r.json())  # tolerate Madrid TZ offset
    assert any(x["start"].startswith("2031-03-10") for x in r.json())


@pytest.mark.parametrize("bad", ["2031-03-10 10:00", "2031-03-10T25:00", "abc", "2031-03-10T10:60", "2031-03-10"])
def test_create_bad_start_422(admin, bad):
    assert _create(admin, bad).status_code == 422


def test_create_conflict_409(admin):
    r = _create(admin, f"{D1}T10:00", name="TEST_iter25 dup")
    assert r.status_code == 409, r.text


def test_create_invalid_phone_422(admin):
    r = _create(admin, f"{D1}T12:00", lead_phone="abc")
    assert r.status_code == 422, r.text


def test_create_empty_name_422(admin):
    assert _create(admin, f"{D1}T12:30", name="").status_code == 422


def test_unauth_401():
    assert requests.get(f"{API}/appointments", timeout=10).status_code in (401, 403)


# ---- patch ----
def test_patch_move_edit_conflict_and_tenant(admin, t2):
    a = _create(admin, f"{D1}T15:00", name="TEST_iter25 move").json()
    b = _create(admin, f"{D1}T16:00", name="TEST_iter25 other").json()
    r = requests.patch(f"{API}/appointments/{a['id']}", headers=admin["hdr"], json={"start": f"{D2}T09:30", "notes": "movida", "duration_minutes": 60}, timeout=10)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["start"] == f"{D2}T09:30" and j["notes"] == "movida" and j["duration_minutes"] == 60
    lst = requests.get(f"{API}/appointments", headers=admin["hdr"], params={"start": D2, "end": "2031-03-12"}, timeout=10).json()
    assert any(x["id"] == a["id"] and x["start"] == f"{D2}T09:30" for x in lst)
    # conflict
    r = requests.patch(f"{API}/appointments/{a['id']}", headers=admin["hdr"], json={"start": f"{D1}T16:00"}, timeout=10)
    assert r.status_code == 409
    # bad start
    assert requests.patch(f"{API}/appointments/{a['id']}", headers=admin["hdr"], json={"start": "x"}, timeout=10).status_code == 422
    # empty
    assert requests.patch(f"{API}/appointments/{a['id']}", headers=admin["hdr"], json={}, timeout=10).status_code == 422
    # other tenant
    assert requests.patch(f"{API}/appointments/{a['id']}", headers=t2["hdr"], json={"notes": "x"}, timeout=10).status_code == 404
    assert requests.delete(f"{API}/appointments/{a['id']}", headers=t2["hdr"], timeout=10).status_code == 404
    # t2 can create same time (unique index is per tenant)
    r = requests.post(f"{API}/appointments", headers=t2["hdr"], json={"start": f"{D1}T16:00", "lead_name": "TEST_iter25 t2"}, timeout=10)
    assert r.status_code == 200, r.text
    # delete
    for x in (a, b):
        assert requests.delete(f"{API}/appointments/{x['id']}", headers=admin["hdr"], timeout=10).status_code == 200
    lst = requests.get(f"{API}/appointments", headers=admin["hdr"], params={"start": D1, "end": "2031-03-12"}, timeout=10).json()
    assert not any(x["id"] in (a["id"], b["id"]) for x in lst)
    assert requests.delete(f"{API}/appointments/{a['id']}", headers=admin["hdr"], timeout=10).status_code == 404


def test_patch_invalid_id(admin):
    r = requests.patch(f"{API}/appointments/notanid", headers=admin["hdr"], json={"notes": "x"}, timeout=10)
    assert r.status_code in (404, 422), r.text


# ---- RGPD erase keeps minutes ----
def test_erase_keeps_minutes(admin):
    d = _db()
    phone = f"+3469988{SUF}"
    now = datetime.now(timezone.utc).isoformat()
    before = requests.get(f"{API}/account/usage", headers=admin["hdr"], timeout=10).json()["minutes_used"]
    d.leads.insert_many([{"tenant_id": admin["id"], "name": "TEST_iter25 Erase", "phone": phone, "email": "x@e.com",
                          "duration_seconds": 120, "created_at": now, "status": "nuevo", "sandbox": True} for _ in range(2)])
    mid = requests.get(f"{API}/account/usage", headers=admin["hdr"], timeout=10).json()["minutes_used"]
    assert round(mid - before, 1) == 4.0, (before, mid)
    r = requests.post(f"{API}/privacy/erase", headers=admin["hdr"], json={"phone": phone}, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json()["deleted"]["calls"] == 2
    after = requests.get(f"{API}/account/usage", headers=admin["hdr"], timeout=10).json()["minutes_used"]
    assert after == mid, (mid, after)
    assert d.leads.count_documents({"tenant_id": admin["id"], "phone": phone}) == 0
    arch = list(d.usage_archive.find({"tenant_id": admin["id"], "created_at": now}))
    assert len(arch) == 2
    for x in arch:
        assert not ({"name", "phone", "email", "transcript", "summary"} & set(x.keys())), x.keys()
        assert x["duration_seconds"] == 120 and x["reason"] == "rgpd_erase"
    d.usage_archive.delete_many({"tenant_id": admin["id"], "created_at": now})
