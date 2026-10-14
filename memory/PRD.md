# VozLead — PRD

## Original problem statement
"Necesito crear algo como https://vystral.com/ que llame a los clientes interesados de mi producto con ia y se escuche 100% real con teclados de fondo etc."

## Architecture
- FastAPI + MongoDB (backend/server.py routes, services.py call/tool logic, vapi.py assistant payload, ambience.py synthesized office/keyboard/call-center WAV, seed.py demo data, auth.py JWT cookies)
- React (CRA) + shadcn, dark emerald theme, Spanish UI
- Telephony: Vapi transient assistant per call (Azure es-ES voices, Deepgram es, GPT-4o, backgroundSound = our WAV URL with volume) + Zadarma +34 SIP number imported into Vapi
- Webhook /api/vapi/webhook (secret header or ?token) handles status-update, tool-calls (check_availability, book_appointment, mark_do_not_call), end-of-call-report (summary, structured outcome, score, transcript, recording)

## Personas
- Spanish SMBs with leads (clinics, real estate, academies)
- SaaS owner (admin)

## Implemented (2026-06)
- Email/password auth, tenant-isolated data, brute-force lockout
- Agent builder: objective (agendar/calificar/vender), questions, 6 es-ES voices, 5 ambiences + volume, greeting with {nombre}, extra instructions, active toggle, preview (ambience real + browser TTS)
- Embeddable public form /f/:agentId with consent, dedupe 10 min, DNC check, IP rate limit → instant call
- "Llamarme ahora" test call
- Agenda: weekly hours, slot length, appointments list/cancel, no double booking (unique index)
- Leads panel with stats, filters, polling, detail sheet (recording, summary, score, chat transcript, appointment)
- Do-not-call list (manual + automatic)
- Telephony status page with Zadarma→Vapi setup steps
- Landing page
- Seeded demo account with sample data labelled "Ejemplo"

## Pending / blockers
- VAPI_API_KEY and VAPI_PHONE_NUMBER_ID empty → real calls end as "Fallida" until provided

## Backlog
- P1: Stripe plans + minute limits; auto-retries for no-answer; SMS/WhatsApp confirmation; Google Calendar; CSV campaigns
- P2: WhatsApp AI follow-up; human handoff; CRM/webhooks; SaaS admin panel with usage/costs; inbound agents
