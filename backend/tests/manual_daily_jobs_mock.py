import asyncio, time
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
import daily_jobs as J, billing as B, emailer, webscan as W
from db import db
sent = []
async def send(to, subj, *a, **k): sent.append((to, subj)); return True
emailer.send = send
class Subs:
    def __init__(self, d): self.data = d
class C:
    class v1:
        class subscriptions:
            @staticmethod
            def list(p):
                now = time.time()
                return Subs([{"id": "sub_rem", "current_period_end": int(now + 2.5 * 86400), "items": {"data": [{"price": {"currency": "eur", "unit_amount": 4900}, "quantity": 1}]}},
                             {"id": "sub_far", "current_period_end": int(now + 10 * 86400), "items": {"data": []}}])
async def client(mode): return C, {"test_key": ""}, False
B.client = client
async def key(): return "k"
async def site(url): return "Clínica X. Limpieza 60€. Nuevo horario sábados 9-14.", 1
class Chat:
    def __init__(self, **k): pass
    def with_model(self, *a): return self
    async def send_message(self, m): return "- Nuevo horario: sábados de 9 a 14.\n- Limpieza ahora 60 €."
W._key, W.read_site, J.LlmChat = key, site, Chat
async def main():
    u = await db.users.insert_one({"email": "dj@example.com", "role": "business", "stripe_subscription_id": "sub_rem"})
    a = await db.agents.insert_one({"tenant_id": str(u.inserted_id), "name": "Marta", "website": "https://x.com", "product": "Clínica X. Limpieza 50€."})
    try:
        print("reminders", await J.payment_reminders(), sent)
        print("again (no dup)", await J.payment_reminders())
        print("web", await J.refresh_websites(), sent[-1])
        ag = await db.agents.find_one({"_id": a.inserted_id}); print("suggestion", ag.get("web_suggestion", {}).get("text"))
        print("web again (not due)", await J.refresh_websites())
        r = await J.apply_suggestion(str(a.inserted_id), {"id": str(u.inserted_id)}); print("applied", r["product"][-80:])
    finally:
        await db.agents.delete_one({"_id": a.inserted_id}); await db.users.delete_one({"_id": u.inserted_id})
asyncio.run(main())
