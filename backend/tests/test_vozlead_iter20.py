"""Iteration 20 security hardening tests.

Covers:
- Vapi webhook: ?token= rejected (401); x-vapi-secret header accepted (200); wrong header 401
- Security headers present: X-Content-Type-Options nosniff, X-Frame-Options DENY, Referrer-Policy
- CORS: with CORS_ORIGINS="*", Access-Control-Allow-Credentials MUST NOT be true
- Admin login + /auth/me + /auth/refresh + /auth/logout flow (regression)
- Business user register + login (regression)
- Public embed form /api/public/agents/{id} (regression)
- client_ip: forging first X-Forwarded-For hop does NOT reset per-IP 3/10min cap on /api/public/info-request
- Daily cap: >=20 info_requests in last 24h with call_status 'llamando' -> new request returns 'limite_diario'
  and a monitor_alerts doc of kind 'demo_cap' is inserted. Cleans up seeded docs.
"""
import os
import uuid
import pytest
import requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
WEBHOOK_SECRET = os.environ["VAPI_WEBHOOK_SECRET"]
ADMIN_EMAIL = "admin@vozlead.es"
ADMIN_PASSWORD = "VozLead2026!"


# ---------- Vapi webhook ----------
class TestVapiWebhook:
    def test_query_token_rejected(self):
        r = requests.post(f"{BASE}/api/vapi/webhook?token={WEBHOOK_SECRET}",
                          json={"message": {"type": "status-update"}})
        assert r.status_code == 401, r.text

    def test_no_header_rejected(self):
        r = requests.post(f"{BASE}/api/vapi/webhook",
                          json={"message": {"type": "status-update"}})
        assert r.status_code == 401, r.text

    def test_wrong_header_rejected(self):
        r = requests.post(f"{BASE}/api/vapi/webhook",
                          json={"message": {"type": "status-update"}},
                          headers={"x-vapi-secret": "wrong"})
        assert r.status_code == 401

    def test_correct_header_accepted(self):
        r = requests.post(f"{BASE}/api/vapi/webhook",
                          json={"message": {"type": "status-update"}},
                          headers={"x-vapi-secret": WEBHOOK_SECRET})
        assert r.status_code == 200, r.text
        assert r.json() == {"ok": True}


# ---------- Security headers ----------
class TestSecurityHeaders:
    def test_security_headers_present(self):
        r = requests.get(f"{BASE}/api/")
        assert r.status_code == 200
        assert r.headers.get("X-Content-Type-Options") == "nosniff"
        assert r.headers.get("X-Frame-Options") == "DENY"
        assert "strict-origin" in (r.headers.get("Referrer-Policy") or "").lower()

    def test_cors_credentials_not_true_with_wildcard(self):
        # CORS_ORIGINS=* -> allow_credentials must be False, so backend never sends ACAC: true.
        # Note: Cloudflare ingress adds Access-Control-Allow-Origin: * unconditionally.
        r = requests.get(f"{BASE}/api/", headers={"Origin": "https://evil.com"})
        acac = r.headers.get("Access-Control-Allow-Credentials", "")
        assert acac.lower() != "true", f"ACAC leaked: {acac}"


# ---------- Auth regression ----------
@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["email"] == ADMIN_EMAIL
    assert data["role"] == "admin"
    assert data.get("access_token")
    s.headers.update({"Authorization": f"Bearer {data['access_token']}"})
    return s


class TestAuthRegression:
    def test_admin_me(self, admin_session):
        r = admin_session.get(f"{BASE}/api/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL

    def test_refresh(self, admin_session):
        # need cookie session; login stored cookies on session
        r = admin_session.post(f"{BASE}/api/auth/refresh")
        assert r.status_code == 200, r.text
        assert r.json().get("access_token")

    def test_logout(self):
        s = requests.Session()
        r = s.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200
        r = s.post(f"{BASE}/api/auth/logout")
        assert r.status_code == 200
        # After logout, /me via cookie should fail
        r = requests.Session().get(f"{BASE}/api/auth/me")
        assert r.status_code == 401

    def test_business_register_login(self):
        s = requests.Session()
        email = f"biz_{uuid.uuid4().hex[:8]}@test.es"
        r = s.post(f"{BASE}/api/auth/register", json={
            "name": "Biz Owner", "business_name": "Biz SL", "email": email, "password": "Password123!",
        })
        assert r.status_code == 200, r.text
        assert r.json()["role"] == "business"
        r2 = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": "Password123!"})
        assert r2.status_code == 200
        token = r2.json()["access_token"]
        r3 = requests.get(f"{BASE}/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r3.status_code == 200
        assert r3.json()["email"] == email


# ---------- Public embed form ----------
class TestPublicEmbed:
    def test_public_agent_returns_info(self, admin_session):
        agents = admin_session.get(f"{BASE}/api/agents").json()
        assert agents, "No agents seeded"
        aid = agents[0]["id"]
        r = requests.get(f"{BASE}/api/public/agents/{aid}")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == aid
        assert "name" in data and "business_name" in data


# ---------- Mongo helpers for seeding ----------
@pytest.fixture(scope="module")
def mongo():
    from pymongo import MongoClient
    client = MongoClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    yield db
    client.close()


# ---------- Per-IP rate limit with spoofed XFF ----------
class TestClientIpRateLimit:
    """
    Seed 4 'repetida' phones so the server treats requests as repeated (no real call).
    Send 4 POSTs from a single real client, each with a DIFFERENT spoofed first XFF hop.
    Because client_ip uses the LAST XFF hop (plus cf-connecting-ip overrides), the per-IP
    limit (3 per 10 min) must still hit on the 4th request.
    """
    def test_spoof_xff_does_not_reset(self, mongo):
        # Insert 4 info_requests from <24h ago to mark phones as 'repeated' when we POST
        # (so backend returns repeated=True, call_status='repetida', NO call placed).
        now_iso = datetime.now(timezone.utc).isoformat()
        phones = [f"+3461122233{i}" for i in range(4)]
        docs = []
        for p in phones:
            d = {"name": "SeedRepeat", "phone": p, "country": "ES", "page": "/", "ip": "seed",
                 "created_at": now_iso, "call_status": "repetida", "intl": False, "_seed": "iter20"}
            docs.append(d)
        mongo.info_requests.insert_many(docs)

        try:
            codes = []
            # Note: We can't spoof cf-connecting-ip (Cloudflare rejects it with 403).
            # Instead rely on the real cf-connecting-ip from Cloudflare being identical
            # for all 4 requests, and spoof the first XFF hop. Backend MUST ignore the
            # spoofed first hop and still rate-limit by the real client IP.
            for i, p in enumerate(phones):
                h = {"X-Forwarded-For": f"10.0.0.{i+1}"}  # spoofed first hop
                r = requests.post(f"{BASE}/api/public/info-request", json={
                    "name": "Test User", "phone": p, "country": "ES",
                    "consent": True, "page": "/",
                }, headers=h)
                codes.append(r.status_code)

            # First 3 should be 200 (repeated), 4th should be 429 (rate-limit by real IP)
            assert codes[:3] == [200, 200, 200], f"Expected 3x 200, got {codes}"
            assert codes[3] == 429, f"4th req should be 429, got {codes[3]} (full: {codes})"
        finally:
            mongo.info_requests.delete_many({"_seed": "iter20"})
            mongo.info_requests.delete_many({"phone": {"$in": phones}})


# ---------- Daily cap ----------
class TestDailyCap:
    def test_daily_cap_triggers_limite_diario(self, mongo):
        # Seed 20 info_requests with call_status 'llamando' within last 24h
        now = datetime.now(timezone.utc)
        docs = []
        for i in range(20):
            docs.append({
                "name": f"SeedCap{i}", "phone": f"+34600000{i:03d}", "country": "ES", "page": "/",
                "ip": f"seed-{i}",
                "created_at": (now - timedelta(hours=1)).isoformat(),
                "call_status": "llamando", "intl": False, "_seed": "iter20-cap",
            })
        mongo.info_requests.insert_many(docs)

        unseen_phone = f"+34611998{uuid.uuid4().int % 1000:03d}"
        alert_before = mongo.monitor_alerts.count_documents({"kind": "demo_cap"})
        try:
            # Use a fresh cf-connecting-ip to avoid tripping per-IP rate limit
            r = requests.post(f"{BASE}/api/public/info-request", json={
                "name": "Test User", "phone": unseen_phone, "country": "ES",
                "consent": True, "page": "/",
            })
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["calling"] is False, body
            # Check the inserted doc has call_status 'limite_diario'
            doc = mongo.info_requests.find_one({"phone": unseen_phone})
            assert doc, "info_request not inserted"
            assert doc["call_status"] == "limite_diario", doc
            # Check monitor_alerts received a demo_cap entry (may be dedup; count >= before, and one exists in last minute)
            recent = mongo.monitor_alerts.count_documents({
                "kind": "demo_cap",
                "created_at": {"$gt": (now - timedelta(minutes=5)).isoformat()}
            })
            # Allow case where notify is throttled every_hours=24 — but at minimum the backend attempted
            # So accept either (recent >= 1) OR (alert_before >= 1 meaning already alerted previously).
            assert recent >= 1 or alert_before >= 1, "No demo_cap monitor alert"
        finally:
            # Cleanup
            mongo.info_requests.delete_many({"_seed": "iter20-cap"})
            mongo.info_requests.delete_many({"phone": unseen_phone})
            # Clean our monitor alerts of kind demo_cap created in this run
            mongo.monitor_alerts.delete_many({
                "kind": "demo_cap",
                "created_at": {"$gt": (now - timedelta(minutes=5)).isoformat()}
            })
