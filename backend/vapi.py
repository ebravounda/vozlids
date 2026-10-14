import os
import httpx
from countries import COUNTRIES

VAPI_URL = "https://api.vapi.ai"
STANDARD = {
    "elvira": "es-ES-ElviraNeural",
    "alvaro": "es-ES-AlvaroNeural",
    "ximena": "es-ES-XimenaNeural",
    "dario": "es-ES-DarioNeural",
    "irene": "es-ES-IreneNeural",
    "arnau": "es-ES-ArnauNeural",
}
PREMIUM = {
    "p_marta": "de38f545-c574-44e8-9b54-a7d6fec1c6b1",
    "p_nuria": "9d8c6b2e-0a23-4a15-ae1b-121d5b5af417",
    "p_isabel": "c0c374aa-09be-42d9-9828-4d2d7df86962",
    "p_elena": "cefcb124-080b-4655-b31f-932f3ee743de",
    "p_marcos": "13ff5deb-2591-42ad-a356-63a04e524411",
    "p_gonzalo": "58e531e3-b212-49df-adee-c335a19c2429",
    "p_luis": "b5aa8098-49ef-475d-89b0-c9262ecf33fd",
    "p_hector": "b042270c-d46f-4d4f-8fb0-7dd7c5fe5615",
}
STANDARD_CL = {"cl_catalina": "es-CL-CatalinaNeural", "cl_lorenzo": "es-CL-LorenzoNeural"}
PREMIUM_LATAM = {
    "l_fernanda": "b4b8e2af-6139-466e-a93a-30c20d2e1fc5",
    "l_daniela": "5c5ad5e7-1020-476b-8b91-fdcbe9cc313c",
    "l_regina": "e5e5c8d7-3924-4ff6-981a-cb667034be29",
    "l_eduardo": "3efb11f3-4c0e-43c2-bad5-85ab99e993e2",
    "l_mateo": "2fc4f1ec-bfd0-46f1-8e6d-d4279eaaf838",
    "l_andres": "d46e87a1-7c6d-4b18-9359-926f4a35ffdf",
}
VOICES_BY_COUNTRY = {"ES": {**PREMIUM, **STANDARD}, "CL": {**PREMIUM_LATAM, **STANDARD_CL}}
VOICES = {**STANDARD, **PREMIUM, **STANDARD_CL, **PREMIUM_LATAM}
STATE = {"numbers": {}}


def voice_config(voice: str) -> dict:
    premium = {**PREMIUM, **PREMIUM_LATAM}
    if voice in premium:
        return {"provider": "cartesia", "model": "sonic-3", "language": "es", "voiceId": premium[voice]}
    return {"provider": "azure", "voiceId": {**STANDARD, **STANDARD_CL}[voice]}


def number_info(country: str) -> dict:
    info = dict(STATE["numbers"].get(country) or {})
    if country == "ES" and os.environ.get("VAPI_PHONE_NUMBER_ID"):
        info["phone_number_id"] = os.environ["VAPI_PHONE_NUMBER_ID"]
    return info


def phone_number_id(country: str = "ES"):
    return number_info(country).get("phone_number_id")


def _headers() -> dict:
    return {"Authorization": f"Bearer {os.environ['VAPI_API_KEY']}"}


async def _post(path: str, payload: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=20) as x:
            r = await x.post(f"{VAPI_URL}{path}", json=payload, headers=_headers())
    except httpx.HTTPError as e:
        raise VapiError(f"No se pudo contactar con Vapi: {e.__class__.__name__}")
    if r.status_code >= 400:
        try:
            msg = r.json().get("message")
        except ValueError:
            msg = r.text
        if isinstance(msg, list):
            msg = "; ".join(map(str, msg))
        raise VapiError(f"Vapi respondió con error ({r.status_code}): {str(msg)[:300]}")
    return r.json()


async def connect_zadarma(sip_login: str, sip_password: str, number: str, country: str = "ES") -> dict:
    cred = await _post("/credential", {
        "provider": "byo-sip-trunk", "name": f"Zadarma Trunk {country}",
        "gateways": [{"ip": "sip.zadarma.com", "inboundEnabled": False}],
        "outboundLeadingPlusEnabled": True,
        "outboundAuthenticationPlan": {"authUsername": sip_login, "authPassword": sip_password},
    })
    phone = await _post("/phone-number", {
        "provider": "byo-phone-number", "name": f"Zadarma {COUNTRIES[country]['prefix']}", "number": number.lstrip("+"),
        "numberE164CheckEnabled": False, "credentialId": cred["id"],
    })
    return {"credential_id": cred["id"], "phone_number_id": phone["id"]}
OBJECTIVES = {
    "agendar": (
        "Tu objetivo es calificar al lead con las preguntas y, si encaja, reservarle una cita. Para reservar: llama primero a "
        "check_availability (con la fecha que prefiera el lead, o sin fecha para ver los próximos huecos), ofrece como máximo dos o "
        "tres horas, y cuando el lead elija llama a book_appointment. Nunca inventes horarios ni des una cita por confirmada si "
        "book_appointment no ha respondido ok. Tras reservar, repite el día y la hora en voz alta."
    ),
    "calificar": (
        "Tu objetivo es calificar al lead con las preguntas. No reserves citas ni cierres ventas. Al terminar, agradece y explica "
        "que una persona del equipo le contactará pronto."
    ),
    "vender": (
        "Tu objetivo es presentar la oferta, resolver dudas y objeciones con honestidad y conseguir un sí claro. Si acepta, confirma "
        "qué ha aceptado y explica que recibirá los siguientes pasos por email o teléfono. No pidas datos de tarjeta ni cobres en la "
        "llamada. No presiones si dice que no."
    ),
}
OUTCOMES = ["calificado", "no_interesado", "cita_agendada", "venta", "no_llamar", "sin_respuesta"]
AI_OUTCOMES = ["calificado", "no_interesado", "cita_agendada", "venta", "no_llamar"]


class VapiError(Exception):
    pass


def configured(country: str = "ES") -> bool:
    return bool(os.environ.get("VAPI_API_KEY")) and bool(phone_number_id(country))


def public_url() -> str:
    return os.environ["PUBLIC_BACKEND_URL"].rstrip("/")


def webhook_url() -> str:
    return f"{public_url()}/api/vapi/webhook"


def background_sound(agent: dict) -> str:
    a = agent.get("ambience", "oficina")
    if a == "none":
        return "off"
    if a == "vapi_office":
        return "office"
    vol = int(agent.get("ambience_volume", 35))
    if a.startswith("custom:"):
        return f"{public_url()}/api/ambience/custom/{a[7:]}/{vol}.wav"
    return f"{public_url()}/api/ambience/{a}/{vol}.wav?v=2"


async def get_call(call_id: str) -> dict:
    async with httpx.AsyncClient(timeout=20) as x:
        r = await x.get(f"{VAPI_URL}/call/{call_id}", headers=_headers())
    if r.status_code >= 400:
        raise VapiError(f"Vapi no devolvió la llamada ({r.status_code})")
    return r.json()


async def recording_url(call_id: str) -> str:
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as x:
        r = await x.get(f"{VAPI_URL}/call/{call_id}/mono-recording", headers=_headers())
    if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
        return r.headers["location"]
    raise VapiError("La grabación aún no está disponible")


def first_name(name: str) -> str:
    return (name or "").strip().split(" ")[0]


def greeting(agent: dict, lead: dict) -> str:
    return (lead.get("greeting") or agent["greeting"]).replace("{nombre}", first_name(lead["name"])).strip()


def system_prompt(agent: dict, lead: dict, today: str) -> str:
    qs = "\n".join(f"- {q}" for q in agent.get("questions") or [] if q.strip()) or \
        "- Sin preguntas fijas: averigua de forma natural qué necesita, para cuándo y su presupuesto aproximado."
    extra = f"\nINSTRUCCIONES ADICIONALES DEL NEGOCIO\n{agent['extra_instructions']}\n" if agent.get("extra_instructions") else ""
    return f"""Eres {agent['name']}, asistente virtual de {agent['business_name']}. Estás llamando por teléfono a una persona que acaba de dejar sus datos en la web pidiendo información.
{today}

SOBRE EL NEGOCIO Y EL PRODUCTO
{agent['product']}

DATOS DEL LEAD
- Nombre: {lead['name']}
- Email: {lead.get('email') or 'no indicado'}

OBJETIVO
{("MOTIVO DE ESTA LLAMADA (tiene prioridad sobre el objetivo general): " + lead['purpose']) if lead.get('purpose') else OBJECTIVES[agent['objective']]}

PREGUNTAS DE CALIFICACIÓN (de una en una, en orden natural, sin que suene a encuesta)
{qs}

CÓMO HABLAS
- {COUNTRIES[agent.get('country', 'ES')]['style']}
- Frases cortas: como máximo dos frases por turno y termina casi siempre con una pregunta.
- Nunca leas listas ni uses formato. Di números y horas como se dicen en voz alta ("a las diez y media").
- Si el lead te interrumpe, para y responde a lo que dice.
- No inventes precios, plazos ni datos que no estén arriba; si no lo sabes, di que lo consultará el equipo.

TRANSPARENCIA Y RESPETO (obligatorio)
- Eres un asistente virtual con IA. Si el saludo inicial no lo ha dejado claro, dilo en tu primera respuesta. Si te preguntan si eres una persona, responde con sinceridad que eres un asistente virtual.
- La llamada se graba para mejorar el servicio; si lo preguntan, confírmalo.
- Si el lead pide que no le llamen más o se molesta por la llamada, discúlpate, llama a mark_do_not_call y despídete.
- Si no es buen momento, pregunta cuándo le viene mejor y despídete.
- Cuando la conversación termine, despídete con amabilidad y finaliza la llamada.
{extra}"""


def _fn_tool(name: str, description: str, properties: dict, required: list, server: dict) -> dict:
    return {
        "type": "function",
        "function": {"name": name, "description": description,
                     "parameters": {"type": "object", "properties": properties, "required": required}},
        "server": server,
    }


def tools(agent: dict, server: dict) -> list:
    out = [{"type": "endCall"}, _fn_tool(
        "mark_do_not_call", "Añade al lead a la lista de no llamar cuando pide que no le vuelvan a llamar.", {}, [], server),
        _fn_tool("request_support", "Registra una solicitud de asistencia técnica cuando el cliente tiene un problema o necesita ayuda.",
                 {"issue": {"type": "string", "description": "Descripción breve del problema del cliente"}}, ["issue"], server)]
    if agent["objective"] == "agendar":
        out.append(_fn_tool(
            "check_availability", "Consulta los huecos libres para citas. Sin fecha devuelve los próximos días con huecos.",
            {"date": {"type": "string", "description": "Fecha en formato YYYY-MM-DD (opcional)"}}, [], server))
        out.append(_fn_tool(
            "book_appointment", "Reserva una cita en un hueco libre devuelto por check_availability.",
            {"date": {"type": "string", "description": "Fecha YYYY-MM-DD"},
             "time": {"type": "string", "description": "Hora HH:MM en formato 24h"},
             "notes": {"type": "string", "description": "Notas breves sobre lo que necesita el lead"}},
            ["date", "time"], server))
    return out


def analysis_plan() -> dict:
    return {
        "summaryPlan": {"enabled": True, "messages": [
            {"role": "system", "content": "Eres analista comercial. Resume la llamada en español de España en 2 a 4 frases: "
                                          "interés del lead, respuestas clave, objeciones y siguiente paso acordado. "
                                          "Escribe directamente el resumen, sin introducciones, títulos ni formato."},
            {"role": "user", "content": "Transcripción:\n\n{{transcript}}\n\nMotivo de fin: {{endedReason}}"},
        ]},
        "successEvaluationPlan": {"enabled": False},
        "structuredDataPlan": {"enabled": True, "schema": {
            "type": "object",
            "properties": {
                "outcome": {"type": "string", "enum": AI_OUTCOMES,
                            "description": "Resultado: calificado (interesado y encaja), no_interesado (no le interesa o "
                                           "colgó sin mostrar interés), cita_agendada, venta (aceptó comprar), "
                                           "no_llamar (pidió no ser llamado)."},
                "interest_score": {"type": "number", "description": "Interés del lead de 0 a 100"},
                "answers": {"type": "string", "description": "Respuestas del lead a las preguntas de calificación, en español"},
            },
            "required": ["outcome", "interest_score"],
        }},
    }


def build_assistant(agent: dict, lead: dict, today: str) -> dict:
    secret = os.environ["VAPI_WEBHOOK_SECRET"]
    server = {"url": f"{webhook_url()}?token={secret}", "headers": {"x-vapi-secret": secret}}
    return {
        "name": f"{agent['name']} {agent['business_name']}"[:40],
        "firstMessage": greeting(agent, lead),
        "firstMessageMode": "assistant-speaks-first",
        "model": {"provider": "openai", "model": "gpt-4o", "temperature": 0.5,
                  "messages": [{"role": "system", "content": system_prompt(agent, lead, today)}],
                  "tools": tools(agent, server)},
        "voice": voice_config(agent["voice"]),
        "transcriber": {"provider": "deepgram", "model": "nova-2", "language": COUNTRIES[agent.get("country", "ES")]["stt"]},
        "backgroundSound": background_sound(agent),
        "silenceTimeoutSeconds": 30,
        "maxDurationSeconds": 900,
        "serverMessages": ["status-update", "end-of-call-report", "tool-calls"],
        "server": server,
        "analysisPlan": analysis_plan(),
        "artifactPlan": {"recordingEnabled": True},
    }


async def create_call(agent: dict, lead: dict, today: str) -> str:
    payload = {
        "phoneNumberId": phone_number_id(agent.get("country", "ES")),
        "customer": {"number": lead["phone"], "name": lead["name"][:40]},
        "assistant": build_assistant(agent, lead, today),
        "metadata": {"lead_id": str(lead["_id"]), "tenant_id": lead["tenant_id"]},
    }
    return (await _post("/call", payload)).get("id")
