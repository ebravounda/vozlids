import os
from datetime import timedelta
import auth as A
import services as S
from db import db
from models import Agent, Appointment, Lead, now_iso

SAMPLE_PRODUCT = ("Clínica dental en Madrid (Chamberí). Primera visita y revisión gratis. Ortodoncia invisible desde 2.900 €, "
                  "implantes desde 990 € y blanqueamiento por 290 €. Financiación hasta 24 meses sin intereses.")


def _sample_leads(tid: str, aid: str) -> list:
    convo = [
        ("agente", "Hola Carlos, soy Marta, la asistente virtual de Clínica Dental Sonrisa. Te llamo porque acabas de pedir "
                   "información sobre ortodoncia invisible. La llamada se graba para mejorar el servicio. ¿Tienes un minuto?"),
        ("lead", "Sí, sí, dime."),
        ("agente", "Genial. ¿Es para ti o para otra persona de tu familia?"),
        ("lead", "Para mí. Llevo tiempo queriendo arreglarme los dientes de abajo."),
        ("agente", "Vale, entiendo. ¿Y más o menos cuándo te gustaría empezar el tratamiento?"),
        ("lead", "Pues este verano si puede ser."),
        ("agente", "Perfecto. Te puedo reservar la primera visita gratis. ¿Te viene bien el jueves a las diez y media?"),
        ("lead", "El jueves a las diez y media me va genial."),
        ("agente", "Hecho, te queda reservada el jueves a las diez y media. ¡Gracias, Carlos, que tengas un buen día!"),
    ]
    base = [
        ("Carlos Ruiz", "+34612345678", "carlos.ruiz@ejemplo.es", "cita_agendada", 88,
         "Carlos quiere ortodoncia invisible para la arcada inferior y empezar este verano. Muy interesado; se le reserva "
         "primera visita gratuita el jueves a las 10:30.", convo),
        ("María Fernández", "+34634567890", "maria.f@ejemplo.es", "calificado", 64,
         "María pregunta por implantes para su madre. Presupuesto ajustado, interesada en la financiación. Prefiere que la "
         "llamen por la tarde.", []),
        ("Alejandro Gómez", "+34698765432", "", "no_interesado", 15,
         "Alejandro pidió información por curiosidad; ya tiene dentista de confianza y no quiere cambiar.", []),
        ("Lucía Martín", "+34655443322", "lucia.martin@ejemplo.es", "sin_respuesta", None, "", []),
    ]
    out = []
    for i, (name, phone, email, status, score, summary, msgs) in enumerate(base):
        lead = Lead(tenant_id=tid, agent_id=aid, agent_name="Marta", name=name, phone=phone, email=email, status=status,
                    call_phase="ended", is_sample=True, interest_score=score, summary=summary,
                    messages=[{"role": r, "text": t, "t": j * 6} for j, (r, t) in enumerate(msgs)],
                    duration_seconds=96 if msgs else None,
                    ended_reason="customer-did-not-answer" if status == "sin_respuesta" else "assistant-ended-call")
        doc = lead.to_mongo()
        doc["created_at"] = doc["updated_at"] = (S.madrid_now() - timedelta(hours=i * 5 + 1)).isoformat()
        out.append(doc)
    return out


async def seed():
    email = os.environ["ADMIN_EMAIL"].lower()
    password = os.environ["ADMIN_PASSWORD"]
    user = await db.users.find_one({"email": email})
    if not user:
        res = await db.users.insert_one({"email": email, "password_hash": A.hash_password(password), "name": "Admin",
                                         "business_name": "Clínica Dental Sonrisa", "role": "admin",
                                         "created_at": now_iso()})
        tid = str(res.inserted_id)
    else:
        tid = str(user["_id"])
        if not A.verify_password(password, user["password_hash"]):
            await db.users.update_one({"_id": user["_id"]}, {"$set": {"password_hash": A.hash_password(password)}})
    await S.get_availability(tid)
    if await db.agents.count_documents({"tenant_id": tid}):
        return
    agent = Agent(tenant_id=tid, name="Marta", business_name="Clínica Dental Sonrisa", product=SAMPLE_PRODUCT,
                  objective="agendar", voice="elvira", ambience="oficina", ambience_volume=35, is_sample=True,
                  questions=["¿El tratamiento es para ti o para otra persona?", "¿Qué te gustaría mejorar de tu sonrisa?",
                             "¿Cuándo te gustaría empezar?"],
                  greeting="Hola {nombre}, soy Marta, la asistente virtual de Clínica Dental Sonrisa. Te llamo porque acabas "
                           "de pedir información en nuestra web. La llamada se graba para mejorar el servicio. ¿Tienes un minuto?")
    aid = str((await db.agents.insert_one(agent.to_mongo())).inserted_id)
    leads = _sample_leads(tid, aid)
    res = await db.leads.insert_many(leads)
    d = S.madrid_now().date() + timedelta(days=2)
    appt = Appointment(tenant_id=tid, lead_id=str(res.inserted_ids[0]), lead_name="Carlos Ruiz", lead_phone="+34612345678",
                       agent_id=aid, start=f"{d.isoformat()}T10:30", notes="Primera visita ortodoncia invisible",
                       is_sample=True)
    appt_id = (await db.appointments.insert_one(appt.to_mongo())).inserted_id
    await db.leads.update_one({"_id": res.inserted_ids[0]}, {"$set": {"appointment_id": str(appt_id)}})
