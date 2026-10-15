# Verify saas.usage_alerts sends once per threshold per month (emailer.send monkeypatched)
import asyncio, os, sys
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
import saas, emailer
from db import db

sent = []
async def fake_send(to, subject, *a, **k):
    if "test_iter28" in to:
        sent.append(subject)
emailer.send = fake_send
saas.emailer.send = fake_send

async def main():
    await db.users.update_one({"email": "test_iter28_ui@example.com"}, {"$set": {"billing_status": "active"}, "$unset": {"usage_alerts": ""}})
    await saas.usage_alerts(); r1 = list(sent)
    await saas.usage_alerts(); r2 = list(sent)
    u = await db.users.find_one({"email": "test_iter28_ui@example.com"})
    await db.leads.update_one({"test_iter28": True}, {"$set": {"duration_seconds": 101 * 60}})
    await saas.usage_alerts(); r3 = list(sent)
    await saas.usage_alerts(); r4 = list(sent)
    await db.leads.update_one({"test_iter28": True}, {"$set": {"duration_seconds": 85 * 60}})
    print("after1", r1, "after2", r2, "flags", u.get("usage_alerts"), "after100", r3, "again", r4)

asyncio.run(main())
