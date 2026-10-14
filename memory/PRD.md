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

## Iteration 4 (2026-06) — Spain + Chile
- countries.py: ES/CL phone formats, timezone (Madrid/Santiago), STT language (es / es-419), speaking style, Zadarma line rate
- Business country (register + Telefonía) and per-agent country override; voices filtered by country (CL: Cartesia Latin premium Fernanda/Daniela/Regina/Eduardo/Mateo/Andrés + Azure es-CL Catalina/Lorenzo)
- Numbers per country in platform_settings.telephony.numbers.{ES,CL}; connect form per country; SUBTEL 600-prefix warning for Chile (user chose Zadarma +56 at own risk)
- Agenda slots interpreted in the agent's country timezone
- Admin costs: CLP for Chilean businesses, per-country line rate, USD→CLP rate, pricing advice and plans per country
- Chile bare national numbers only accepted starting with 9 or 2 (avoid misdialing Spanish numbers)

## Iteration 5 (2026-06) — SaaS
- saas.py: plans (minutes/month, price EUR/CLP, overage price), super admin users (plan, overage switch, suspend, delete with cascade, impersonate via "imp" cookie + stop), monthly quota check before every dial (pause + one email alert/month)
- Call templates (5 defaults: seguimiento, cobro, info, recordatorio, encuesta) + scheduled/immediate outbound calls per contact list in agent's country timezone; cron .emergent/crons.yml every 15 min → /api/cron/dispatch (WEBHOOK_CRON_SECRET)
- Agent tool request_support → support_tickets + email to account owner; appointment booked → email to owner and lead (if email)
- emailer.py: Emergent managed Resend (from_name "VozLeads"; sender address managed by platform, not notificaciones@vozleads.com)
- Public API: per-tenant API keys (sha256), GET /api/v1/agents, POST /api/v1/calls (type, consent, context, scheduled_at), GET /api/v1/calls/{id}; developer docs page /app/api
- Role-based UI: clients see Leads, Agentes, Llamadas salientes, Agenda, Asistencia, No llamar, API; admin also sees Super admin, Costes, Telefonía
- New professional light landing (VozLeads)

## Backlog
- P1: Stripe card on file + automatic overage billing; client-visible plan upgrade; verify vozleads.com domain for custom sender
- P1: Chile 600 number; legal calling hours; retries for no-answer
- P2: webhooks to client systems on call end; CRM integrations; inbound agents

## Backlog
- P1: Stripe plans + minute limits; auto-retries for no-answer; SMS/WhatsApp confirmation; Google Calendar; CSV campaigns
- P2: WhatsApp AI follow-up; human handoff; CRM/webhooks; SaaS admin panel with usage/costs; inbound agents

## Update — Oct 2026 (session 2)
- Geo pricing: Landing pricing section (auto EUR/CLP by timezone/locale + manual switch, persisted), super admin plan editor with price_eur/price_clp/overage per country, client usage badge in own currency. 3 sample plans seeded. (iteration_5 PASS)
- ElevenLabs voices via Vapi (eleven_turbo_v2_5, language es, Cartesia fallback), GPT-4.1, Deepgram nova-3 (ES), tuned start/stop speaking plans + Spanish acknowledgement phrases, more human prompt. Existing agents migrated to e_sarah/e_chris. Admin can add custom ElevenLabs voice IDs (native accents; needs ElevenLabs key in Vapi).
- Human handoff: tool request_human → support ticket kind=humano, email to business, red header alert + sidebar counter, /app/asistencia badge.
- Stripe subscriptions (billing.py): admin pastes secret key in Super admin (auto-creates webhook /api/billing/webhook); fallback shared test key. /app/plan "Mi plan": checkout (monthly, EUR or CLP by country), status polling, cancel at period end, billing portal (real key only). No automatic tax (Stripe only processes payment).
- Costs page: per-voice cost comparison (measured or estimated) and suggested price per minute ES/CL. (iteration_6 PASS, 101 backend tests)

## Backlog
- P1: Google Calendar sync; bulk CSV lead upload for campaigns; Stripe Tax/IVA
- P2: WhatsApp/SMS follow-ups; CRM integrations; inbound agents; live call transfer to human

## Update — session 2 (cont.)
- Bug fix: landing/agent voice preview was silent on iPhone (speechSynthesis blocked). Now backend voice_preview.py generates real voice (ElevenLabs with admin key from Super admin panel, fallback OpenAI TTS tts-1-hd via Emergent key) mixed server-side with ambience into one WAV; cached in object storage (tts_cache) + memory. Endpoints: GET /api/voice-preview/demo.wav (public), GET /api/voice-preview (auth), GET/PUT/DELETE /api/admin/elevenlabs. (iteration_7 PASS)
