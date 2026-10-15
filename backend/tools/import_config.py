"""Import VozLeads configuration exported from the preview environment (JSON on stdin)."""
import asyncio
import os
import sys
from bson import json_util
from motor.motor_asyncio import AsyncIOMotorClient
sys.path.insert(0, "/app")
import auth as A  # noqa: E402


async def main():
    data = json_util.loads(sys.stdin.read())
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    admin = data["users"][0]
    email = os.environ["ADMIN_EMAIL"].lower()
    async for u in db.users.find({"email": email, "_id": {"$ne": admin["_id"]}}):
        tid = str(u["_id"])
        for c in ("agents", "call_templates", "availability"):
            await db[c].delete_many({"tenant_id": tid})
        await db.users.delete_one({"_id": u["_id"]})
    admin.update(email=email, password_hash=A.hash_password(os.environ["ADMIN_PASSWORD"]))
    for col, docs in data.items():
        for d in docs:
            await db[col].replace_one({"_id": d["_id"]}, d, upsert=True)
        print(f"{col}: {len(docs)}")
    print(f"Administrador: {email}")


asyncio.run(main())
