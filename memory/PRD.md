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

## Iteration 2 (2026-06)
- VAPI_API_KEY set (validated; assistant config accepted by Vapi API for Cartesia + Azure voices)
- 8 premium Castilian voices (Cartesia sonic-3 via Vapi billing) + 6 standard Azure voices; new agents default to premium Marta
- Admin-only "Conectar número" form on Telefonía: creates Vapi byo-sip-trunk credential (sip.zadarma.com) + byo-phone-number, stores phone_number_id in platform_settings (overridable by VAPI_PHONE_NUMBER_ID env)

## Iteration 3 (2026-06)
- Real public-domain keyboard recordings (Wikimedia Commons) → presets oficina_real / teclado_real, cleaned (HPF 220 Hz + tonal notch) to avoid buzz; assets in backend/assets/ambience
- Custom ambience uploads (any audio → ffmpeg via imageio-ffmpeg → cleaned WAV in Emergent object storage), served at /api/ambience/custom/{token}/{vol}.wav; admin uploads shared as library
- Recording playback via /api/leads/{id}/recording (302 to Vapi signed URL; Vapi recordings are private)
- Transcript UI with Agente/Cliente + mm:ss, copy & .txt download
- Cost tracking: cost + costBreakdown stored from end-of-call-report (fallback GET /call after 45 s, manual sync); admin page /app/costes with breakdown, per business, per call, pricing params (Zadarma $/min, USD→EUR, margin) and suggested plans
- Status fix: AI can no longer mark a call where the customer spoke as sin_respuesta; summary without preamble; successEvaluation disabled (saves cost)
- NOTE: testing agent accidentally placed 1–2 real calls to fake numbers (+34612000222 no answer); tests now skip live call paths

## Pending / blockers
- None blocking. Telephony live (Zadarma +34919932652 connected)

## Backlog
- P1: Stripe plans + minute limits; auto-retries for no-answer; SMS/WhatsApp confirmation; Google Calendar; CSV campaigns
- P2: WhatsApp AI follow-up; human handoff; CRM/webhooks; SaaS admin panel with usage/costs; inbound agents
