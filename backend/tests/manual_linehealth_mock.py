import asyncio, os
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
import linehealth as H, lines as Li, zadarma as Z, vapi, emailer, saas
from fastapi import HTTPException
from db import db
sent = []
async def creds(): return {"key": "k"}
NUMS = [{"number": "34919000111", "status": "on"}]
async def mn(): return NUMS
async def ls(): return [{"id": "100"}], 0
OK = {"v": True}
async def vok(pid): return OK["v"]
async def send(to, subj, *a, **k): sent.append(subj); return True
async def ccall(agent, lead, today, phone_id): return "call_123"
async def noquota(t): return ""
Z.creds, Z.my_numbers, Z.list_sips, H._vapi_ok, emailer.send, vapi.create_call, saas.quota_error = creds, mn, ls, vok, send, ccall, noquota
os.environ.setdefault("VAPI_API_KEY", "x")
async def main():
    u = await db.users.insert_one({"email": "lh@example.com", "business_name": "LH", "role": "business", "country": "ES"})
    tid = str(u.inserted_id)
    aid = str((await db.agents.insert_one({"tenant_id": tid, "name": "Marta", "country": "ES", "business_name": "LH", "voice": "e_sarah", "active": True})).inserted_id)
    await db.tenant_numbers.insert_one({"tenant_id": tid, "number": "+34919000111", "status": "activo", "phone_number_id": "pn_1", "credential_id": "cr", "sip_id": "100", "inbound_agent_id": aid})
    try:
        print("1 ok", await H.check_once(), sent)
        OK["v"] = False
        print("2 down", await H.check_once(), sent)
        print("3 still down (no new email)", len(sent))
        await H.check_once(); print("   emails", len(sent))
        OK["v"] = True
        print("4 back", await H.check_once(), sent)
        r = await Li.test_line("+34919000111", Li.TestIn(phone="600850506"), {"id": "x", "role": "admin"})
        print("test call ->", r)
        ld = await db.leads.find_one({"tenant_id": tid, "source": "prueba_linea"})
        print("lead", ld.get("line_number"), ld.get("vapi_call_id"), ld.get("status"), ld.get("error"))
    finally:
        for c in ("tenant_numbers", "agents", "leads"): await db[c].delete_many({"tenant_id": tid})
        await db.users.delete_one({"_id": u.inserted_id})
asyncio.run(main())
