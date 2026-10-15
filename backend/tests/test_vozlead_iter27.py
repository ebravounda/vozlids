"""Iter-27: Reminders settings + run_due + public confirm/cancel, Google Calendar admin/status/connect, appointment regression."""
import asyncio
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs

import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv  # noqa: E402
load_dotenv("/app/backend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = {"email": "admin@vozlead.es", "password": "VozLead2026!"}
LOOP = asyncio.new_event_loop()
DEFAULTS = {"call": False, "email": False, "hours_before": 24, "call_from": "09:00", "call_to": "21:00"}


def _db():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture(scope="module")
def admin():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    yield {"hdr": {"Authorization": f"Bearer {j['access_token']}"}, "id": j.get("id") or j.get("user", {}).get("id")}
    requests.put(f"{API}/reminders", headers={"Authorization": f"Bearer {j['access_token']}"}, json=DEFAULTS, timeout=10)
    requests.delete(f"{API}/admin/google", headers={"Authorization": f"Bearer {j['access_token']}"}, timeout=10)
    _db().appointments.delete_many({"lead_name": {"$regex": "^TEST_iter27"}})


@pytest.fixture(scope="module")
def user2():
    s = str(int(time.time() * 1000))[-8:]
    r = requests.post(f"{API}/auth/register", timeout=15, json={"name": "T2", "business_name": f"TEST biz {s}",
                      "email": f"TEST_iter27_{s}@vozlead-test.es", "password": "Password123!", "country": "ES"})
    assert r.status_code == 200, r.text
    yield {"hdr": {"Authorization": f"Bearer {r.json()['access_token']}"}, "id": r.json()["id"]}
    _db().users.delete_many({"email": {"$regex": "^TEST_iter27_", "$options": "i"}})


# ---- Reminder settings ----
def test_reminders_defaults_and_validation(admin):
    requests.put(f"{API}/reminders", headers=admin["hdr"], json=DEFAULTS, timeout=10)
    r = requests.get(f"{API}/reminders", headers=admin["hdr"], timeout=10)
    assert r.status_code == 200
    j = r.json()
    for k, v in DEFAULTS.items():
        assert j[k] == v
    assert "sent_total" in j
    for bad in [{**DEFAULTS, "hours_before": 2}, {**DEFAULTS, "call_from": "21:00", "call_to": "09:00"},
                {**DEFAULTS, "call_from": "10:00", "call_to": "10:00"}, {**DEFAULTS, "call_from": "25:00"}]:
        assert requests.put(f"{API}/reminders", headers=admin["hdr"], json=bad, timeout=10).status_code == 422, bad
    ok = {**DEFAULTS, "email": True, "hours_before": 3, "call_from": "10:00", "call_to": "20:00"}
    r = requests.put(f"{API}/reminders", headers=admin["hdr"], json=ok, timeout=10)
    assert r.status_code == 200 and r.json()["hours_before"] == 3
    g = requests.get(f"{API}/reminders", headers=admin["hdr"], timeout=10).json()
    assert g["email"] is True and g["call_from"] == "10:00"
    requests.put(f"{API}/reminders", headers=admin["hdr"], json=DEFAULTS, timeout=10)


def test_reminders_requires_auth():
    assert requests.get(f"{API}/reminders", timeout=10).status_code == 401


# ---- run_due ----
def _madrid_now():
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("Europe/Madrid"))


def _run_due():
    import reminders
    import db as dbmod  # noqa: F401
    return LOOP.run_until_complete(reminders.run_due())


def test_run_due_email_and_call_without_phone(admin):
    d = _db()
    requests.put(f"{API}/reminders", headers=admin["hdr"], json={**DEFAULTS, "email": True, "call": True,
                                                                 "call_from": "00:00", "call_to": "23:59"}, timeout=10)
    now = _madrid_now()
    old = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    base = {"tenant_id": admin["id"], "lead_phone": "", "lead_email": "test@example.com", "notes": "", "source": "manual",
            "reminder_sent_at": None, "reminder_channels": [], "confirmed_at": None, "google_event_id": None,
            "created_at": old, "duration_minutes": None, "agent_id": None, "lead_id": None}
    near = (now + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")
    far = (now + timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M")
    sample = (now + timedelta(hours=3, minutes=7)).strftime("%Y-%m-%dT%H:%M")
    ids = {
        "near": d.appointments.insert_one({**base, "lead_name": "TEST_iter27 Near", "start": near, "is_sample": False}).inserted_id,
        "far": d.appointments.insert_one({**base, "lead_name": "TEST_iter27 Far", "start": far, "is_sample": False}).inserted_id,
        "sample": d.appointments.insert_one({**base, "lead_name": "TEST_iter27 Sample", "start": sample, "is_sample": True}).inserted_id,
    }
    try:
        _run_due()
        n = d.appointments.find_one({"_id": ids["near"]})
        assert n["reminder_sent_at"], n
        assert isinstance(n.get("reminder_token"), str) and len(n["reminder_token"]) > 10
        print("channels:", n["reminder_channels"])
        assert "llamada no realizada (sin teléfono)" in n["reminder_channels"]
        sent_at, tok = n["reminder_sent_at"], n["reminder_token"]
        _run_due()
        n2 = d.appointments.find_one({"_id": ids["near"]})
        assert n2["reminder_sent_at"] == sent_at and n2["reminder_token"] == tok, "resent!"
        assert d.appointments.find_one({"_id": ids["far"]})["reminder_sent_at"] is None
        assert d.appointments.find_one({"_id": ids["sample"]})["reminder_sent_at"] is None
        # API out fields
        lst = requests.get(f"{API}/appointments", headers=admin["hdr"], timeout=10).json()
        a = next(x for x in lst if x["id"] == str(ids["near"]))
        for k in ("reminder_sent_at", "reminder_channels", "confirmed_at", "google_event_id"):
            assert k in a
        assert "reminder_token" not in a, "token leaked in API"
        pytest.near_token = tok
        pytest.near_id = str(ids["near"])
    finally:
        requests.put(f"{API}/reminders", headers=admin["hdr"], json=DEFAULTS, timeout=10)


# ---- Public endpoints ----
def test_public_view_confirm_cancel(admin):
    tok = getattr(pytest, "near_token", None)
    if not tok:
        pytest.skip("no token")
    r = requests.get(f"{API}/public/appointment/{tok}", timeout=10)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["name"] == "TEST_iter27" and j["when"] and "business" in j and j["confirmed"] is False
    r = requests.post(f"{API}/public/appointment/{tok}/confirm", timeout=10)
    assert r.status_code == 200
    assert _db().appointments.find_one({"reminder_token": tok})["confirmed_at"]
    assert requests.get(f"{API}/public/appointment/{tok}", timeout=10).json()["confirmed"] is True
    r = requests.post(f"{API}/public/appointment/{tok}/cancel", timeout=10)
    assert r.status_code == 200
    assert _db().appointments.find_one({"reminder_token": tok}) is None
    assert requests.get(f"{API}/public/appointment/{tok}", timeout=10).status_code == 404


def test_public_bad_token():
    assert requests.get(f"{API}/public/appointment/badtokenxxxxxxxx", timeout=10).status_code == 404
    assert requests.post(f"{API}/public/appointment/short/confirm", timeout=10).status_code == 404
    assert requests.post(f"{API}/public/appointment/badtokenxxxxxxxx/cancel", timeout=10).status_code == 404


# ---- Appointment create/patch regression ----
def test_create_with_email_patch_resets_reminder(admin):
    r = requests.post(f"{API}/appointments", headers=admin["hdr"], timeout=10,
                      json={"start": "2031-04-07T10:00", "lead_name": "TEST_iter27 Email", "lead_email": " Foo@Example.COM "})
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["lead_email"] == "foo@example.com"
    for k in ("reminder_sent_at", "reminder_channels", "confirmed_at", "google_event_id"):
        assert k in a
    from bson import ObjectId
    _db().appointments.update_one({"_id": ObjectId(a["id"])}, {"$set": {"reminder_sent_at": "2031-01-01", "confirmed_at": "2031-01-01"}})
    r = requests.patch(f"{API}/appointments/{a['id']}", headers=admin["hdr"], json={"start": "2031-04-07T11:00"}, timeout=10)
    assert r.status_code == 200
    print("patch response reminder_sent_at:", r.json()["reminder_sent_at"])
    doc = _db().appointments.find_one({"_id": ObjectId(a["id"])})
    assert doc["reminder_sent_at"] is None and doc["confirmed_at"] is None
    # notes-only patch keeps reminder
    _db().appointments.update_one({"_id": ObjectId(a["id"])}, {"$set": {"reminder_sent_at": "2031-01-01"}})
    requests.patch(f"{API}/appointments/{a['id']}", headers=admin["hdr"], json={"notes": "x"}, timeout=10)
    assert _db().appointments.find_one({"_id": ObjectId(a["id"])})["reminder_sent_at"] == "2031-01-01"
    assert requests.delete(f"{API}/appointments/{a['id']}", headers=admin["hdr"], timeout=10).status_code == 200
    assert requests.delete(f"{API}/appointments/{a['id']}", headers=admin["hdr"], timeout=10).status_code == 404


# ---- Google ----
def test_google_unavailable(admin):
    requests.delete(f"{API}/admin/google", headers=admin["hdr"], timeout=10)
    s = requests.get(f"{API}/google/status", headers=admin["hdr"], timeout=10).json()
    assert s["available"] is False and s["connected"] is False
    assert requests.post(f"{API}/google/connect", headers=admin["hdr"], timeout=10).status_code == 409
    b = requests.get(f"{API}/google/busy", headers=admin["hdr"], params={"start": "2031-04-07", "end": "2031-04-08"}, timeout=10)
    assert b.status_code == 200 and b.json() == []


def test_admin_google_crud(admin):
    g = requests.get(f"{API}/admin/google", headers=admin["hdr"], timeout=10)
    assert g.status_code == 200
    assert g.json()["redirect_uri"].endswith("/api/oauth/calendar/callback") and g.json()["configured"] is False
    h = admin["hdr"]
    assert requests.put(f"{API}/admin/google", headers=h, json={"client_id": "1234567890-abc.example.com", "client_secret": "secret12345"}, timeout=10).status_code == 422
    assert requests.put(f"{API}/admin/google", headers=h, json={"client_id": "1234567890-abc.apps.googleusercontent.com", "client_secret": "short"}, timeout=10).status_code == 422
    r = requests.put(f"{API}/admin/google", headers=h, json={"client_id": "1234567890-abc.apps.googleusercontent.com", "client_secret": "GOCSPX-fakefakefake"}, timeout=10)
    assert r.status_code == 200 and r.json()["configured"] is True
    assert "client_secret" not in r.json()
    assert requests.get(f"{API}/google/status", headers=h, timeout=10).json()["available"] is True
    c = requests.post(f"{API}/google/connect", headers=h, timeout=10)
    assert c.status_code == 200
    url = c.json()["url"]
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth")
    q = parse_qs(urlparse(url).query)
    assert q["state"][0] and q["redirect_uri"][0].endswith("/api/oauth/calendar/callback")
    assert q["client_id"][0] == "1234567890-abc.apps.googleusercontent.com"
    # keep secret when blank
    r = requests.put(f"{API}/admin/google", headers=h, json={"client_id": "999999999-x.apps.googleusercontent.com", "client_secret": ""}, timeout=10)
    assert r.status_code == 200 and r.json()["configured"] is True
    assert requests.delete(f"{API}/admin/google", headers=h, timeout=10).status_code == 200
    assert requests.get(f"{API}/google/status", headers=h, timeout=10).json()["available"] is False


def test_oauth_callback_bad_state():
    r = requests.get(f"{API}/oauth/calendar/callback", params={"state": "bad", "code": "x"}, allow_redirects=False, timeout=10)
    assert r.status_code in (302, 307)
    assert r.headers["location"].endswith("/app/agenda?google=error")


def test_non_admin_forbidden(user2):
    for m in ("get", "delete"):
        assert getattr(requests, m)(f"{API}/admin/google", headers=user2["hdr"], timeout=10).status_code == 403
    assert requests.put(f"{API}/admin/google", headers=user2["hdr"], json={"client_id": "1234567890-abc.apps.googleusercontent.com", "client_secret": "secret12345"}, timeout=10).status_code == 403
    s = requests.get(f"{API}/reminders", headers=user2["hdr"], timeout=10).json()
    assert s["email"] is False and s["call"] is False


# ---- free_slots regression ----
def test_free_slots_no_google(admin):
    import services as S
    from datetime import date
    d = date.today() + timedelta(days=14)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    slots = LOOP.run_until_complete(S.free_slots(admin["id"], d, "ES"))
    print("slots", d, slots[:5])
    assert isinstance(slots, list)
