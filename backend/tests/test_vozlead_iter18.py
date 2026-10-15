"""Iteration 18 backend tests: sector demo audio & admin reset."""
import os
import uuid
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = "admin@vozlead.es"
ADMIN_PWD = "VozLead2026!"

SLUGS = ["clinicas-dentales", "clinicas-esteticas", "psicologos", "barberias",
         "restaurantes", "cafeterias", "abogados"]


# --- fixtures ---
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PWD}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def biz_token():
    email = f"TEST_iter18_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{BASE}/api/auth/register", json={
        "name": "T", "business_name": "T", "email": email, "password": "Passw0rd!"
    }, timeout=20)
    assert r.status_code in (200, 201), r.text
    return r.json()["access_token"]


# --- marks endpoint (quick, no audio generation if already cached, else generates) ---
def test_marks_barberias_es():
    r = requests.get(f"{BASE}/api/public/sector-demo/es/barberias/marks", timeout=120)
    assert r.status_code == 200, r.text
    d = r.json()
    assert isinstance(d["marks"], list) and len(d["marks"]) == 7
    assert all(isinstance(x, (int, float)) for x in d["marks"])
    assert isinstance(d["duration"], (int, float)) and d["duration"] > 0


def test_audio_barberias_es_mp3():
    r = requests.get(f"{BASE}/api/public/sector-demo/es/barberias.mp3", timeout=120)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("audio/mpeg")
    assert len(r.content) > 5000  # non-trivial mp3


def test_unknown_slug_404():
    r = requests.get(f"{BASE}/api/public/sector-demo/es/nope-sector.mp3", timeout=30)
    assert r.status_code == 404


def test_unknown_country_404():
    r = requests.get(f"{BASE}/api/public/sector-demo/fr/barberias.mp3", timeout=30)
    assert r.status_code == 404


def test_admin_reset_requires_admin(biz_token):
    # non-admin
    r = requests.delete(f"{BASE}/api/admin/sector-demos",
                        headers={"Authorization": f"Bearer {biz_token}"}, timeout=20)
    assert r.status_code == 403


def test_admin_reset_unauth():
    r = requests.delete(f"{BASE}/api/admin/sector-demos", timeout=20)
    assert r.status_code in (401, 403)


# Verify all 7 slugs have marks (uses whatever is cached in DB, may generate)
@pytest.mark.parametrize("country", ["es", "cl"])
@pytest.mark.parametrize("slug", SLUGS)
def test_marks_all_sectors(country, slug):
    r = requests.get(f"{BASE}/api/public/sector-demo/{country}/{slug}/marks", timeout=180)
    assert r.status_code == 200, f"{country}/{slug}: {r.status_code} {r.text[:200]}"
    d = r.json()
    assert len(d["marks"]) == 7
    assert d["duration"] > 0
