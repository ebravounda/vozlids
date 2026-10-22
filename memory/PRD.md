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

## 2026-06 Calendario de citas + minutos RGPD
- /app/agenda: calendario propio (semana por defecto, día en móvil, mes), arrastrar para mover, clic en hueco para crear, detalle con editar/cancelar/ver llamada; pestaña Horario
- Backend: GET /api/appointments?start&end, POST /api/appointments (manual), PATCH /api/appointments/{id}; Appointment.duration_minutes y source
- Borrado RGPD archiva consumo en usage_archive (sin PII); saas.minutes_used suma leads + usage_archive
- Probado: iteration_25.json

## 2026-06 Landing orientada a venta
- Nuevas secciones: PlatformTour (6 pestañas con maquetas del panel: leads, agenda, resultados, botón web, API, RGPD), FeatureGrid (16 funciones), Testimonials (Tramilex, IberoAcademy, GoRoky; fotos Unsplash), calculadora LostCalls
- CTA doble: "Llamada demo" (#solicitar) + "Empezar ahora" (/registro) en nav, hero, tour, calculadora, CTA final y barra móvil
- Probado: iteration_26.json (97%, mejoras menores aplicadas)
- Pendiente: que los clientes aprueben los textos de los testimonios

## 2026-06 Google Calendar + recordatorios + logos
- gcal.py: app OAuth en Super Admin (platform_settings google: client_id/secret; redirect {PUBLIC_BACKEND_URL}/api/oauth/calendar/callback). Cada cliente conecta su Google (users.google_calendar). Citas se crean/actualizan/borran en Google; eventos ocupados de Google bloquean huecos del agente (free_slots) y se ven en el calendario. PENDIENTE: el usuario debe pegar ID y secreto OAuth en Super Admin
- reminders.py: users.reminders {email, call, hours_before 24|3|1, call_from, call_to}; worker cada ~60 s; email con enlace /cita/{token} (confirmar/anular); llamada IA (gasta minutos) solo dentro de la ventana, si no se reintenta; PATCH de hora reinicia recordatorios
- Landing: LogoStrip (public/clients/*.webp) + logos en testimonios
- Probado: iteration_27.json (100%), mejoras menores aplicadas


## 2026-06 Despliegue Plesk: memoria y vuelta atrás
- update.sh: crea swap 4 GB si falta, compila backend y web por separado (web solo si cambió), progreso visible, timeout 25 min; guarda imágenes :previous + .previous_version antes de compilar
- rollback.sh: vuelve a las imágenes :previous y al commit anterior (solo programa, datos intactos); -y para no preguntar
- Dockerfile web: DISABLE_ESLINT_PLUGIN, NODE_OPTIONS max-old-space 1536

## 2026-06 Avisos de proveedores + consumo de voz
- monitor.py: provider_issues() (ElevenLabs <20%, Zadarma < sip_min, Vapi saldo anotado - gasto real < ai_min_usd, concurrencia) -> GET /admin/monitor/provider-alerts; banner ProviderAlerts en Super Admin y Monitor
- Vapi sin API de saldo: PUT /admin/monitor/vapi-credit {amount}; resta coste de llamadas Vapi desde set_at; email 1/día
- GET /admin/monitor/voice-usage: caracteres dichos por el agente por cliente este mes, % y por minuto (panel VoiceUsage)

## 2026-06 Planes: recomendado, promociones y límites
- PlanIn: recommended (único), promo_active/label/price_eur/price_clp/months (Stripe coupon repeating; en proxy test se cobra unit_amount rebajado), limits {max_agents,max_concurrent,recording_days,outbound,api,widget,agenda_pro,premium_voices,ambience}
- plan_limits.py: for_tenant/require/has/concurrency_error/check_agent/effective_agent (degrada voz HD y ambiente en llamada si el plan ya no lo incluye); admin = sin límites; planes sin limits = todo permitido
- Enforcement: agents, /keys + /v1 (403 plan_feature_missing), widget, gcal/reminders, scheduled-calls (espera si concurrencia llena), privacy retention cap, quota_error incluye concurrencia
- usage_alerts: email 80% y 100% una vez al mes; /account/usage devuelve limits/agents/is_admin
- Frontend: PlanGate.jsx (Gate, LockedCard, UsageMeter sidebar, UsageBanner, AdminTabs), PlanPrice.jsx (precio tachado, badges, limitLines). Sidebar admin: un solo item Super admin + pestañas
- Probado iteration_28 (backend 17/17); arreglos posteriores: voz por defecto según plan, botón Crear agente al límite, plural, contraste Mi plan, doble badge, 404 plan

## 2026-06 Cambio de plan en un clic
- billing.py: POST /billing/change-plan/preview, POST /billing/change-plan (subir: subscriptions.update proration always_invoice + error_if_incomplete, plan al instante; bajar: proration none, pending_plan_id/at aplicado en invoice.paid subscription_cycle o worker apply_pending_downgrades), DELETE /billing/change-plan (anular bajada). Proxy Stripe compartido no soporta subscriptions -> 409 con mensaje
- Frontend: components/ChangePlan.jsx (ChangePlanDialog, useNextPlan); UsageBanner abre diálogo con el siguiente plan; Mi plan: Subir/Bajar a este plan + aviso de cambio programado
- Probado con cliente Stripe simulado (python) + captura UI; flujo real con Stripe NO probado en preview

## 2026-06 Editar datos de negocio (super admin)
- saas.py GET/PUT /admin/users/{uid}/profile (business_name, name, email único, contact_phone normalizado, sector, website, business_hours); actualiza Stripe customer (name/email/phone) si hay stripe_customer_id y clave propia
- components/AdminBusinessEdit.jsx: botón Editar en cada cuenta de Super admin
- billing: aviso uses_shared_test_key en Super Admin Stripe + mensaje claro si la clave compartida devuelve 403 en servidor propio

## 2026-06 Llamadas en directo + bloqueos
- security_admin.py: blocklist (phone dígitos/email/domain, expires_at para auto 24h), DISPOSABLE emails, guard_public (formularios/widget/demo + auto-bloqueo >5/h), blocked_email en registro, blocked_phone en dial (saliente) y assistant_request (entrante -> {error})
- Live: GET /admin/monitor/live con can_listen/can_hangup; GET /admin/monitor/calls/{id}/listen (listenUrl), POST .../hangup (controlUrl end-call); vapi.build_assistant monitorPlan listen/control
- Frontend: components/LiveCalls.jsx (escucha PCM s16le 16k vía WebSocket + Web Audio, auto mono/estéreo), components/Blocklist.jsx en Monitor
- Escucha/colgar NO probados con una llamada real (no había llamadas activas en preview)
- Alerta de fraude: fraud_alert() envía email (monitor.notify kind fraud:{num}, 1 por número/24h) con hasta 12 intentos (hora, origen, negocio, nombre, email, IP)
- Bloqueo IP: kind ip en blocklist, guard_public(ip) en formularios/demo/registro; fraud_alert guarda ips en el bloqueo y el email lleva botón a /app/monitor?block_ip=...&reason=... (confirmación en panel). Botones "Bloquear IP" en filas automáticas
- Live control: POST /admin/monitor/calls/{id}/say {message} (controlUrl say) y /transfer {number} (+34 si 9 dígitos); UI en LiveCalls al escuchar. NO probado con llamada real
- Bloqueo por país: platform_settings country_block {countries, blocked_total}; GET/PUT /admin/country-block (ES/CL no bloqueables); guard_public comprueba prefijo (phonenumbers) e IP (cf-ipcountry o ipwho.is cacheado 30 días en ip_geo). UI components/CountryBlock.jsx en Monitor

## 2026-06 Fix llamada muda (saliente)
- Causa: grabaciones estéreo muestran canal cliente en silencio digital ~10 s tras "answered" (la línea marca contestada mientras aún suena) -> el saludo se decía a nadie. 15-oct mañana además ElevenLabs free agotado (voice chars 0)
- vapi.build_assistant saliente: firstMessageMode assistant-waits-for-user + messagePlan idleMessages "¿Hola? Soy X, de Y. ¿Me escuchas bien?" a los 5 s (máx 2). Entrantes sin cambios. Validado creando asistente en Vapi (201)

## 2026-06 Confirmar nombre + llamadas mudas
- vapi: confirm_name(lead) (excluye nombres genéricos/demos <=20 s); saliente firstMessage "Hola, ¿hablo con X?", idle "¿Hola? ¿Hablo con X?", prompt INICIO DE LA LLAMADA con saludo sin "Hola" (GREET_RE)
- monitor.check_silent en end-of-call-report: conectada >=4 s sin mensajes del cliente (excluye no contesta/ocupado/buzón/errores) -> db.silent_calls + notify silent_call (1/h); GET /admin/monitor/silent; provider-alerts añade kind silent si >=2 en 1 h; GET /admin/monitor/calls/{id}/recording (admin)
- UI components/SilentCalls.jsx en Monitor (escuchar grabación)

## 2026-06 — Rellamadas automáticas ("llámame más tarde")
- Herramienta Vapi `schedule_callback` (solo salientes): hora que diga el cliente o +2h; ventana L-V 9:00-21:00 (hora local del agente); máx. 2 rellamadas por contacto; si se vuelve a pedir en la misma llamada se reprograma (no duplica).
- Crea un lead `programada` con `run_at` (lo marca el worker existente), `callback_of`, `callback_count`, `callback_at`. Lead original → estado `rellamada` ("Pidió rellamada").
- Agenda: rellamadas en ámbar (GET/PATCH/DELETE /api/callbacks), mover arrastrando, cambiar hora o cancelar. DNC cancela/bloquea la rellamada.
- Archivos: backend/callbacks.py, services.py, vapi.py, models.py; frontend calendar/CallbackDetail.jsx y relacionados. Testeado: iteration_29 (100%).

## 2026-06 — Vista previa de voces y naturalidad
- Vista previa real por tipo de voz: HD → ElevenLabs (admin key), Premium → Cartesia sonic-3 (env CARTESIA_API_KEY), Estándar → voces Azure Neural vía edge-tts (sin clave). Antes Premium/Estándar sonaban con OpenAI (otra voz).
- Mezcla de vista previa con filtro telefónico (250–3600 Hz + compresión ligera) para que suene a llamada real.
- ElevenLabs: modelo eleven_flash_v2_5 (mismo coste que turbo), stability 0.32, style 0.15, speed 0.98, chunkPlan minCharacters 40. Prompt con estilo hablado coloquial.
- Fondos: todos con grabaciones reales; teclados a ratos (bursts) + tono de sala; call_center = 3 min de la grabación del usuario sin capas extra; bucles con fundido (ambience v=6).
- Clave Cartesia: se conecta en Super Admin → panel "Cartesia" (platform_settings _id=cartesia; env CARTESIA_API_KEY solo como respaldo opcional). Endpoints GET/PUT/DELETE /api/admin/cartesia (PUT valida la clave contra Cartesia).

## 2026-06 — Recepcionista: saludo sin pisar al cliente
- Entrantes: firstMessageInterruptionsEnabled=true (el cliente puede cortar el saludo) + pausa de 1 s antes del saludo (<break time="1s"/>; 11labs con enableSsmlParsing, Cartesia nativo; Azure sin pausa). Tags eliminados del transcript (services._messages). Validado contra la API de Vapi (201).

## 2026-06 — Agente solo habla del negocio
- system_prompt: bloque "TEMAS PERMITIDOS" (prioridad máxima) + recordatorio final: rechaza temas ajenos, cuelga tras 2 insistencias, ignora prompt-injection. Verificado con gpt-4.1 (puré de patatas / "olvida tus instrucciones" → rechazo).
- Campo "Información del negocio" (product) ampliado a 8000 caracteres con contador y ayuda.

## 2026-06 — Voces Cartesia nuevas + costes reales y beneficio
- +9 voces Premium castellano (p_blanca, p_eva, p_lara, p_alicia, p_maite, p_lucia, p_octavio, p_rafael, p_dario) y +4 LATAM (l_catalina "Valeria", l_veronica, l_rodrigo, l_santiago) elegidas de la API de Cartesia (acento nativo es-ES / es-MX/CO).
- costs_real.py: coste real Zadarma por llamada (/v1/statistics billcost, match por número ±10 min, hora Madrid, sync cada 10 min o botón), coste ElevenLabs propio = ttsCharacters × créditos/letra × precio plan, uso ElevenLabs (/v1/user/subscription), ingresos por suscripción activa (excluye billing_test), números por cliente, comisión Stripe.
- /api/admin/costs: profit {revenue, variable, per_client_fixed, fixed, net, margin_pct}, fixed (editable + "ElevenLabs parte sin usar" automática), tenants con beneficio/margen; filtro tenant_id excluye fijos. Pricing: eleven_plan_usd/credits/credits_per_char, number_es/cl_usd_month, stripe_pct/fixed_eur, fixed_costs[].
- UI AdminCosts: Beneficio real, desglose, editor de costes fijos, Beneficio por cliente, etiqueta real/est. en línea. iteration_30: 100%.

## 2026-06 — Audio "Escuchar una llamada real" del landing
- Antes: e_sarah (voz ElevenLabs americana) leyendo un saludo → sonaba "gringa robot".
- Ahora: llamada de 2 voces nativas de España (Cartesia Blanca = agente, Alicia = clienta), con pausas naturales, fondo oficina_real y sonido telefónico. Archivo estático backend/assets/demo/demo_call.wav (~50 s), generado con tools/make_demo_call.py; /api/voice-preview/demo.wav lo sirve sin depender de claves en producción. Verificado con Whisper (transcripción correcta).
- Demos por sector: voces de respaldo ahora Cartesia nativas (ES p_blanca/p_octavio, CL l_veronica/l_rodrigo) tras las voces propias; VERSION=2 regenera automáticamente las cacheadas.

## 2026-06 — Multi-ejecutivo en rotación
- Agent.executives [{voice, name}] (máx 5, voces distintas, del país del agente, gating HD por plan). services.pick_executive rota por turnos con contador atómico agents.exec_turn; se aplica a salientes (dial, también rellamadas → siguiente en la rotación) y entrantes (assistant_request). Prompt, voz y saludo usan el ejecutivo; el saludo sustituye el nombre del agente / otros ejecutivos por el del que llama. Lead.executive guardado y mostrado en LeadDetail.
- UI: ExecutivesPanel en pestaña Voz (activar, añadir, renombrar, quitar). Cambiar país vacía la rotación. iteration_31 + fix del saludo.

## 2026-06 — Landing: nuevas funciones, citas, equipo de voces, menú móvil
- Highlights.jsx: secciones #citas (OnlineBooking, "Citas en línea 24/7") y #voces (AgentTeam, voces 100% realistas España/Latam, rotación de ejecutivos, botón demo).
- Features: 20 funciones (nuevas: voces 100% realistas, equipo de ejecutivos, citas en línea, rellamadas, escucha en directo, solo habla de tu negocio) + bloque "Próximamente" con 11 ideas (WhatsApp, memoria, resumen al oído, voz clonada, informe semanal, llamadas perdidas, campañas calendario, Excel, CRM, mejora automática, multi-idioma).
- Menú móvil (Sheet) visible < 1280px; Nav home prop para páginas legales (/#ancla). Hero checklist actualizado. iteration_32: 97% + fixes.

## 2026-06 — Documentación pública de la API
- Revisión: /api/v1/docs y openapi.json solo exponen los 15 endpoints públicos (19 operaciones) con X-API-Key; sin claves, emails, IPs ni rutas internas. Swagger se mantiene como "Probar en vivo".
- Endurecido: FastAPI interno (server.py) sin docs/redoc/openapi (docs_url=None…), antes accesible en :8001/docs.
- Nueva página pública /desarrolladores (pages/ApiDocs.jsx + components/apidocs/*): hero, guías (inicio rápido cURL/Python/Node, autenticación, webhooks con payload real y verificación HMAC, errores/límites) y referencia generada desde openapi.json. Enlaces: nav "API", menú móvil, footer, botón en bloque API del landing.

## 2026-06 — Revisión llamada demo del landing
- Fix: la frase de "¿me escuchas?" usaba el nombre del negocio del agente (p. ej. OpenFactura.es) → la demo fuerza business_name "VozLeads".
- Fix: duración máx. demo 15 → 20 s (el saludo dura ~10 s + espera al "¿Diga?"; se cortaba).
- Fix: email de solicitud decía "Sí, en curso" aunque no se llamara (tope, sin agente, no_llamar) → CALL_LABELS con el motivo real.
- Validado payload contra Vapi (201). Preview sin agente demo configurado (Super Admin → Landing) → "sin_agente".
- Demo web (v2): vapi.is_demo(lead) (source web_vozleads) → habla primero tras 1 s (<break>), no interrumpible, sin detección de buzón, mensaje "Hola {nombre}, te estoy llamando de VozLeads. Esta es una llamada demostrativa…¡Hasta luego!" y cuelga (endCallPhrases); máx 25 s. Las demos no cuentan como "llamadas mudas". Validado contra Vapi (201).

## 2026-06 — Recordatorios al dueño + calendario moderno
- reminders.owner_reminders() (worker cada ~60 s): email "En 1 hora: cita con X" (appointments.owner_hour_at, se resetea al mover la cita) y resumen diario "Tu agenda de hoy" entre 8:00–12:00 hora local (users.agenda_digest_day). Todas las citas (agente y manuales), excluye ejemplos. Si el envío falla, se reintenta. Ya existía el email al agendar (saas.notify_appointment).
- Calendario "Claro y limpio" (design_guidelines.json): toolbar en tarjeta, eventos con borde izquierdo de color y etiqueta de tipo, fuera de horario gris suave, línea "ahora" con punto, mes con chips de color y contador, leyenda en tarjeta, panel "Próximas citas de hoy" (xl), citas solapadas lado a lado, tabs sin desbordar en móvil. iteration_33 + fixes.

## 2026-06 — Demo: número del dueño sin límites + voz Jessica
- security_admin.OWNER_PHONES = {"34600850506"}: nunca bloqueado (blocked_phone/guard_public), sin límite por IP, sin "repetida", sin topes diarios/internacionales; info_requests.owner_test=True (no cuenta en topes ni envía email de solicitud).
- Demo web: landing.demo_voice(phone): +34 → voz propia ElevenLabs ES de mujer (Carolina primero; si no hay, p_blanca); resto (Chile, LATAM, otros) → e_jessica. Sin rotación de ejecutivos; keep_voice evita la bajada por plan.

## 2026-06 — Un número por agente (sucursal/empresa)
- extra_numbers.py: tenant_numbers con extra=True + agent_id + stripe_item_id. Precio 10 €/mes (ES) y 13.000 CLP/mes (CL), añadido como subscription item de Stripe (metadata kind=extra_number, prorrateo always_invoice; producto "Número adicional VozLeads" cacheado en platform_settings.stripe). Activación: auto si Zadarma auto_provision+API key; si no, "pendiente_aprobacion" + email al admin → Super Admin "Números adicionales por aprobar" (approve → provision). Baja: libera Zadarma/Vapi y quita el item sin prorrateo. Borrar agente → número queda libre (agent_id=None, sigue cobrándose).
- phone_numbers: PRIMARY filter, provision/release(user_id, num_id), phone_id_for(tenant, country, agent_id) → saliente desde el número del agente; entrante en número extra → su agente (o recepcionista del principal si está libre). billing change-plan ignora items de números; cancelación libera también los extra. onboarding/admin lists solo número principal. Costes: fee por cada número + ingresos de números extra.
- UI: AgentNumbers (Mi número y Telefonía), PendingExtraNumbers (Super Admin). iteration_34: 100% + fixes de revisión.

## 2026-06 · SuperAdmin approval of extra numbers made more visible
- Amber banner at the top of Super admin showing the count of pending numbers (click scrolls to the panel)
- "Números adicionales por aprobar" panel always visible (empty-state text), shows agent + date
- New POST /api/admin/numbers/extra/{id}/reject: cancels the Stripe item (credit on next invoice) + email to the customer

## 2026-06 · Landing: varios números + "¿Tienes dudas? Llámanos"
- New section "Agrega todos los números que desees para tu empresa" (#numeros, after Voces; no price): Recepción / Atención al cliente / Ventas / Soporte técnico
- "¿Tienes dudas? Llámanos" box before the final CTA + "¿Dudas? Llámanos" button in the top menu (popover) and in the mobile menu
- Central lines in Chrome.jsx CENTRALES: Chile +56233844477, España +34919932652 (tel: links)

## 2026-06 · Todas las voces + atención multi-idioma (iteration_35 PASS 19/19)
- Voices: every Spanish voice is available to every agent regardless of country (España/Latino/Chileno/Neutro HD + custom) with an accent label and accent filter chips; executives rotation lists every voice/tier. Changing country no longer resets voices. premium_voices gating removed (all plans include all voices).
- Plan feature `multilang` (Super admin → plan, default off). Agent field `languages: [{lang, voice, name}]` (en, pt, fr, ca, it, de). Without the feature, languages are silently removed on save and ignored at call time.
- Call flow: the Spanish assistant asks for the language (inbound greeting / prompt), transcriber deepgram nova-3 "multi"; handoff tool `cambiar_idioma` (dynamic) → webhook `handoff-destination-request` → services.language_handoff returns a transient native assistant (languages.py: greeting, style, STT; Azure native voices LANG_VOICES or ElevenLabs HD with language=lang; Catalan Azure only). lead.language saved.
- Custom voices: language + accent fields; ElevenLabs library search by language + accent (Argentino, Mexicano, Colombiano, Peruano, Venezolano, Americano, Británico, Brasileño…).
- Voice preview supports ?lang=.
- NOT verified with a real Vapi call (preview Vapi key is 401): handoff tool schema accepted only via docs.

## 2026-06 · Idioma en leads + Memoria de llamadas (iteration_36 PASS)
- Lead.language (set on handoff) + memory_calls. GET /api/leads?language=es|en|… filter; Leads table "Idioma" column with flag (LangFlag.jsx; ES/CL by phone prefix, Catalan CSS flag); LeadDetail shows language + "El agente recordó N llamadas anteriores".
- Agent.memory (switch in tab Guion, default on). services.attach_history: last 3 leads of the same tenant + phone with a summary → vapi.memory_block in system prompt (dates, outcome, summary, known name; mention naturally). Applied to outbound dial, inbound assistant-request and language handoff. Skipped for demo/test calls.

## 2026-06 · KYC: titular de cada línea (iteration_37 PASS 20/20)
- kyc.py: client fills data (persona/empresa, ID type per country ES: DNI/NIE/PASSPORT, CL: NATIONAL_ID_CARD/PASSPORT, address, contact) and uploads photos (id_front/id_back or passport; company_cert for empresa) to object storage (client-side shrink to 1800px JPEG). Legal notice per country (ES Ley 11/2022, CL Ley 18.168/Subtel; orientative text). Submit → pendiente → admin email.
- Super admin "Documentos de los titulares" (AdminKyc.jsx): view data + images, Approve → Zadarma documents group create + upload (only required files) → enviado_zadarma; Reject with reason → client email; "Comprobar en Zadarma" (groups/valid) → verificado.
- Clients with an active line get 30-day deadline + banner (line keeps working). provision() for non-admin tenants without approved KYC → status pendiente_documentos (no purchase); approving KYC auto-provisions waiting numbers using the client's group.
- Docs kept in VozLeads (admin + owner only); kyc deleted with account. Gateway errors now use 424 instead of 502 (ingress replaced 502 bodies).
- Pending: WhatsApp follow-up after calls (explained to user: Meta WhatsApp Cloud API or Twilio, templates required).

## 2026-06 · Tutorial de bienvenida (onboarding tour)
- components/Tour.jsx: 10-step spotlight tour over the real sidebar (welcome, agentes, mi número [1–24 h + KYC note], leads, agenda, salientes, botón web, asistencia, plan, final CTA → /app/agentes/nuevo). Arrows/Esc keys, progress dots, centered cards on mobile.
- Auto-opens only for users registered after this release (users.tour_done False on register; user_out.tour_pending). Closing → POST /api/account/tour-done. Not auto-opened while impersonating. "Ver tutorial" button in sidebar + mobile nav reopens it.
- KYC: panel always shown to clients; admin sees an explanatory note in Mi número.

## 2026-06 · Email de bienvenida
- server.welcome_email (fire-and-forget on /auth/register): 5 steps (documentos según país, número 1–24 h, crear agente, llamadas, dudas + centrales CL/ES), CTA "Subir mis documentos" → /app/numero. Verified 202 from email API.

## 2026-06 · Landing: sección multi-idioma
- components/landing/Multilang.jsx (#idiomas, after Voces, nav link "Idiomas"): copy about native executives per language, 15 accent chips, interactive call mock with 6 language tabs (auto-rotates; click stops) showing ask → reply → handoff → native greeting. AgentTeam copy mentions accents + languages.

## 2026-06 · Escuchar cada idioma + catalán HD
- Landing Multilang demo: "Escuchar" button plays a mini call (Marta question es-ES → customer → native exec) from static files /frontend/public/demo/lang/{q,c,r}_{lang}.mp3 (generated once with edge-tts, free; no credits per play). Speaking bubble highlighted; tab change stops audio. English exec renamed Jenny.
- Catalan HD: languages.ELEVEN_LANGS includes "ca"; ELEVEN_MODEL {"ca": "eleven_v4_turbo"} (Vapi supports it; preview verified via ElevenLabs API; NOT verified in a live call). Super admin custom voices + library search accept Catalán.
- 2026-06: demo re-recorded with real call voices: Marta = Cartesia Premium p_marta (q_*.wav), customer + native exec = ElevenLabs HD with language code (c_/r_*.mp3; Catalan via eleven_v4_turbo). Script /tmp/hd.py pattern: voice_preview.tts(voice, text, lang). One-time cost, static files.

## 2026-06 · Conectar números existentes de Zadarma
- connect_numbers.py: GET /api/admin/zadarma/my-numbers (Zadarma /v1/direct_numbers/, marks used_by), GET /api/admin/zadarma/connect-options/{tid} (kyc_ok, has_main, agents, price), POST /api/admin/zadarma/connect {number, tenant_id, agent_id?} → KYC required (409), main line or per-agent extra (charged), phone_numbers.activate() creates SIP + Vapi + routes inbound. source="zadarma_existente" → release does not turn off Zadarma autorenew (number returns to stock).
- Extra numbers now charge FULL first month at once (invoice + pay) instead of proration; subscription item with proration none; reject credits full amount to the customer balance. NOT verified against real Stripe (preview uses proxy).
- UI: components/numbers/ConnectExisting.jsx inside Super admin → Zadarma panel ("Conectar números de mi Zadarma").
- SIP: no need to buy SIP lines; one internal Zadarma SIP is created per number via API.
- 2026-06: "Número activo" celebration email (phone_numbers.activate): subject "¡Enhorabuena! Tu número X ya está activo", rows (número, quién contesta, pruébalo ahora, salientes, siguiente paso), CTA "Probar mi agente" → /app/agentes/{agent}?tab=test (AgentBuilder reads ?tab=).

## 2026-06 · Separar cuenta admin / cuenta de llamadas
- POST /api/admin/split-account {email} (one-time, Super admin panel "Separar tu cuenta…", email prefilled ed0.2580@gmail.com): creates role=business user (same password hash, copied business fields, split_from_admin) and moves every collection's tenant_id from admin → client (except users/platform_settings/plans/login_attempts/oauth_states/ip_geo/tts_cache/api_rate). Admin gets admin_only + client_id, business_name "Administración VozLeads"; seed skips sample data for admin_only.
- Frontend: admin_only → nav only Super admin, /app redirects to /app/admin, no tutorial/usage meter; "Mi cuenta de llamadas" button (impersonate client_id); "Volver a mi cuenta" via existing impersonation bar. Users list marks "tu cuenta de llamadas".
- minutes_used excludes landing demo leads (source web_vozleads).
- Preview admin NOT split (test creds unchanged). Production: user must press the button after updating.
- 2026-06 fix: connect existing numbers — /my-numbers now returns {hidden, numbers} with ONLY usable numbers (Zadarma status not off/blocked/expired, stop_date not past, not used by any VozLeads record); connect re-validates. connect-options returns current active numbers, can_charge (Stripe sub active), agents without own number. ConnectIn.charge: admin-assigned plans (no Stripe) connect without charge (billing "manual") instead of failing "Necesitas un plan activo".
- 2026-06 fix: Zadarma SIP limit ("You cannot register more than 3 numbers" = sip/create limit, grows with Zadarma balance; GET /v1/sip/ returns `left`). activate() now: create SIP → on limit reuse a free "VozLeads…" SIP (PUT /v1/sip/<id>/password/ + /v1/sip/callerid/), never the user's own lines; step-labelled errors. connect pre-checks SIP room before charging; on failure undoes record + charge so the number stays available. Panel shows "Líneas SIP: X creadas · puedes crear Y más · Z reutilizables".
- 2026-06: Número por país — services.dial picks the caller number by the LEAD's phone country (+34→ES, +56→CL; else agent country): agent's own number in that country → account main number in that country → any active account number in that country → platform number. phone_numbers.num_country() derives country from the number itself (record country may be billing country). today_text uses that country.
- 2026-06: Connect dialog lets admin pick "Crear una línea SIP nueva" or "Usar mi línea SIP <id>" (any Zadarma SIP not used by VozLeads; password is reset — warning shown). ConnectIn.sip_id; activate(..., sip_id) uses Z.reuse_sip. my-numbers returns sip_list.

## 2026-06 · Super admin «Líneas» (/app/lineas)
- backend/lines.py (/api/admin/lines): GET table (every Zadarma number: free/inactive/connected, owner, role main|agent|platform, agent, SIP, checks entrantes/salientes/documentos, errors; sips with used_by; orphans), GET /options (owners+agents+kyc+can_charge, platform_tenant = admin.client_id or admin), POST /connect {number, tenant_id, role, agent_id, sip_id ("new"|id, required), charge}, POST /{n}/agent, /{n}/reconfigure {sip_id}, /reconfigure-all (uses each record's current SIP; skips ones without), /{n}/move, /{n}/disconnect. Platform role updates vapi.STATE numbers + platform_settings.telephony.numbers.
- PRIMARY now excludes platform records. Old "Conectar números de mi Zadarma" panel replaced by link to Líneas.
- Mock test script: backend/tests/manual_lines_mock.py (run with PYTHONPATH=backend). Not verified against real Zadarma/Vapi.
- 2026-06: Líneas extras — POST /api/admin/lines/{n}/test {phone} (line's agent calls you FROM that number; lead source prueba_linea, via_phone_id honored by services.dial); linehealth.py loop every 30 min (+ POST /api/admin/lines/health-check "Revisar ahora"): Zadarma number present/active, SIP exists, Vapi phone-number exists → tenant_numbers.health caida/ok + emails admin on down and on recovery (only on transitions; provider errors skip). Leads: line_number stored on outbound (dial) and inbound (assistant_request); Leads table "Línea" column with 🇪🇸/🇨🇱 flag (LineFlag in LangFlag.jsx). Mock script backend/tests/manual_linehealth_mock.py.
- 2026-06 fix (iteration_38 PASS): SIP selector lists ALL Zadarma SIP lines (used ones disabled "en uso por +…", current "(la actual)"); new collapsible "Tus líneas SIP en Zadarma (N)" list on Líneas page.
- 2026-06 fix: Zadarma SIP passwords now letters+digits only (Z.new_password, 16 chars) — token_urlsafe produced -/_ which Zadarma rejects.

## 2026-06 · Super admin menú lateral + Pagos + lectura de web con IA (iteration_39 PASS)
- Sidebar group "Administración" (ADMIN_TABS exported from PlanGate: Cuentas y planes, Pagos, Monitor, Costes, Líneas, Telefonía); top AdminTabs removed; nav items compact; tutorial button hidden for admin.
- payments.py (/api/admin/payments): Stripe invoices live+test (pagada/pendiente/vencida/impagada), accounts with subscription status + renewal date (current_period_end, item-level fallback), totals; POST /invoices/{id}/pay?mode= (charge now), POST /send-link {user_id, plan_id} (billing.checkout session emailed). Proxy Stripe (preview) → friendly warning. UI pages/dashboard/AdminPayments.jsx (/app/pagos).
- Provisioning banner for clients (sin_numero/pendiente/comprando/error/pendiente_documentos): "Estamos a la espera de asignación de numeración. Puede demorar de 2 a 24 horas. Tu suscripción comienza cuando tu numeración está activa." Same text in tour + welcome email. Billing unchanged (user chose to keep current billing).
- webscan.py: super admin OpenAI key (PUT/GET/DELETE /api/admin/openai, validated; platform_settings._id=openai), POST /api/agents/scan-website {url} → reads homepage + up to 4 same-domain key pages (SSRF guard: public IPs only), gpt-5.4-mini via emergentintegrations LlmChat with the admin's key, Spanish summary; 2 scans/day per tenant (db.web_scans), admin exempt. UI components/agent/WebScan.jsx (review/edit → append to product), components/admin/OpenAISettings.jsx in Cuentas y planes.
- Testing agent fixed monitor.py margins _parts() missing pricing arg (500 on Monitor).
- 2026-06: daily_jobs.py (loop every 6 h): payment_reminders → email 3 days before each active Stripe renewal (once per period: users.reminded_period_end); refresh_websites → agents with website re-read every 30 days (gpt-5.4-mini diff vs web_summary; "SIN CAMBIOS" ignored) → agent.web_suggestion + email; POST /api/agents/{id}/web-suggestion/apply|dismiss. Agent fields website, web_summary (saved when adding a scan), web_suggestion. invoice.payment_failed email improved (amount, reason, next attempt, "Actualizar mi tarjeta"). Mock: backend/tests/manual_daily_jobs_mock.py.

## 2026-06 Web scan: bot-protection message
- webscan.read_site now detects Cloudflare/anti-bot challenges (403/429/503 + cf headers/challenge page) and returns a clear message telling the owner to disable Under Attack mode or allow "VozLeadsBot". Also specific messages for timeout and HTTP errors. Failed reads do not consume daily quota. (User chose: only show error, no manual paste fallback.)

## 2026-06 Per-agent receptionist on own number
- Agent fields: address, hours, notify_email, receptionist, reception_book, reception_message, transfer_number (E.164).
- Inbound on an extra (own) number: receptionist ON -> reception objective (book / take message / transferCall to transfer_number); OFF -> agent own objective. Main number always receptionist. Lead doc gets `reception` flag in phone_numbers.assistant_request.
- Emails for appointments/request_human go to agent.notify_email if set, else owner.
- UI: components/agent/Reception.jsx in GeneralTab (toggle only shown if agent has own number). Tested iteration_40 (100%).
- Fix: Reception panel now also shows for agents on the MAIN number (inbound_agent_id); main number has no on/off toggle (always receptionist) but has book/message/transfer options.
- Debug note: +34919939915 inbound "not found" is a Zadarma-side issue (all destinations fail; config VozLeads/Vapi identical to working numbers). User to open Zadarma ticket.

## 2026-10-22 Inbound routing fix (Vapi "number not found")
- Root cause: every per-number byo-sip-trunk credential had the same Zadarma inbound IPs; Vapi picked ONE credential (Chile 56233844477) for all Zadarma INVITEs, so other numbers got 404 "number not found".
- Fix: per-number credentials are now OUTBOUND-only (OUTBOUND_GATEWAYS). One shared credential "VozLeads Entrante Zadarma" holds Zadarma inbound IPs; each number gets a 2nd byo-phone-number on it (inbound_phone_number_id, inbound_uri). Zadarma routes to NUM@<sharedCred>.sip.vapi.ai. Vapi allows same number on 2 credentials (verified).
- Migration: Super admin > Líneas > "Reparar llamadas entrantes" (POST /api/admin/lines/repair-inbound): isolate_inbound() + connect_inbound() + Zadarma route for every active number; deletes legacy vapi-provider sip:vozleads-* numbers.
- WARNING: preview and production share the SAME Vapi org. Never run repair/isolate from preview.
- 2026-10-22 later: shared cred gateways expanded (185.45.152-155/24 + exact Zadarma hosts). Spanish numbers still 404 by plain digits even on shared cred; routing 919939915 to the Chile URI worked => Vapi lookup by plain Spanish digits fails (likely registered elsewhere in Vapi). Fix: inbound record uses alias "00"+digits (vapi.inbound_alias), Zadarma routes to 00<digits>@<sharedCred>.sip.vapi.ai. repair_inbound deletes non-00 records in shared cred + legacy vozleads- SIP numbers.
- CONFIRMED 2026-10-22: alias 0034919939915 on shared cred -> Laura answers. LESSON: Vapi objects created from PREVIEW get preview webhook URL/secret (server_cfg). Never create/patch phone numbers from preview; always run on the Plesk server (docker compose exec backend).
- Pending for user: Save to Github + update.sh + "Reparar llamadas entrantes" to move all 4 numbers to 00-alias.

## 2026-10-22 Monitor de Vapi + transfer fix
- New Super admin page /app/vapi (AdminVapi.jsx, components/vapi/VapiParts.jsx) + backend vapi_monitor.py (/api/admin/vapi/calls|errors|spend|numbers). Spend limited to 14 days (Vapi plan retention; monitor.vapi_calls clamps createdAtGe). audit() cached 20s. Auto-repair runs after linehealth check every 30 min (guarded: needs Zadarma creds) and emails admin. vapi_events collection (TTL 14d) logs no_disponible, webhook_rechazado, auto_repair. Tested iteration_41 (100%).
- Transfer dropped (endedReason call.in-progress.error-transfer-failed): Zadarma rejects SIP REFER. transferCall now uses transferPlan {blind-transfer, sipVerb dial, fallbackPlan message}. Dial leg goes through shared inbound trunk, so set_transfer_line() puts a Zadarma SIP login on it (done on every connect_tenant_number / Reconfigurar). User must press Reconfigurar on one line after update.
- Call detail: GET /api/admin/vapi/calls/{id} -> ai leg (secs, Vapi cost breakdown) + human leg (secs from transferCall secondsFromStart, Vapi platform share, Zadarma billcost from /v1/statistics matching destination; server-only). UI: click row in Monitor (components/vapi/CallDetail.jsx), "Pasada" badge. Successful-transfer path not yet verified with a real call.
