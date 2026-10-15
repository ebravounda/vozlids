"""Iteration 19 backend tests: new sector pages, info-request repeat flag, legal pages."""
import os
import pytest
import requests
from datetime import datetime, timezone
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

NEW_SLUGS = ["inmobiliarias", "talleres-mecanicos", "gimnasios", "academias"]
SEED_PHONE = "+34611222333"


@pytest.fixture(scope="module")
def mongo():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


# --- new sector slugs: marks ---
@pytest.mark.parametrize("country", ["es", "cl"])
@pytest.mark.parametrize("slug", NEW_SLUGS)
def test_new_sector_marks(country, slug):
    r = requests.get(f"{BASE}/api/public/sector-demo/{country}/{slug}/marks", timeout=240)
    assert r.status_code == 200, f"{country}/{slug}: {r.status_code} {r.text[:200]}"
    d = r.json()
    assert isinstance(d["marks"], list) and len(d["marks"]) == 7
    assert d["duration"] > 0


# --- new sector slugs: mp3 ---
@pytest.mark.parametrize("country", ["es", "cl"])
@pytest.mark.parametrize("slug", NEW_SLUGS)
def test_new_sector_mp3(country, slug):
    r = requests.get(f"{BASE}/api/public/sector-demo/{country}/{slug}.mp3", timeout=240)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("audio/mpeg")
    assert len(r.content) > 5000


# --- info-request repeat flag ---
def test_info_request_repeated_returns_flag(mongo):
    # Seed existing request so repeat detection triggers
    mongo.info_requests.delete_many({"phone": SEED_PHONE})
    mongo.info_requests.insert_one({
        "name": "Prev", "phone": SEED_PHONE, "country": "ES",
        "page": "/", "ip": "", "created_at": datetime.now(timezone.utc).isoformat(),
        "call_status": "fallida", "intl": False,
    })
    r = requests.post(f"{BASE}/api/public/info-request", json={
        "name": "Test Repeat", "phone": "611222333", "country": "ES",
        "consent": True, "page": "/",
    }, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["repeated"] is True
    assert d["calling"] is False
    # Second call stored with status 'repetida' (no real call placed)
    docs = list(mongo.info_requests.find({"phone": SEED_PHONE}).sort("created_at", -1))
    assert any(x.get("call_status") == "repetida" for x in docs)
    # cleanup
    mongo.info_requests.delete_many({"phone": SEED_PHONE})


# --- validation unchanged ---
def test_info_request_requires_consent():
    r = requests.post(f"{BASE}/api/public/info-request", json={
        "name": "No Consent", "phone": "611222334", "country": "ES",
        "consent": False, "page": "/",
    }, timeout=20)
    assert r.status_code == 400


def test_info_request_unknown_country():
    r = requests.post(f"{BASE}/api/public/info-request", json={
        "name": "X", "phone": "500000000", "country": "FR",
        "consent": True, "page": "/",
    }, timeout=20)
    assert r.status_code == 422
