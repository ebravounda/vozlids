# Iter37 UI helper: create (setup) or remove (cleanup) a KYC-required test client for Playwright checks
import sys
import requests
from datetime import datetime, timezone
from bson import ObjectId
from pymongo import MongoClient
from dotenv import dotenv_values

E = dotenv_values("/app/backend/.env")
B = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/")
db = MongoClient(E["MONGO_URL"])[E["DB_NAME"]]
EMAIL = "test_kyc_ui@example.com"
if sys.argv[1] == "setup":
    r = requests.post(f"{B}/api/auth/register", json={"name": "TEST UI", "business_name": "TEST_KYC_UI", "email": EMAIL,
                                                     "password": "TestPass123!", "country": "ES"})
    uid = r.json()["id"]
    db.users.update_one({"_id": ObjectId(uid)}, {"$set": {"billing_status": "active"}})
    db.tenant_numbers.insert_one({"tenant_id": uid, "status": "pendiente_documentos", "country": "ES",
                                  "error": "Falta", "created_at": datetime.now(timezone.utc).isoformat()})
    print(uid)
else:
    u = db.users.find_one({"email": EMAIL})
    if u:
        uid = str(u["_id"])
        for c in ("users",):
            db[c].delete_one({"_id": u["_id"]})
        for c in ("kyc", "tenant_numbers", "agents", "leads"):
            db[c].delete_many({"tenant_id": uid})
    print("cleaned")
