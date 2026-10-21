"""Extra call languages: each one is answered by a native executive the call is handed off to."""

LANGS = {
    "en": {"name": "inglés", "native": "English", "stt": ("nova-3", "en"),
           "first": "Of course! I'm {name} and I'll help you in English. How can I help you?",
           "style": "Speak natural, warm and professional English, like a friendly receptionist. Short sentences."},
    "pt": {"name": "portugués", "native": "português", "stt": ("nova-2", "pt"),
           "first": "Claro! Sou {name} e vou atendê-lo em português. Em que posso ajudar?",
           "style": "Fala português natural, simpático e profissional. Frases curtas."},
    "fr": {"name": "francés", "native": "français", "stt": ("nova-2", "fr"),
           "first": "Bien sûr ! Je suis {name} et je vais vous aider en français. Comment puis-je vous aider ?",
           "style": "Parle un français naturel, chaleureux et professionnel, en vouvoyant. Phrases courtes."},
    "ca": {"name": "catalán", "native": "català", "stt": ("nova-2", "ca"),
           "first": "I tant! Sóc {name} i t'atendré en català. En què et puc ajudar?",
           "style": "Parla un català natural, proper i professional. Frases curtes."},
    "it": {"name": "italiano", "native": "italiano", "stt": ("nova-2", "it"),
           "first": "Certo! Sono {name} e la assisto in italiano. Come posso aiutarla?",
           "style": "Parla un italiano naturale, cordiale e professionale. Frasi brevi."},
    "de": {"name": "alemán", "native": "Deutsch", "stt": ("nova-2", "de"),
           "first": "Natürlich! Ich bin {name} und helfe Ihnen gerne auf Deutsch. Was kann ich für Sie tun?",
           "style": "Sprich natürliches, freundliches und professionelles Deutsch (Sie-Form). Kurze Sätze."},
}

# id: (language, Azure neural voice, female)
LANG_VOICES = {
    "en_jenny": ("en", "en-US-JennyNeural", True), "en_guy": ("en", "en-US-GuyNeural", False),
    "en_sonia": ("en", "en-GB-SoniaNeural", True), "en_ryan": ("en", "en-GB-RyanNeural", False),
    "pt_francisca": ("pt", "pt-BR-FranciscaNeural", True), "pt_antonio": ("pt", "pt-BR-AntonioNeural", False),
    "pt_raquel": ("pt", "pt-PT-RaquelNeural", True), "pt_duarte": ("pt", "pt-PT-DuarteNeural", False),
    "fr_denise": ("fr", "fr-FR-DeniseNeural", True), "fr_henri": ("fr", "fr-FR-HenriNeural", False),
    "ca_joana": ("ca", "ca-ES-JoanaNeural", True), "ca_enric": ("ca", "ca-ES-EnricNeural", False),
    "it_elsa": ("it", "it-IT-ElsaNeural", True), "it_diego": ("it", "it-IT-DiegoNeural", False),
    "de_katja": ("de", "de-DE-KatjaNeural", True), "de_conrad": ("de", "de-DE-ConradNeural", False),
}
# ElevenLabs Flash v2.5 does not speak Catalan.
ELEVEN_LANGS = {"es", "en", "pt", "fr", "it", "de"}


def azure_fallback(lang: str, female: bool) -> str:
    return next(v for v, f in ((v[1], v[2]) for v in LANG_VOICES.values() if v[0] == lang) if f == female)


def transcriber(lang: str) -> dict:
    model, code = LANGS[lang]["stt"]
    return {"provider": "deepgram", "model": model, "language": code}


def choices(agent: dict) -> list:
    return [e for e in agent.get("languages") or [] if e.get("lang") in LANGS and e.get("voice") and e.get("name")]


def ask_line(agent: dict) -> str:
    opts = ["español"] + [LANGS[e["lang"]]["native"] for e in choices(agent)]
    return f"¿En qué idioma prefieres que te atienda: {', '.join(opts[:-1])} o {opts[-1]}?"


def prompt_block(agent: dict) -> str:
    names = ", ".join(f"{LANGS[e['lang']]['name']} ({e['lang']})" for e in choices(agent))
    return f"""
IDIOMAS DE ATENCIÓN
- Puedes atender en español o pasar la llamada a un compañero nativo en: {names}.
- Al empezar, justo después de saludar (y de confirmar con quién hablas si es una llamada saliente), pregunta: «{ask_line(agent)}». Si ya lo preguntaste en el saludo, no lo repitas.
- Si la persona elige uno de esos idiomas, o te habla directamente en uno de ellos, llama al instante a cambiar_idioma con su código, sin decir nada más.
- Si elige español, sigue tú con normalidad. Si pide otro idioma que no está en la lista, dile con amabilidad que puedes atenderle en español o en los idiomas indicados.
"""


def handoff_tool(agent: dict, server: dict) -> dict:
    codes = [e["lang"] for e in choices(agent)]
    return {"type": "handoff",
            "function": {"name": "cambiar_idioma",
                         "description": "Pasa la llamada al compañero nativo que atiende en el idioma que ha elegido la persona.",
                         "parameters": {"type": "object", "properties": {
                             "destination": {"type": "string", "enum": ["dynamic"]},
                             "language": {"type": "string", "enum": codes,
                                          "description": "Idioma elegido: " + ", ".join(f"{c}={LANGS[c]['name']}" for c in codes)}},
                             "required": ["destination", "language"]}},
            "destinations": [{"type": "dynamic", "server": server}],
            "messages": [{"type": "request-start", "content": "Un momento, por favor.", "blocking": True}]}
