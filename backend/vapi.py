import os
import httpx

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
VOICES = {**STANDARD, **PREMIUM}
STATE = {"phone_number_id": None, "number": None}


def voice_config(voice: str) -> dict:
    if voice in PREMIUM:
        return {"provider": "cartesia", "model": "sonic-3", "language": "es", "voiceId": PREMIUM[voice]}
    return {"provider": "azure", "voiceId": STANDARD[voice]}


def phone_number_id():
    return os.environ.get("VAPI_PHONE_NUMBER_ID") or STATE["phone_number_id"]


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


async def connect_zadarma(sip_login: str, sip_password: str, number: str) -> dict:
    cred = await _post("/credential", {
        "provider": "byo-sip-trunk", "name": "Zadarma Trunk",
        "gateways": [{"ip": "sip.zadarma.com", "inboundEnabled": False}],
        "outboundLeadingPlusEnabled": True,
        "outboundAuthenticationPlan": {"authUsername": sip_login, "authPassword": sip_password},
    })
    phone = await _post("/phone-number", {
        "provider": "byo-phone-number", "name": "Zadarma +34", "number": number.lstrip("+"),
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


class VapiError(Exception):
    pass


def configured() -> bool:
    return bool(os.environ.get("VAPI_API_KEY")) and bool(phone_number_id())


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
    return f"{public_url()}/api/ambience/{a}/{int(agent.get('ambience_volume', 35))}.wav?v=2"


def first_name(name: str) -> str:
    return (name or "").strip().split(" ")[0]


def greeting(agent: dict, lead: dict) -> str:
    return agent["greeting"].replace("{nombre}", first_name(lead["name"])).strip()


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
{OBJECTIVES[agent['objective']]}

PREGUNTAS DE CALIFICACIÓN (de una en una, en orden natural, sin que suene a encuesta)
{qs}

CÓMO HABLAS
- Español de España, tuteo cercano y profesional (pasa a "usted" si el lead lo usa).
- Frases cortas: como máximo dos frases por turno y termina casi siempre con una pregunta.
- Suena natural: de vez en cuando usa expresiones como "vale", "perfecto", "genial", "entiendo" o "mmm, déjame ver", sin exagerar.
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
        "mark_do_not_call", "Añade al lead a la lista de no llamar cuando pide que no le vuelvan a llamar.", {}, [], server)]
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
                                          "interés del lead, respuestas clave, objeciones y siguiente paso acordado."},
            {"role": "user", "content": "Transcripción:\n\n{{transcript}}\n\nMotivo de fin: {{endedReason}}"},
        ]},
        "structuredDataPlan": {"enabled": True, "schema": {
            "type": "object",
            "properties": {
                "outcome": {"type": "string", "enum": OUTCOMES,
                            "description": "Resultado: calificado (interesado y encaja), no_interesado, cita_agendada, venta "
                                           "(aceptó comprar), no_llamar (pidió no ser llamado), sin_respuesta (no habló nadie)."},
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
        "transcriber": {"provider": "deepgram", "model": "nova-2", "language": "es"},
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
        "phoneNumberId": phone_number_id(),
        "customer": {"number": lead["phone"], "name": lead["name"][:40]},
        "assistant": build_assistant(agent, lead, today),
        "metadata": {"lead_id": str(lead["_id"]), "tenant_id": lead["tenant_id"]},
    }
    return (await _post("/call", payload)).get("id")
