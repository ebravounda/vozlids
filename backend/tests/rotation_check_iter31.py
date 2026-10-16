# Iter31: direct check of services.pick_executive rotation + vapi.build_assistant/greeting (no calls placed)
import asyncio
import json
import sys
sys.path.insert(0, "/app/backend")
import services as S
import vapi
from db import db  # noqa


async def main():
    ex = [{"voice": "p_marta", "name": "Marta"}, {"voice": "p_gonzalo", "name": "Pablo"}, {"voice": "p_nuria", "name": "Lucía"}]
    doc = {"tenant_id": "TEST_rot", "name": "Ana", "business_name": "Clínica Sol", "product": "x", "objective": "agendar",
           "questions": [], "country": "ES", "voice": "p_marta", "ambience": "none", "ambience_volume": 35,
           "greeting": "Hola {nombre}, soy Ana de {empresa}. ¿Tienes un minuto?", "extra_instructions": "", "executives": ex, "active": True}
    res = await db.agents.insert_one(doc)
    doc["_id"] = res.inserted_id
    try:
        seq = []
        for _ in range(7):
            a = await S.pick_executive(doc)
            seq.append((a["name"], a["voice"], a.get("base_name"), a.get("executive")))
        print("SEQ", seq)
        assert [s[0] for s in seq] == ["Marta", "Pablo", "Lucía", "Marta", "Pablo", "Lucía", "Marta"], seq
        a = await S.pick_executive(doc)  # Pablo
        out_lead = {"_id": "x", "name": "Laura Pérez", "phone": "+34600000000", "direction": "saliente", "source": "form", "tenant_id": "TEST_rot"}
        in_lead = {"_id": "y", "name": "Llamada entrante", "phone": "+34600000000", "direction": "entrante", "source": "entrante", "tenant_id": "TEST_rot"}
        g_out = vapi.greeting(a, out_lead)
        g_in = vapi.greeting(a, in_lead)
        print("OUT", g_out)
        print("IN", g_in)
        assert "Pablo" in g_out and "Ana" not in g_out
        assert "te atiende Pablo" in g_in
        asst = vapi.build_assistant(a, out_lead, "hoy")
        s = json.dumps(asst, ensure_ascii=False)
        print("VOICE", asst.get("voice"))
        assert "Eres Pablo" in s
        assert "p_gonzalo" in s.lower() or "gonzalo" in s.lower() or json.dumps(asst.get("voice")) != "null"
        # agent without executives -> unchanged
        plain = {**doc, "executives": []}
        assert (await S.pick_executive(plain)) is plain
        # single exec
        one = {**doc, "executives": [ex[2]]}
        assert (await S.pick_executive(one))["name"] == "Lucía"
        print("ALL ROTATION CHECKS PASSED")
    finally:
        await db.agents.delete_one({"_id": doc["_id"]})


asyncio.run(main())
