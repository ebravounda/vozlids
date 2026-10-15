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

## Update — SEO landing (session 2)
- Marketing site rebuilt for sales + SEO (brand "VozLeads.com by GoRoky.com", domain https://vozleads.com): pages /, /es, /cl and keyword pages /telefonia-ip-con-inteligencia-artificial, /centralita-virtual-con-ia, /central-ip-con-inteligencia-artificial, /oficina-virtual-con-asistente-telefonico-ia, /llamadas-automaticas-con-ia, /privacidad. Content in frontend/src/seo/pages.json (positioning: user sells ONLY the AI agent, compatible with telefonía IP/central IP/oficina virtual).
- SEO: per-route title/description/canonical/hreflang/OG/JSON-LD (Organization, WebSite, SoftwareApplication, FAQPage, Breadcrumb) via components/Seo.jsx + seo/head.mjs; post-build static prerender scripts/seo-prerender.mjs (build = craco build && node scripts/seo-prerender.mjs); robots.txt, sitemap.xml (regen: node scripts/seo-prerender.mjs sitemap), og-image.jpg, logo.png, favicon.svg.
- "Solicita información ahora" form (hero + bottom + mobile sticky CTA): name + country ES/CL + phone. backend/landing.py POST /api/public/info-request → db.info_requests, email to owner, optional instant short call (max 45s, custom purpose/greeting, source web_vozleads) by agent configured in Super admin (GET/PUT /api/admin/landing, GET /api/admin/info-requests). Rate limit 3/IP/10min, same phone 24h = repetida. (iteration_8 PASS)
- Copy update: business (owner) provides the number + SIP via Zadarma; all plans "incluyen número de España (+34) o Chile (+56) gratis" (hero, trust bar, compat section, SEO pages, pricing cards, /app/plan). No text asks customers to bring their own SIP. (iteration_9 PASS)

## Update — Numbers, inbound receptionist, voicemail, native voices (session 2)
- zadarma.py (signed API client) + phone_numbers.py: on Stripe paid (live mode, or admin toggle buy_on_test) auto-buy number in Zadarma (direction/docs per country set in Super admin), create SIP with callerid, route inbound to number@sip.vapi.ai, create Vapi BYO credential (inbound enabled) + phone-number with server webhook. db.tenant_numbers. Release on subscription ended (autorenew off + delete Vapi resources). Admin: /api/admin/zadarma (GET/PUT/DELETE, options), /api/admin/numbers (+provision/release). Tenant: /api/my-number GET/PUT (choose inbound agent). Outbound dial uses tenant's own number when active.
- Inbound: Vapi assistant-request → receptionist assistant (objective "recepcion"), lead direction "entrante", status "atendida", caller_name from analysis.
- Voicemail: outbound voicemailDetection (vapi, audio) hangs up; prompt rule; status "buzon".
- ElevenLabs: key linked to Vapi as 11labs credential (needs User read permission); library search/add native-accent voices (needs Voices read/write). Current stored key only has TTS → user must create new key. Voice tuning stability .38/style .22/speed 1.02.
- NOT verified with real Zadarma (no API key yet): order/create_sip/route params & SIP login format need live verification. (iteration_10 PASS with simulated records)
- Bug fix: outbound templates had business_name hard-coded ("Clínica Dental Sonrisa"). Templates now use {nombre}/{agente}/{empresa} resolved from the calling agent (vapi.greeting); migration seed.migrate_templates; hint in Outbound template editor. (iteration_11 PASS)

## Update — Self-hosted deploy kit for Plesk (session 2)
- deploy/: docker-compose.yml (project "vozleads": mongo:7 own volume, backend :8710, frontend nginx :8711 both bound to 127.0.0.1, cron container POST /api/cron/dispatch every 15 min), .env.example, install.sh (generates secrets, decrypts data/env-secrets.enc, imports data/vozleads-config.json.enc via backend/tools/import_config.py), update.sh (backup + git pull + rebuild), backup.sh, plesk-nginx.conf (regex locations), README-PLESK.md.
- backend/Dockerfile, frontend/Dockerfile (+nginx.conf SPA fallback with prerendered SEO pages).
- Encrypted exports (AES-256, pbkdf2) passphrase stored only at /root/vl_pass.txt (NOT in repo) and given to user in chat.
- Not verifiable here (no Docker in preview): import script + install env-fill logic tested locally.
- frontend/yarn.lock is NOT pushed to GitHub by platform; Docker build uses frontend/yarn-lock.txt copy. After any yarn add: cp frontend/yarn.lock frontend/yarn-lock.txt
- Fix: pre-hydration flash (black screen + text) — prerendered markup now .seo-static (visually hidden), html.mk white bg on marketing paths until React mounts. (iteration_12)

## Update — Redesign light & pro (session 2)
- Light theme for whole app (index.css :root vars light, blue primary #2563EB, fonts Plus Jakarta Sans + DM Sans). Legacy dark Tailwind classes remapped under `.app-light` (DashboardLayout root). vl-* animations (wave, pulse, float, reveal, type).
- Landing hero redesigned: live-status eyebrow, CallStudio animated card (waveform + rotating transcript), scroll reveals; emerald→blue in landing components.
- Login/registro split-screen (tabs, dark showcase with waveform).
- Logo from user: /frontend/public/brand/vozleads-logo.png (+ -white). Logo component uses it.
- Provider names removed from public site + client panel (voice tier "Ultra natural HD"); only Super admin/Telefonía/Costes show providers. Generic VapiError/voice error texts.
- New tenant page /app/numero (Mi número).  (iteration_13 PASS)

## Update — Country-adaptive web + LatAm SEO (session 2)
- lib/geo.jsx: DEMO countries (ES, CL + 16 Spanish-speaking LatAm), GeoProvider (GET /api/public/geo = Cloudflare cf-ipcountry, fallback timezone), useMarket(pageCountry) → market ES|CL|INT, visitor flag, TXT per market.
- "/" adapts: ES visitors see /es content, CL see /cl, others international (EUR, visitor flag). /es only Spain, /cl only Chile (CLP). No currency switch on public site.
- Demo call: 15 s max (landing.MAX_SECONDS), short greeting, endCallPhrases ['hasta luego'] when max_seconds<=20; non ES/CL countries use ES landing agent (+34); cap 40 intl demos/day; countries.norm_demo_phone.
- SEO: 27 pages — 16 LatAm country pages (/mx, /ar, /co, /pe, /ec, /uy, /ve, /pa, /cr, /gt, /hn, /sv, /ni, /do, /bo, /py) + /call-center-con-ia, /central-telefonica-con-ia, /telefono-con-ia; hreflang es-XX for all; sitemap regenerated. (iteration_14; 2 minor fixes applied after)
- Fix inbound IVR (platform number): vapi.enable_inbound (Zadarma inbound IP gateways numeric + netmask, phone-number server URL), /api/admin/platform-inbound GET/PUT/DELETE, Telefonía panel "Contestar llamadas entrantes". Manual Zadarma step: route number to <number>@sip.vapi.ai (auto if Zadarma API key). NOTE: Vapi account shared preview/prod — whichever env presses "Activar" last receives inbound webhooks. (iteration_15)
- Agent no longer says "asistente virtual" (prompt rule + seed.migrate_ai_label).
- WARNING: never call PUT /api/admin/platform-inbound from preview (shared Vapi number; re-points inbound webhooks to preview). Inbound SIP URI now <number>@<credentialId>.sip.vapi.ai
- Inbound now via free Vapi SIP number sip:vozleads-34919932652@sip.vapi.ai (id dc43e89e…) — Zadarma must forward to vozleads-34919932652@sip.vapi.ai. (iteration_16)

## 2026-06 Ambientes realistas
- oficina_real: grabacion ARISTEIA + 2 teclados reales (Computer/Laptop), drive 3.0, tecleo mas presente
- call_center: grabacion real del usuario (Call_center_real.wav, 90s del min 60) sin filtro clean + teclado suave; voces sinteticas eliminadas
- URL de ambiente en Vapi versionada ?v=3 para forzar recarga

## 2026-06 Monitor Super Admin + Resend
- /app/monitor (AdminMonitor.jsx, MonitorParts.jsx, MonitorLogs.jsx): saldos en vivo (Zadarma balance, ElevenLabs caracteres, Vapi gasto mes + concurrencia, Stripe balance), llamadas en curso (poll 10s), margen por cliente (mes), registro de llamadas con desglose (/admin/costs ampliado), log facturado Zadarma (/v1/statistics, cache 60s)
- Alertas email (monitor.py loop cada 10 min, dedupe 6h; umbrales SIP 2 EUR, voces 2%; aviso instantaneo si Vapi rechaza por concurrencia o sin creditos). Coleccion monitor_alerts
- Vapi no tiene API de saldo de creditos: se muestra gasto del mes + enlace al dashboard; limite de concurrencia se guarda de subscriptionLimits al crear llamadas (platform_settings vapi_limits)
- Resend: platform_settings resend {api_key, from_email, reply_to}; emailer.deliver usa Resend si esta configurado, si no el envio integrado
- Tested iteration_17: 100%

## 2026-06 Landing por sectores + SEO
- 7 sectores x ES/CL = 14 paginas /es|cl/<slug> (type sector en src/seo/pages.json, generadas con /app/scripts/gen_sectors.py que tambien escribe backend/assets/sector_dialogs.json)
- Seccion Sectores en home/pais/topic (components/landing/Sectors.jsx) con foto, audio de llamada de ejemplo y enlace; pagina de sector con SectorHero + reproductor con transcripcion sincronizada
- Audio: sector_demo.py genera bajo demanda (voz nativa custom del pais -> fallback e_sarah/e_chris -> OpenAI), linea telefonica en cliente + ambiente oficina_real 30, mp3 guardado en Mongo sector_demos. DELETE /api/admin/sector-demos para regenerar
- SEO: hreflang ES/CL por sector, JSON-LD Service + AudioObject + Breadcrumb 3 niveles, og:image por sector, sitemap 42 urls
- Tested iteration_18: 100%

## 2026-06 Sectores extra + aviso repetida + legales
- +4 sectores (inmobiliarias [CL: corredoras de propiedades], talleres-mecanicos, gimnasios, academias) x ES/CL = 22 paginas de sector
- Formulario: limite 1 llamada/24h por numero se mantiene; si repetida -> nota pequena bajo el boton (solicitar-repeat-note), backend devuelve repeated:true
- Paginas legales /terminos /privacidad /cookies /aviso-legal (pages/Legal.jsx, COMPANY). Footer: VozLeads es parte del Grupo GoRoky, GoRoky LLC (EEUU, Espana, Chile), Raimundo Fernandez Villaverde 39 Madrid, soporte@goroky.com. Sin banner de cookies (solo tecnicas). Sitemap 53 urls
- Tested iteration_19: 100%

## 2026-06 Seguridad + Boton web + Alta de clientes
- Seguridad (iteration_20 OK): CORS sin credenciales con *, client_ip (cf-connecting-ip > x-real-ip > ultimo XFF), tope 20 llamadas demo/24h (limite_diario), cabeceras seguridad API + nginx (/f/ embebible), seed no resetea admin salvo ADMIN_RESET_PASSWORD=1, webhook Vapi solo cabecera x-vapi-secret, cookies SameSite=Lax
- Boton flotante (widget.py, assets/widget.js, /app/boton-web): script universal data-id, plugin WordPress zip, personalizacion texto/color/posicion/horario/saludo; PublicForm ?embed=1&color
- Alta (onboarding.py, SignupForm.jsx, Welcome.jsx, AdminOnboarding.jsx): registro con plan+datos fiscales (DNI/NIE/RUT validados)+direccion -> Stripe checkout signup -> /app/bienvenida; al pagar status pendiente + alerta admin (auto compra Zadarma solo si zadarma_api.auto_provision); admin asigna numero+SIP -> Vapi + email al cliente; bloquear/desbloquear; banner Aprovisionando linea; Mi numero con estado, copiar, quien contesta, escuchar voz
- Tested iteration_21 OK (pago Stripe completo y banner no probados end-to-end)

## 2026-06 Estadisticas del boton
- widget.js envia eventos view/open (POST /api/public/widget/{id}/event, text/plain, max 30/ip/dia); leads del iframe con source=widget
- Embudo vistas->pulsaciones->telefono->contestada->cita (GET /api/widget/stats?days, /api/admin/monitor/widget-stats) con grafico 7/30/90 (components/WidgetStats.jsx) en Boton para tu web y Monitor
- Self-tested curl + screenshot

## 2026-06 Stripe modo prueba
- platform_settings stripe: secret_key (real) + test_key opcional (si no, STRIPE_API_KEY emergent) + test_scope off|all|emails + test_emails
- billing.client(mode), mode_for(email); tx/user guardan stripe_mode; webhook verifica con ambos secretos; altas de prueba billing_test=True -> badge PRUEBA, no cuentan como ingreso
- UI en Super admin > Cobros con Stripe > Modo prueba
- Tested iteration_22 OK

## 2026-06 Emails + API v1 profesional (Fase 1)
- Emails: nuevo _wrap con logo (APP_PUBLIC_URL/brand/vozleads-logo.png), barra degradada, filas, CTA azul, pie legal GoRoky; send(..., intro, cta_label). Muestras enviadas a ed0.2580@gmail.com
- API v1: sub-app apiv1.py montada en /api/v1 (OpenAPI 3.1 /api/v1/docs), api_core.py. Claves vl_live_/vl_test_ (sha256), scopes, caducidad, IPs, ultimo uso, rotar (gracia 24h), desactivar. Rate limit Mongo por clave/min, llamadas/min, concurrencia y diario (solo live) con lock por tenant (1 proceso). Idempotency-Key (api_idem TTL 24h). POST /calls 202 asincrono, estados estandar + status_detail, programadas ISO8601 con zona, cancelar, listado paginado. Horario legal por pais (commercial/contractual). legal_basis + evidencia + finalidad. DNC por API. Webhooks HMAC (VozLeads-Signature t=,v1=) con reintentos backoff x8, SSRF, sandbox. Errores RFC 9457 con code/request_id; 402 mantenido. Worker cada 5s (programadas API, entregas webhooks, saas.dispatch_due).
- Portal /app/api (Developers.jsx + DevParts.jsx). Tested iteration_23 37/37
- Fase 2 pendiente: historial de peticiones por clave, export/supresion RGPD, retencion transcripciones, call.analysis.completed, lock distribuido si se escala a varios procesos, UI horario por pais

## 2026-06 API Fase 2: historial por clave + RGPD + retención
- privacy.py: api_request_logs (TTL 30 días, rutas con teléfonos enmascaradas) y GET /api/privacy/keys/{kid}/requests; botón "Historial" por clave en /app/api
- Scope privacy:manage: POST /v1/privacy/export, POST /v1/privacy/erase (borrado total: leads, citas, programadas, tickets, entregas webhook, caché idempotencia y llamada en proveedor; DNC se conserva), GET/PUT /v1/account/retention
- Panel /app/privacidad: plazo (Nunca/30/90/180/365), exportar/borrar por teléfono o email, registro sin PII (subject_ref hash); botones RGPD en ficha del lead
- Purga automática cada hora en api_core.worker (privacy.purge_expired): vacía messages/transcript/recording_url y marca transcript_purged_at
- Probado: iteration_24.json (backend 17/17, frontend OK; contraste y plurales corregidos)
- Siguiente: Fase 2 P1 carga masiva Excel/CSV, Google Calendar; P2 WhatsApp/SMS post-llamada, plugins CRM

