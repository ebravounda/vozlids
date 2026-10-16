# Iteration 30 probe: every new Cartesia voice ID renders a preview; print sync + profit snapshot
import os
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
B = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
s = requests.Session()
s.headers["Authorization"] = "Bearer " + s.post(f"{B}/api/auth/login", json={"email": "admin@vozlead.es", "password": "VozLead2026!"}).json()["access_token"]
for v in ["p_blanca", "p_eva", "p_lara", "p_alicia", "p_maite", "p_lucia", "p_octavio", "p_rafael", "p_dario",
          "l_catalina", "l_veronica", "l_rodrigo", "l_santiago"]:
    r = s.get(f"{B}/api/voice-preview", params={"voice": v, "text": "Hola, ¿qué tal? Le llamo de la clínica.", "ambience_id": "none"}, timeout=90)
    print(v, r.status_code, r.headers.get("x-voice-source"), len(r.content), r.text[:120] if r.status_code != 200 else "")
print("sync", s.post(f"{B}/api/admin/costs/sync", timeout=120).json())
d = s.get(f"{B}/api/admin/costs?days=30", timeout=90).json()
print("profit", d["profit"])
print("fixed", d["fixed"])
print("zsync", d["zadarma_sync"], "eleven", d["eleven_usage"])
print("totals", d["totals"])
for t in d["tenants"][:8]:
    print({k: t[k] for k in ("business", "plan", "revenue", "total", "number_fee", "stripe_fee", "profit", "margin_pct")})
print("pricing", d["pricing"])
