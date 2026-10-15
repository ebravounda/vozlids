import os, time, requests
B = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
t = requests.post(f"{B}/api/auth/login", json={"email": "admin@vozlead.es", "password": "VozLead2026!"}).json()["access_token"]
h = {"Authorization": f"Bearer {t}"}
k = requests.post(f"{B}/api/developer/keys", headers=h, json={"name": "iter24-ui", "env": "test", "scopes": ["agents:read", "calls:read", "calls:write", "privacy:manage"]}).json()
kh = {"X-API-Key": k["key"]}
ag = requests.get(f"{B}/api/v1/agents", headers=kh).json()["data"][0]["id"]
ids = []
for ph in ("+34611220101", "+34611220102"):
    r = requests.post(f"{B}/api/v1/calls", headers=kh, json={"agent_id": ag, "name": "TEST UI RGPD", "phone": ph, "type": "recordatorio", "legal_basis": "contract"})
    ids.append(r.json()["id"])
requests.get(f"{B}/api/v1/calls/{'0'*24}", headers=kh)
time.sleep(8)
print("KEY_ID", k["id"], "LEADS", ids)
