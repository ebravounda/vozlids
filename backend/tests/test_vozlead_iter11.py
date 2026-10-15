"""Iteration-11 tests: outbound template greeting placeholders bug fix.

Bug: outbound templates had business_name hardcoded (Clínica Dental Sonrisa).
Fix: templates use {nombre}, {agente}, {empresa} placeholders resolved at call time
by vapi.greeting() and vapi.build_assistant() using the calling agent.
"""
import asyncio
import os
import sys
import uuid

import pytest
import requests

sys.path.insert(0, "/app/backend")

def _load_react_backend_url() -> str:
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        try:
            with open("/app/frontend/.env") as f:
                for ln in f:
                    if ln.startswith("REACT_APP_BACKEND_URL="):
                        url = ln.split("=", 1)[1].strip()
                        break
        except OSError:
            pass
    assert url, "REACT_APP_BACKEND_URL not configured"
    return url.rstrip("/")


BASE_URL = _load_react_backend_url()
ADMIN_EMAIL = "admin@vozlead.es"
ADMIN_PASSWORD = "VozLead2026!"
NEW_GREETING = "Hola {nombre}, soy {agente}, de {empresa}. Te llamo un momento y la llamada se graba. ¿Tienes un minuto?"


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return s


@pytest.fixture(scope="module")
def new_tenant_client():
    s = requests.Session()
    tag = uuid.uuid4().hex[:8]
    email = f"tb_i11_{tag}@example.com"
    r = s.post(f"{BASE_URL}/api/auth/register", json={
        "name": "Tester", "business_name": "OpenFactura.es", "email": email, "password": "Password2026!",
    })
    assert r.status_code in (200, 201), r.text
    data = r.json()
    s.headers["Authorization"] = f"Bearer {data['access_token']}"
    s._email = email
    s._tenant_id = data["id"]
    yield s
    # cleanup via admin
    try:
        admin = requests.Session()
        lr = admin.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        admin.headers["Authorization"] = f"Bearer {lr.json()['access_token']}"
        admin.delete(f"{BASE_URL}/api/admin/users/{s._tenant_id}")
    except Exception:
        pass


# ---------- Templates list & migration ----------
class TestTemplates:
    def test_admin_templates_no_clinica_and_placeholders(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/templates")
        assert r.status_code == 200
        tpls = r.json()
        assert len(tpls) >= 1
        for t in tpls:
            g = t["greeting"]
            assert "Clínica" not in g and "Clinica" not in g, f"template '{t['name']}' still mentions clinic: {g}"
            assert "{agente}" in g, f"missing {{agente}} in: {g}"
            assert "{empresa}" in g, f"missing {{empresa}} in: {g}"

    def test_new_tenant_templates_use_placeholders(self, new_tenant_client):
        r = new_tenant_client.get(f"{BASE_URL}/api/templates")
        assert r.status_code == 200
        tpls = r.json()
        assert len(tpls) == 5, f"expected 5 default templates, got {len(tpls)}"
        for t in tpls:
            g = t["greeting"]
            # no hard-coded business name
            assert "OpenFactura" not in g, f"template greeting hard-coded business name: {g}"
            assert "Clínica" not in g and "Clinica" not in g
            assert g == NEW_GREETING, f"unexpected default greeting: {g}"


# ---------- Scheduled call does not place real call ----------
class TestScheduledCall:
    def test_schedule_future_call_persists_template_greeting(self, new_tenant_client):
        # create an agent "Marta" at OpenFactura.es
        agent_payload = {
            "name": "Marta", "business_name": "OpenFactura.es",
            "product": "Software de facturación electrónica.",
            "objective": "calificar", "voice": "e_sarah",
            "questions": ["¿Facturáis actualmente?"],
            "greeting": NEW_GREETING,
            "country": "ES",
            "ambience": "oficina",
            "ambience_volume": 35,
        }
        r = new_tenant_client.post(f"{BASE_URL}/api/agents", json=agent_payload)
        assert r.status_code in (200, 201), r.text
        agent_id = r.json()["id"]
        # get a template
        tpls = new_tenant_client.get(f"{BASE_URL}/api/templates").json()
        tpl_id = tpls[0]["id"]
        # schedule for far future
        r = new_tenant_client.post(f"{BASE_URL}/api/scheduled-calls", json={
            "agent_id": agent_id, "template_id": tpl_id,
            "contacts": [{"name": "Juan Pérez", "phone": "+34600111222", "email": ""}],
            "run_at": "2099-12-31T10:00",
        })
        assert r.status_code == 200, r.text
        # list and verify stored
        lst = new_tenant_client.get(f"{BASE_URL}/api/scheduled-calls").json()
        assert lst and lst[0]["status"] == "pendiente"
        sid = lst[0]["id"]
        # cancel so it never runs
        c = new_tenant_client.delete(f"{BASE_URL}/api/scheduled-calls/{sid}")
        assert c.status_code == 200
        # cleanup agent
        new_tenant_client.delete(f"{BASE_URL}/api/agents/{agent_id}")


# ---------- vapi.greeting / build_assistant unit tests ----------
class TestVapiGreeting:
    def _agent(self):
        return {
            "name": "Marta", "business_name": "OpenFactura.es",
            "greeting": NEW_GREETING,
            "objective": "calificar", "voice": "e_sarah", "country": "ES",
            "product": "Software de facturación.", "questions": ["¿Facturáis?"],
            "ambience": "oficina", "ambience_volume": 35,
        }

    def test_outbound_greeting_resolves_placeholders(self):
        import vapi
        lead = {"_id": "x", "tenant_id": "t", "name": "Juan Pérez", "greeting": NEW_GREETING, "direction": "saliente"}
        g = vapi.greeting(self._agent(), lead)
        assert "soy Marta" in g
        assert "de OpenFactura.es" in g and "asistente virtual" not in g
        assert "Clínica" not in g and "{" not in g

    def test_build_assistant_firstMessage_and_system_prompt(self):
        import vapi
        lead = {"_id": "abc123", "tenant_id": "t1", "name": "Juan Pérez",
                "greeting": NEW_GREETING, "direction": "saliente", "purpose": "Hablar de facturación"}
        # ensure needed env for server_cfg exists
        os.environ.setdefault("VAPI_WEBHOOK_SECRET", "test-secret")
        os.environ.setdefault("PUBLIC_BACKEND_URL", "https://example.com")
        os.environ.setdefault("VAPI_API_KEY", "test-key")
        a = vapi.build_assistant(self._agent(), lead, "Hoy es jueves")
        fm = a["firstMessage"]
        assert "soy Marta, de OpenFactura.es" in fm
        assert "Clínica" not in fm
        # system prompt
        sp = a["model"]["messages"][0]["content"]
        assert "OpenFactura.es" in sp
        assert "Clínica" not in sp
        assert "Marta" in sp

    def test_inbound_greeting_unchanged(self):
        import vapi
        lead = {"_id": "x", "tenant_id": "t", "name": "", "direction": "entrante"}
        g = vapi.greeting(self._agent(), lead)
        assert g.startswith("Hola, OpenFactura.es, te atiende Marta")


# ---------- Startup migration regression ----------
class TestMigrateTemplates:
    def test_migrate_rewrites_old_clinic_greeting(self):
        """Insert a template with the old clinic-style greeting, run migrate_templates,
        verify it's rewritten to use placeholders."""
        # ensure backend env is loaded for db/MONGO_URL
        from pathlib import Path
        for ln in Path("/app/backend/.env").read_text().splitlines():
            if "=" in ln and not ln.strip().startswith("#"):
                k, v = ln.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        from db import db
        import seed as seed_mod

        async def run():
            tid = f"TEST_mig_{uuid.uuid4().hex[:6]}"
            old = ("Hola {nombre}, soy {agente}, te llamo de Clínica Dental Sonrisa. "
                   "Soy una asistente virtual y la llamada se graba.")
            res = await db.call_templates.insert_one({
                "tenant_id": tid, "name": "TEST_old", "call_type": "info",
                "purpose": "x", "greeting": old, "created_at": "2026-01-01T00:00:00+00:00",
            })
            try:
                await seed_mod.migrate_templates()
                doc = await db.call_templates.find_one({"_id": res.inserted_id})
                assert "Clínica" not in doc["greeting"]
                assert "{empresa}" in doc["greeting"]
                assert "{agente}" in doc["greeting"]
            finally:
                await db.call_templates.delete_one({"_id": res.inserted_id})

        asyncio.get_event_loop().run_until_complete(run()) if not asyncio.get_event_loop().is_running() else asyncio.run(run())
