# Setup/teardown helper for iter28 UI tests: python iter28_ui_setup.py setup|teardown
import os, sys, json, requests
from datetime import datetime, timezone
from pymongo import MongoClient
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
EMAIL, PW = "test_iter28_ui@example.com", "TestPass123!"
RESTRICTED = {"max_agents": 1, "max_concurrent": 1, "recording_days": 90, "outbound": False, "api": False, "widget": False,
              "agenda_pro": False, "premium_voices": False, "ambience": False}
db = MongoClient("mongodb://localhost:27017")["test_database"]
a = requests.Session()
a.headers["Authorization"] = "Bearer " + a.post(f"{BASE}/api/auth/login", json={"email": "admin@vozlead.es", "password": "VozLead2026!"}).json()["access_token"]
if sys.argv[1] == "setup":
    requests.post(f"{BASE}/api/auth/register", json={"name": "TEST UI", "business_name": "TEST UI Biz", "email": EMAIL, "password": PW})
    uid = str(db.users.find_one({"email": EMAIL})["_id"])
    plan = a.post(f"{BASE}/api/admin/plans", json={"name": "TEST_UI_Plan", "minutes": 100, "price_eur": 50, "price_clp": 50000, "public": False, "limits": RESTRICTED}).json()
    print(a.put(f"{BASE}/api/admin/users/{uid}", json={"plan_id": plan["id"]}).status_code)
    db.leads.insert_one({"tenant_id": uid, "name": "TEST lead", "phone": "+34600000001", "created_at": datetime.now(timezone.utc).isoformat(), "duration_seconds": int(sys.argv[2]) if len(sys.argv) > 2 else 85 * 60, "status": "completada", "agent_id": "000000000000000000000000", "test_iter28": True})
    print(json.dumps({"uid": uid, "plan": plan["id"]}))
else:
    u = db.users.find_one({"email": EMAIL})
    if u:
        a.delete(f"{BASE}/api/admin/users/{u['_id']}")
    for p in db.plans.find({"name": {"$regex": "^TEST_"}}):
        db.plans.delete_one({"_id": p["_id"]})
    db.leads.delete_many({"test_iter28": True})
    print("cleaned")
