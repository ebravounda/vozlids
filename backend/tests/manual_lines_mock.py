import asyncio
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
import lines as Li, zadarma as Z, vapi, kyc, extra_numbers as E
from fastapi import HTTPException
from db import db
NUMS = [{"number": "34919000111", "status": "on"}, {"number": "56221110000", "status": "on"}, {"number": "34910000999", "status": "off"}]
SIPS = [{"id": "100", "display_name": "Mi SIP 1"}, {"id": "101", "display_name": "Mi SIP 2"}, {"id": "102", "display_name": "Mi SIP 3"}]
calls = []
async def mn(): return NUMS
async def ls(): return SIPS, 1
async def reuse(s, p, n): calls.append(("reuse", s, n))
async def create(name, p, n): calls.append(("create", n)); SIPS.append({"id": "200", "display_name": name}); return "200"
cnt = [0]
async def conn(*a): cnt[0] += 1; return {"phone_number_id": f"pn{cnt[0]}", "credential_id": f"cr{cnt[0]}"}
async def route(n, uri): calls.append(("route", n, uri))
deleted = []
async def dele(p): deleted.append(p)
async def grp(t): return "g1"
Z.my_numbers, Z.list_sips, Z.reuse_sip, Z.create_sip, vapi.connect_tenant_number, Z.route_to, vapi.delete = mn, ls, reuse, create, conn, route, dele
kyc.group_for = grp
ADMIN = {"id": "000000000000000000000001", "role": "admin"}
async def tryit(label, coro):
    try: print(label, "->", await coro)
    except HTTPException as e: print(label, "-> ERR", e.status_code, e.detail)
async def main():
    u = await db.users.insert_one({"email": "lines_t@example.com", "business_name": "Lines T", "role": "business", "country": "ES"})
    tid = str(u.inserted_id)
    a1 = str((await db.agents.insert_one({"tenant_id": tid, "name": "Recepción", "country": "ES"})).inserted_id)
    a2 = str((await db.agents.insert_one({"tenant_id": tid, "name": "Chile", "country": "CL"})).inserted_id)
    try:
        await tryit("main own sip", Li.connect(Li.ConnectIn(number="+34919000111", tenant_id=tid, role="main", sip_id="100"), ADMIN))
        await tryit("sip in use", Li.connect(Li.ConnectIn(number="+56221110000", tenant_id=tid, role="agent", agent_id=a2, sip_id="100"), ADMIN))
        await tryit("agent new sip", Li.connect(Li.ConnectIn(number="+56221110000", tenant_id=tid, role="agent", agent_id=a2, sip_id="new"), ADMIN))
        await tryit("number in use", Li.connect(Li.ConnectIn(number="+56221110000", tenant_id=tid, role="main", sip_id="101"), ADMIN))
        await tryit("change agent", Li.change_agent("+34919000111", Li.AgentIn(agent_id=a2), ADMIN))
        await tryit("reconfigure other sip", Li.reconfigure("+34919000111", Li.SipIn(sip_id="101"), ADMIN))
        await tryit("reconfigure all", Li.reconfigure_all(ADMIN))
        await tryit("move to platform", Li.move("+56221110000", Li.MoveIn(tenant_id=tid, role="platform", sip_id="102"), ADMIN))
        print("STATE CL", vapi.STATE["numbers"].get("CL"))
        L = await Li.lines(ADMIN)
        for r in L["lines"]: print(" ", {k: r.get(k) for k in ("number", "role", "owner", "agent", "sip_id", "ok_in", "ok_out", "ok_docs", "usable")})
        print(" sips", L["sips"])
        opts = await Li.options(ADMIN)
        print(" opts", [(o["name"], o["main_number"], [(a["name"], a["has_own"]) for a in o["agents"]]) for o in opts["owners"] if o["id"] == tid])
        await tryit("disconnect platform", Li.disconnect("+56221110000", ADMIN))
        print("STATE CL after", vapi.STATE["numbers"].get("CL"))
        await tryit("disconnect main", Li.disconnect("+34919000111", ADMIN))
        print("deleted", deleted[:6], "calls", calls[:8])
    finally:
        await db.tenant_numbers.delete_many({"tenant_id": tid}); await db.agents.delete_many({"tenant_id": tid}); await db.users.delete_one({"_id": u.inserted_id})
        await db.platform_settings.update_one({"_id": "telephony"}, {"$unset": {"numbers.CL": ""}}) if False else None
asyncio.run(main())
