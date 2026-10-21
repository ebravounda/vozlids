import { useEffect, useState } from "react";
import { toast } from "sonner";
import { CreditCard, Globe2, Loader2, Mail, Mic, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";
import { VoiceLibrary } from "@/components/AdminTelephony";

export function StripeSettings() {
  const [s, setS] = useState(null);
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () => api.get("/admin/stripe").then((r) => setS(r.data));
  useEffect(() => { load(); }, []);
  const save = async () => {
    setBusy(true);
    try { const r = await api.put("/admin/stripe", { secret_key: key }); toast.success(`Stripe conectado (${r.data.mode === "live" ? "modo real" : "modo pruebas"})`); setKey(""); load(); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const disconnect = async () => { if (!window.confirm("¿Desconectar tu cuenta de Stripe? Los nuevos pagos usarán el modo de pruebas.")) return; await api.delete("/admin/stripe"); load(); };
  if (!s) return null;
  return (
    <Panel className="space-y-4" data-testid="stripe-settings-panel">
      <div className="flex items-center gap-2"><CreditCard className="h-5 w-5 text-emerald-300" /><h3 className="text-lg font-semibold text-white">Cobros con Stripe</h3></div>
      {s.uses_shared_test_key && <p className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-3 text-sm text-rose-200" data-testid="stripe-shared-key-warning">
        {s.test_scope !== "off" ? "El modo de prueba está activado pero falta tu clave de prueba (sk_test_…). " : "No hay clave de Stripe conectada. "}
        Ahora se usa una clave de prueba compartida que <b>solo funciona en la vista previa</b>: en tu servidor el pago falla con «403 Forbidden». Pega tu clave abajo.</p>}
      {s.connected ? (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-200" data-testid="stripe-status-connected">
          Conectado a <b>{s.account_name}</b> · {s.mode === "live" ? "modo real (cobros de verdad)" : "modo pruebas"} · clave …{s.key_last4}{s.webhook ? " · avisos automáticos activos" : ""}
        </div>
      ) : (
        <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200" data-testid="stripe-status-test">
          Sin cuenta propia: los clientes pagan en <b>modo pruebas</b> (tarjeta 4242 4242 4242 4242). Pega tu clave secreta para cobrar de verdad.
        </p>
      )}
      <Input type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder="sk_live_… o sk_test_…" className="bg-slate-950/60 font-mono" data-testid="stripe-secret-key-input" />
      <p className="text-xs text-slate-500">Stripe → Desarrolladores → Claves de API → Clave secreta. Al guardar se configuran solos los avisos de pago (webhook).</p>
      <div className="flex gap-2">
        <Button onClick={save} disabled={busy || key.length < 10} className="rounded-full" data-testid="stripe-save-button">{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}{s.connected ? "Cambiar clave" : "Conectar Stripe"}</Button>
        {s.connected && <Button variant="ghost" onClick={disconnect} className="rounded-full" data-testid="stripe-disconnect-button">Desconectar</Button>}
      </div>
      <StripeTestMode s={s} reload={load} />
    </Panel>
  );
}

function StripeTestMode({ s, reload }) {
  const [scope, setScope] = useState(s.test_scope);
  const [emails, setEmails] = useState(s.test_emails.join(", "));
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const run = async (fn, ok) => { setBusy(true); try { await fn(); toast.success(ok); reload(); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); } };
  const saveMode = () => run(() => api.put("/admin/stripe/test-mode", { scope, emails: emails.split(/[\s,;]+/).filter(Boolean) }),
    scope === "off" ? "Modo prueba desactivado: se cobra de verdad" : "Modo prueba activado");
  const saveKey = () => run(async () => { await api.put("/admin/stripe/test-key", { secret_key: key }); setKey(""); }, "Clave de pruebas conectada");
  const opts = [["off", "Desactivado", "todos pagan de verdad"], ["emails", "Solo emails de prueba", "el resto paga de verdad"], ["all", "Toda la web", "nadie paga de verdad"]];
  return (
    <div className="space-y-3 border-t border-slate-800 pt-4" data-testid="stripe-test-mode">
      <div className="flex items-center justify-between">
        <p className="font-semibold text-white">Modo prueba</p>
        {s.test_scope !== "off" && <span className="rounded-full bg-amber-500 px-2.5 py-0.5 text-xs font-bold text-slate-950" data-testid="stripe-test-mode-active">ACTIVO</span>}
      </div>
      <p className="text-xs text-slate-400">Para probar el alta completa sin cobrar: paga con la tarjeta <b className="font-mono">4242 4242 4242 4242</b>, cualquier fecha futura y cualquier CVC. Las altas de prueba se marcan como PRUEBA y no cuentan como ingresos.</p>
      <div className="grid gap-2 sm:grid-cols-3">
        {opts.map(([v, l, d]) => (
          <button key={v} type="button" onClick={() => setScope(v)} className={`rounded-xl border p-3 text-left text-sm transition-colors ${scope === v ? "border-amber-400 bg-amber-500/10" : "border-slate-800 hover:border-slate-600"}`} data-testid={`stripe-test-scope-${v}`}>
            <p className="font-semibold text-white">{l}</p><p className="text-xs text-slate-500">{d}</p>
          </button>
        ))}
      </div>
      {scope === "emails" && <Input value={emails} onChange={(e) => setEmails(e.target.value)} placeholder="pruebas@tudominio.com, otro@…" className="bg-slate-950/60" data-testid="stripe-test-emails-input" />}
      <Button onClick={saveMode} disabled={busy} variant="outline" className="rounded-full" data-testid="stripe-test-mode-save">Guardar modo prueba</Button>
      <div className="space-y-2 rounded-xl border border-slate-800 p-3">
        <p className="text-xs text-slate-400" data-testid="stripe-test-key-status">{s.test_connected ? <>Pagos de prueba en tu cuenta <b>{s.test_account_name}</b> (clave …{s.test_key_last4}).</> : <>Los pagos de prueba usan una cuenta de pruebas ya preparada. Si quieres verlos en tu propio Stripe, pega tu clave <b>sk_test_…</b>.</>}</p>
        <div className="flex gap-2">
          <Input type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder="sk_test_… (opcional)" className="bg-slate-950/60 font-mono" data-testid="stripe-test-key-input" />
          <Button onClick={saveKey} disabled={busy || key.length < 10} variant="outline" className="rounded-full" data-testid="stripe-test-key-save">Guardar</Button>
          {s.test_connected && <Button variant="ghost" onClick={() => run(() => api.delete("/admin/stripe/test-key"), "Clave de pruebas quitada")} className="rounded-full" data-testid="stripe-test-key-remove">Quitar</Button>}
        </div>
      </div>
    </div>
  );
}

export function ElevenLabsSettings() {
  const [s, setS] = useState(null);
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () => api.get("/admin/elevenlabs").then((r) => setS(r.data));
  useEffect(() => { load(); }, []);
  const save = async () => {
    setBusy(true);
    try { const r = await api.put("/admin/elevenlabs", { api_key: key }); r.data.vapi_linked ? toast.success("ElevenLabs conectado y vinculado a Vapi") : toast.warning("ElevenLabs conectado, pero Vapi no aceptó la clave: revisa que tenga el permiso «User» (lectura)."); setKey(""); load(); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const disconnect = async () => { await api.delete("/admin/elevenlabs"); load(); };
  const link = async () => { try { await api.post("/admin/elevenlabs/link-vapi"); toast.success("ElevenLabs vinculado a Vapi"); load(); } catch (e) { toast.error(errMsg(e)); } };
  if (!s) return null;
  return (
    <Panel className="space-y-4" data-testid="elevenlabs-settings-panel">
      <div className="flex items-center gap-2"><Mic className="h-5 w-5 text-emerald-300" /><h3 className="text-lg font-semibold text-white">ElevenLabs (audios de ejemplo)</h3></div>
      {s.connected
        ? <p className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-200" data-testid="elevenlabs-status-connected">Conectado · clave …{s.key_last4}. Los ejemplos suenan con la misma voz que las llamadas.{s.vapi_linked ? " Vinculado a Vapi para las llamadas." : ""}</p>
        : <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200" data-testid="elevenlabs-status-missing">Sin conectar: los ejemplos usan una voz IA de respaldo. Conecta tu clave para oír exactamente la voz de las llamadas.</p>}
      <Input type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder="Clave de API de ElevenLabs" className="bg-slate-950/60 font-mono" data-testid="elevenlabs-key-input" />
      <ol className="list-decimal space-y-1 pl-4 text-xs text-slate-400">
        <li>Entra en elevenlabs.io y crea una cuenta (el plan gratuito sirve para empezar).</li>
        <li>Abajo a la izquierda: tu perfil → «API Keys» → «Create API Key».</li>
        <li>Marca los permisos «Text to Speech», «Voices» (lectura y escritura) y «User» (lectura), crea la clave y cópiala aquí.</li>
        <li>Al guardar la vinculamos también a Vapi, así las llamadas pueden usar voces con acento nativo de la biblioteca.</li>
      </ol>
      <div className="flex gap-2">
        <Button onClick={save} disabled={busy || key.length < 20} className="rounded-full" data-testid="elevenlabs-save-button">{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}{s.connected ? "Cambiar clave" : "Conectar ElevenLabs"}</Button>
        {s.connected && <Button variant="ghost" onClick={disconnect} className="rounded-full" data-testid="elevenlabs-disconnect-button">Desconectar</Button>}
        {s.connected && !s.vapi_linked && <Button variant="outline" onClick={link} className="rounded-full" data-testid="elevenlabs-link-vapi-button">Vincular con Vapi</Button>}
      </div>
    </Panel>
  );
}

export function CartesiaSettings() {
  const [s, setS] = useState(null);
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () => api.get("/admin/cartesia").then((r) => setS(r.data));
  useEffect(() => { load(); }, []);
  const save = async () => {
    setBusy(true);
    try { await api.put("/admin/cartesia", { api_key: key.trim() }); toast.success("Cartesia conectado: ya puedes escuchar las voces Premium"); setKey(""); load(); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const disconnect = async () => { await api.delete("/admin/cartesia"); load(); };
  if (!s) return null;
  return (
    <Panel className="space-y-4" data-testid="cartesia-settings-panel">
      <div className="flex items-center gap-2"><Mic className="h-5 w-5 text-emerald-300" /><h3 className="text-lg font-semibold text-white">Cartesia (ejemplos de voces Premium)</h3></div>
      {s.connected
        ? <p className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-200" data-testid="cartesia-status-connected">Conectado · clave …{s.key_last4}. Los ejemplos de las voces Premium suenan con la misma voz que las llamadas.</p>
        : <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200" data-testid="cartesia-status-missing">Sin conectar: tus clientes no pueden escuchar el ejemplo de las voces Premium. Las llamadas funcionan igual.</p>}
      <Input type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder="Clave de API de Cartesia (sk_car_…)" className="bg-slate-950/60 font-mono" data-testid="cartesia-key-input" />
      <ol className="list-decimal space-y-1 pl-4 text-xs text-slate-400">
        <li>Entra en play.cartesia.ai y crea una cuenta (el plan gratuito sirve).</li>
        <li>Menú «API Keys» → «New API key», cópiala y pégala aquí.</li>
      </ol>
      <div className="flex gap-2">
        <Button onClick={save} disabled={busy || key.trim().length < 10} className="rounded-full" data-testid="cartesia-save-button">{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}{s.connected ? "Cambiar clave" : "Conectar Cartesia"}</Button>
        {s.from_panel && <Button variant="ghost" onClick={disconnect} className="rounded-full" data-testid="cartesia-disconnect-button">Desconectar</Button>}
      </div>
    </Panel>
  );
}

export function ResendSettings() {
  const [s, setS] = useState(null);
  const [f, setF] = useState({ api_key: "", from_email: "", reply_to: "" });
  const [busy, setBusy] = useState(false);
  const load = () => api.get("/admin/resend").then((r) => { setS(r.data); setF((x) => ({ ...x, from_email: r.data.from_email, reply_to: r.data.reply_to })); });
  useEffect(() => { load(); }, []);
  const save = async () => {
    setBusy(true);
    try { await api.put("/admin/resend", f); toast.success("Resend conectado"); setF((x) => ({ ...x, api_key: "" })); load(); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const test = async () => { setBusy(true); try { const r = await api.post("/admin/resend/test"); toast.success(`Email de prueba enviado a ${r.data.to}`); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); } };
  const disconnect = async () => { await api.delete("/admin/resend"); load(); };
  if (!s) return null;
  const inp = (k, ph, type = "text") => <Input type={type} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} placeholder={ph} className="bg-slate-950/60 font-mono" data-testid={`resend-${k}-input`} />;
  return (
    <Panel className="space-y-4" data-testid="resend-settings-panel">
      <div className="flex items-center gap-2"><Mail className="h-5 w-5 text-emerald-300" /><h3 className="text-lg font-semibold text-white">Emails con Resend</h3></div>
      {s.connected
        ? <p className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-200" data-testid="resend-status-connected">Conectado · clave …{s.key_last4} · todos los emails salen desde <b>{s.from_email}</b></p>
        : <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200" data-testid="resend-status-missing">Sin conectar: los emails salen por el servicio de envío integrado. Conecta tu cuenta de Resend para enviarlos desde tu dominio.</p>}
      {inp("api_key", s.connected ? "Nueva clave re_… (opcional para cambiar)" : "Clave de API re_…", "password")}
      {inp("from_email", "Remitente: avisos@vozleads.com")}
      {inp("reply_to", "Responder a (opcional): soporte@vozleads.com")}
      <ol className="list-decimal space-y-1 pl-4 text-xs text-slate-400">
        <li>En resend.com → Domains, añade tu dominio (ej. vozleads.com) y crea los registros DNS que te indica hasta que salga «Verified».</li>
        <li>API Keys → Create API Key con permiso «Sending access» y pégala aquí.</li>
        <li>El remitente debe ser de ese dominio verificado. Pulsa «Enviar prueba» para comprobarlo.</li>
      </ol>
      <div className="flex flex-wrap gap-2">
        <Button onClick={save} disabled={busy || (!s.connected && f.api_key.length < 10) || !f.from_email.includes("@")} className="rounded-full" data-testid="resend-save-button">{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}{s.connected ? "Guardar cambios" : "Conectar Resend"}</Button>
        <Button variant="outline" onClick={test} disabled={busy} className="rounded-full" data-testid="resend-test-button">Enviar prueba</Button>
        {s.connected && <Button variant="ghost" onClick={disconnect} className="rounded-full" data-testid="resend-disconnect-button">Desconectar</Button>}
      </div>
    </Panel>
  );
}

export function GoogleSettings() {
  const [s, setS] = useState(null);
  const [f, setF] = useState({ client_id: "", client_secret: "" });
  const [busy, setBusy] = useState(false);
  const load = () => api.get("/admin/google").then((r) => { setS(r.data); setF((x) => ({ ...x, client_id: r.data.client_id })); });
  useEffect(() => { load(); }, []);
  const save = async () => { setBusy(true); try { await api.put("/admin/google", f); toast.success("Google Calendar activado para tus clientes"); setF((x) => ({ ...x, client_secret: "" })); load(); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); } };
  if (!s) return null;
  return (
    <Panel className="space-y-4" data-testid="google-settings-panel">
      <h3 className="text-lg font-semibold text-white">Google Calendar (app OAuth)</h3>
      {s.configured
        ? <p className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-200" data-testid="google-settings-configured">Activo · {s.connected_accounts} cuentas conectadas</p>
        : <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200" data-testid="google-settings-missing">Sin configurar: tus clientes ven el botón “Conectar Google Calendar” desactivado.</p>}
      <Input value={f.client_id} onChange={(e) => setF({ ...f, client_id: e.target.value })} placeholder="ID de cliente …apps.googleusercontent.com" className="bg-slate-950/60 font-mono" data-testid="google-client-id-input" />
      <Input type="password" value={f.client_secret} onChange={(e) => setF({ ...f, client_secret: e.target.value })} placeholder={s.configured ? "Nuevo secreto (opcional)" : "Secreto de cliente GOCSPX-…"} className="bg-slate-950/60 font-mono" data-testid="google-client-secret-input" />
      <ol className="list-decimal space-y-1 pl-4 text-xs text-slate-400">
        <li>console.cloud.google.com → crea un proyecto → APIs y servicios → Biblioteca → activa <b>Google Calendar API</b>.</li>
        <li>Pantalla de consentimiento OAuth: tipo Externo, nombre VozLeads, ámbitos calendar.events, calendar.freebusy y userinfo.email. Publica la app (o añade usuarios de prueba).</li>
        <li>Credenciales → Crear ID de cliente OAuth → Aplicación web. Origen autorizado: <code className="text-slate-200">{s.origin}</code></li>
        <li>URI de redirección autorizada: <code className="break-all text-slate-200" data-testid="google-redirect-uri">{s.redirect_uri}</code></li>
        <li>Pega aquí el ID y el secreto y guarda.</li>
      </ol>
      <div className="flex gap-2">
        <Button onClick={save} disabled={busy || !f.client_id.includes(".apps.googleusercontent.com") || (!s.configured && f.client_secret.length < 10)} className="rounded-full" data-testid="google-settings-save">{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Guardar</Button>
        {s.configured && <Button variant="ghost" onClick={() => api.delete("/admin/google").then(load)} className="rounded-full" data-testid="google-settings-delete">Desactivar</Button>}
      </div>
    </Panel>
  );
}

const EMPTY = { name: "", gender: "Mujer", language: "es", accent: "", voice_id: "", tone: "" };
export const VOICE_LANGS = [["es", "Español"], ["en", "Inglés"], ["pt", "Portugués"], ["fr", "Francés"], ["it", "Italiano"], ["de", "Alemán"], ["ca", "Catalán"]];

export function CustomVoices() {
  const [items, setItems] = useState([]);
  const [f, setF] = useState(EMPTY);
  const load = () => api.get("/voices/custom").then((r) => setItems(r.data));
  useEffect(() => { load(); }, []);
  const add = async () => { try { await api.post("/admin/voices", f); toast.success("Voz añadida"); setF(EMPTY); load(); } catch (e) { toast.error(errMsg(e)); } };
  const del = async (id) => { try { await api.delete(`/admin/voices/${id}`); load(); } catch (e) { toast.error(errMsg(e)); } };
  const sel = (k, opts) => (
    <Select value={f[k]} onValueChange={(v) => setF({ ...f, [k]: v })}>
      <SelectTrigger className="bg-slate-950/60" data-testid={`voice-${k}-select`}><SelectValue /></SelectTrigger>
      <SelectContent>{opts.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
    </Select>
  );
  return (
    <Panel className="space-y-4" data-testid="custom-voices-panel">
      <div className="flex items-center gap-2"><Mic className="h-5 w-5 text-emerald-300" /><h3 className="text-lg font-semibold text-white">Voces ElevenLabs con acento nativo</h3></div>
      <p className="text-xs text-slate-400">Añade voces de la biblioteca de ElevenLabs en cualquier idioma y con su acento (chileno, argentino, mexicano…). Tus clientes las verán todas al elegir voz. Necesitas tu clave de ElevenLabs conectada en Vapi (Integraciones → ElevenLabs). Si la voz falla, la llamada usa una voz premium de respaldo.</p>
      {items.map((v) => (
        <div key={v.id} className="flex items-center justify-between rounded-xl border border-slate-800 p-3 text-sm" data-testid={`custom-voice-${v.id}`}>
          <span className="text-white">{v.name} <span className="text-xs text-slate-500">· {v.gender} · {(VOICE_LANGS.find(([c]) => c === (v.language || "es")) || [])[1]} · Acento {v.accent || (v.country === "CL" ? "chileno" : "España")} · {v.voice_id}</span></span>
          <button onClick={() => del(v.id)} className="text-slate-500 hover:text-rose-300" data-testid={`custom-voice-delete-${v.id}`}><Trash2 className="h-4 w-4" /></button>
        </div>
      ))}
      <div className="grid grid-cols-2 gap-2">
        <Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Nombre (ej. Carmen)" className="bg-slate-950/60" data-testid="voice-name-input" />
        <Input value={f.voice_id} onChange={(e) => setF({ ...f, voice_id: e.target.value.trim() })} placeholder="ID de voz ElevenLabs" className="bg-slate-950/60 font-mono" data-testid="voice-id-input" />
        {sel("gender", [["Mujer", "Mujer"], ["Hombre", "Hombre"]])}
        {sel("language", VOICE_LANGS)}
        <Input value={f.accent} onChange={(e) => setF({ ...f, accent: e.target.value })} placeholder="Acento (ej. Argentino)" maxLength={30} className="bg-slate-950/60" data-testid="voice-accent-input" />
        <Input value={f.tone} onChange={(e) => setF({ ...f, tone: e.target.value })} placeholder="Tono (opcional)" className="col-span-2 bg-slate-950/60" data-testid="voice-tone-input" />
      </div>
      <Button onClick={add} disabled={!f.name || f.voice_id.length < 10} className="rounded-full" data-testid="voice-add-button"><Plus className="mr-2 h-4 w-4" /> Añadir voz</Button>
      <VoiceLibrary onAdded={load} />
    </Panel>
  );
}

const ST = { llamando: "Llamando", en_curso: "En curso", completada: "Llamado", fallida: "Llamada fallida", sin_agente: "Sin agente", repetida: "Repetida (24 h)", limite_diario: "Tope diario (sin llamada)", limite_internacional: "Tope internacional", no_llamar: "No llamar" };

export function LandingSettings() {
  const [cfg, setCfg] = useState(null);
  const [agents, setAgents] = useState([]);
  const [reqs, setReqs] = useState([]);
  useEffect(() => {
    api.get("/admin/landing").then((r) => setCfg(r.data));
    api.get("/agents").then((r) => setAgents(r.data));
    api.get("/admin/info-requests").then((r) => setReqs(r.data));
  }, []);
  const save = async () => { try { await api.put("/admin/landing", cfg); toast.success("Formulario de la web guardado"); } catch (e) { toast.error(errMsg(e)); } };
  if (!cfg) return null;
  const pick = (c) => (
    <Select value={cfg[`agent_${c}`] || "none"} onValueChange={(v) => setCfg({ ...cfg, [`agent_${c}`]: v === "none" ? "" : v })}>
      <SelectTrigger className="bg-slate-950/60" data-testid={`landing-agent-${c}-select`}><SelectValue /></SelectTrigger>
      <SelectContent>
        <SelectItem value="none">No llamar, solo avisarme</SelectItem>
        {agents.filter((a) => (a.country || "ES") === c.toUpperCase()).map((a) => <SelectItem key={a.id} value={a.id}>{a.name} · {a.business_name}</SelectItem>)}
      </SelectContent>
    </Select>
  );
  return (
    <Panel className="space-y-4 lg:col-span-2" data-testid="landing-settings-panel">
      <div className="flex items-center gap-2"><Globe2 className="h-5 w-5 text-emerald-300" /><h3 className="text-lg font-semibold text-white">Formulario «Solicita información» de la web</h3></div>
      <p className="text-xs text-slate-400">Elige qué agente llama al instante a quien deja sus datos (llamada corta de ~40 segundos con guion de bienvenida de VozLeads). Siempre recibes un email con cada solicitud.</p>
      <div className="grid gap-3 md:grid-cols-3">
        <label className="space-y-1 text-xs text-slate-400">Agente para España (+34){pick("es")}</label>
        <label className="space-y-1 text-xs text-slate-400">Agente para Chile (+56){pick("cl")}</label>
        <label className="space-y-1 text-xs text-slate-400">Email de aviso (vacío = tu email)
          <Input value={cfg.notify_email} onChange={(e) => setCfg({ ...cfg, notify_email: e.target.value })} placeholder="ventas@vozleads.com" className="bg-slate-950/60" data-testid="landing-notify-email-input" />
        </label>
      </div>
      <Button onClick={save} className="rounded-full" data-testid="landing-settings-save-button">Guardar</Button>
      <div className="max-h-72 overflow-y-auto rounded-xl border border-slate-800" data-testid="info-requests-list">
        {reqs.length === 0 ? <p className="p-4 text-sm text-slate-500">Aún no hay solicitudes desde la web.</p> : reqs.map((r) => (
          <div key={r.id} className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 p-3 text-sm last:border-0" data-testid={`info-request-${r.id}`}>
            <span className="text-white">{r.name} <a href={`tel:${r.phone}`} className="font-mono text-xs text-slate-400 hover:text-emerald-300">{r.phone}</a></span>
            <span className="text-xs text-slate-500">{r.page} · {new Date(r.created_at).toLocaleString("es-ES")} · <span className="text-emerald-300">{ST[r.call_status] || r.call_status}</span></span>
          </div>
        ))}
      </div>
    </Panel>
  );
}
