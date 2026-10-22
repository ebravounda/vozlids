# Iter39 UI setup: register a fresh client and ensure it has an agent; prints email|agent_id
import os
import sys
import uuid

import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
email = f"test_iter39ui_{uuid.uuid4().hex[:6]}@example.com"
s = requests.Session()
r = s.post(f"{BASE}/api/auth/register", json={"email": email, "password": "TestPass123!", "business_name": "TEST_Iter39 UI",
                                              "name": "Test UI", "country": "ES", "accept_terms": True})
r.raise_for_status()
s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
ag = s.get(f"{BASE}/api/agents").json()
if not ag:
    a = requests.post(f"{BASE}/api/auth/login", json={"email": "admin@vozlead.es", "password": "VozLead2026!"}).json()["access_token"]
    tpl = requests.get(f"{BASE}/api/agents", headers={"Authorization": f"Bearer {a}"}).json()[0]
    tpl = {k: v for k, v in tpl.items() if k not in ("id", "tenant_id", "created_at", "updated_at", "vapi_assistant_id")}
    tpl.update({"name": "TEST agente", "business_name": "TEST_Iter39 UI", "product": "Somos un negocio de prueba.", "executives": [], "languages": [], "ambience": "none"})
    c = s.post(f"{BASE}/api/agents", json=tpl)
    print("create agent:", c.status_code, c.text[:300], file=sys.stderr)
    ag = [c.json()] if c.ok else []
if False:
    c = s.post(f"{BASE}/api/agents", json={"name": "TEST agente", "business_name": "TEST_Iter39 UI", "objective": "recepcion", "greeting": "Hola, gracias por llamar.", "product": "Somos un negocio de prueba."})
    print("create agent:", c.status_code, c.text[:200], file=sys.stderr)
    ag = [c.json()] if c.ok else []
print(email, ag[0]["id"] if ag else "", sep="|")
