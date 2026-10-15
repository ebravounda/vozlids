import { useEffect, useState } from "react";
import { toast } from "sonner";
import { CheckCircle2, CircleDashed, Loader2, Plug } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageHeader, Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";
import { COUNTRIES } from "@/lib/constants";
import { useAuth } from "@/context/AuthContext";

function ConnectZadarma({ onDone, country, prefix }) {
  const [f, setF] = useState({ sip_login: "", sip_password: "", number: "", country });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await api.post("/telephony/zadarma", f);
      toast.success(`Número ${data.number} conectado. ¡Ya puedes llamar!`);
      onDone();
    } catch (err) { toast.error(errMsg(err)); }
    finally { setBusy(false); }
  };
  return (
    <form onSubmit={submit} className="space-y-4 border-t border-slate-800 pt-5" data-testid={`zadarma-connect-form-${country}`}>
      <h4 className="font-semibold text-white">Conectar número {prefix} de Zadarma</h4>
      <div className="space-y-2"><Label>Número virtual {prefix}</Label><Input required value={f.number} onChange={set("number")} placeholder={COUNTRIES[country].example} className="bg-slate-950/60 font-mono" data-testid={`zadarma-number-input-${country}`} /></div>
      <div className="space-y-2"><Label>Usuario SIP (ej. 123456-100)</Label><Input required value={f.sip_login} onChange={set("sip_login")} className="bg-slate-950/60 font-mono" data-testid={`zadarma-sip-login-input-${country}`} /></div>
      <div className="space-y-2"><Label>Contraseña SIP</Label><Input required type="password" value={f.sip_password} onChange={set("sip_password")} className="bg-slate-950/60" data-testid={`zadarma-sip-password-input-${country}`} /></div>
      <p className="text-xs text-slate-500">Se envía directamente a Vapi; no la guardamos.</p>
      <Button type="submit" disabled={busy} className="rounded-full font-semibold" data-testid={`zadarma-connect-button-${country}`}>
        {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plug className="mr-2 h-4 w-4" />} Conectar número
      </Button>
    </form>
  );
}

const Row = ({ ok, label, testid }) => (
  <div className="flex items-center gap-3 text-sm" data-testid={testid}>
    {ok ? <CheckCircle2 className="h-5 w-5 text-emerald-400" /> : <CircleDashed className="h-5 w-5 text-amber-400" />}
    <span className={ok ? "text-white" : "text-slate-300"}>{label}</span>
  </div>
);

const STEPS = [
  "Entra en my.zadarma.com y contrata un número virtual de España (+34) o Chile (+56). Te pedirán documentación para activarlo.",
  "En Configuración › Centralita/PBX o «Números SIP», abre tu número SIP (tipo 123456-100) y copia su usuario y contraseña.",
  "En ese número SIP, en «CallerID», pon el número del país al que vas a llamar (+34 o +56). En España activa el identificador UE (≈0,02 $/min); en Chile la llamada a móviles cuesta ≈0,04–0,05 $/min.",
  "Recarga algo de saldo en Zadarma (las llamadas salientes se pagan allí).",
  "Rellena aquí el número, el usuario y la contraseña SIP y pulsa «Conectar número». Nosotros lo damos de alta en Vapi.",
];

const NUM = { activo: "Activo", comprando: "Preparando tu número…", error: "Pendiente: estamos resolviendo un problema", liberado: "Liberado", sin_numero: "Se asigna al contratar un plan" };

export function MyNumber() {
  const [n, setN] = useState(null);
  const [agents, setAgents] = useState([]);
  useEffect(() => { api.get("/my-number").then((r) => setN(r.data)); api.get("/agents").then((r) => setAgents(r.data)); }, []);
  const setAgent = async (id) => {
    try { const r = await api.put("/my-number", { inbound_agent_id: id === "none" ? "" : id }); setN(r.data); toast.success("Recepcionista actualizada"); }
    catch (e) { toast.error(errMsg(e)); }
  };
  if (!n) return null;
  const mine = agents.filter((a) => (a.country || "ES") === (n.country || "ES"));
  return (
    <Panel className="space-y-4" data-testid="my-number-panel">
      <h3 className="text-lg font-semibold text-white">Tu número</h3>
      <p className="font-mono text-2xl text-white" data-testid="my-number-value">{n.number || "—"}</p>
      <p className={`text-sm ${n.status === "activo" ? "text-emerald-300" : "text-slate-400"}`} data-testid="my-number-status">{NUM[n.status] || n.status}</p>
      {n.status === "activo" && (
        <div className="space-y-2">
          <Label>¿Quién contesta cuando te llaman?</Label>
          <Select value={n.inbound_agent_id || "none"} onValueChange={setAgent}>
            <SelectTrigger className="bg-slate-950/60" data-testid="my-number-inbound-agent-select"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="none">Nadie (no contestar)</SelectItem>
              {mine.map((a) => <SelectItem key={a.id} value={a.id}>{a.name}{a.objective === "recepcion" ? " · recepcionista" : ""}</SelectItem>)}
            </SelectContent>
          </Select>
          <p className="text-xs text-slate-500">Recomendado: crea un agente con el objetivo «Recepcionista». Contesta, resuelve dudas, agenda citas y te avisa si piden hablar con una persona. Las llamadas entrantes cuentan como minutos de tu plan.</p>
        </div>
      )}
    </Panel>
  );
}

function BusinessCountry() {
  const { user, setUser } = useAuth();
  const change = async (country) => {
    try { const { data } = await api.put("/account/country", { country }); setUser(data); toast.success("País del negocio actualizado"); }
    catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Panel className="space-y-3" data-testid="business-country-panel">
      <h3 className="text-lg font-semibold text-white">País de tu negocio</h3>
      <p className="text-sm text-slate-400">Es el país por defecto de tus agentes nuevos. Cada agente puede cambiarlo en su pestaña General.</p>
      <div className="grid grid-cols-2 gap-2">
        {Object.entries(COUNTRIES).map(([c, x]) => (
          <button key={c} onClick={() => change(c)} data-testid={`business-country-${c}`}
            className={`h-11 rounded-lg border text-sm font-semibold ${(user?.country || "ES") === c ? "border-emerald-500 bg-emerald-500/10 text-emerald-200" : "border-slate-700 text-slate-300 hover:border-slate-500"}`}>{x.name} ({x.prefix})</button>
        ))}
      </div>
    </Panel>
  );
}

function PlatformInbound() {
  const [rows, setRows] = useState(null);
  const [agents, setAgents] = useState([]);
  const [sel, setSel] = useState({});
  const [busy, setBusy] = useState("");
  const load = () => api.get("/admin/platform-inbound").then((r) => { setRows(r.data); setSel(Object.fromEntries(r.data.map((x) => [x.country, x.agent_id]))); }).catch(() => setRows([]));
  useEffect(() => { load(); api.get("/agents").then((r) => setAgents(r.data)); }, []);
  const save = async (c) => {
    setBusy(c);
    try {
      const r = await api.put("/admin/platform-inbound", { country: c, agent_id: sel[c] });
      toast.success(r.data.routed ? "Contestador IA activado" : "Activado en la IA. Falta el desvío en Zadarma (ver pasos)");
      load();
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(""); }
  };
  if (!rows?.length) return null;
  return (
    <Panel className="space-y-4" data-testid="platform-inbound-panel">
      <h3 className="text-xl font-semibold text-white">Contestar llamadas entrantes (recepcionista IA)</h3>
      {rows.map((x) => (
        <div key={x.country} className="space-y-3 rounded-xl border border-slate-800 p-4" data-testid={`platform-inbound-${x.country}`}>
          <p className="text-sm font-semibold text-white">{x.number} · {x.enabled ? <span className="text-emerald-300">contesta la IA</span> : <span className="text-amber-300">sin contestador</span>}</p>
          <div className="flex gap-2">
            <Select value={sel[x.country] || ""} onValueChange={(v) => setSel({ ...sel, [x.country]: v })}>
              <SelectTrigger className="bg-slate-950/60" data-testid={`platform-inbound-agent-${x.country}`}><SelectValue placeholder="Elige el agente que contesta" /></SelectTrigger>
              <SelectContent>{agents.filter((a) => (a.country || "ES") === x.country).map((a) => <SelectItem key={a.id} value={a.id}>{a.name}{a.objective === "recepcion" ? " · Recepcionista" : ""}</SelectItem>)}</SelectContent>
            </Select>
            <Button onClick={() => save(x.country)} disabled={!sel[x.country] || busy === x.country} className="rounded-full" data-testid={`platform-inbound-save-${x.country}`}>{busy === x.country && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}{x.enabled ? "Guardar" : "Activar"}</Button>
          </div>
          {x.enabled && !x.routed && (
            <ol className="list-decimal space-y-1 rounded-lg bg-amber-500/10 p-3 pl-7 text-xs text-amber-200" data-testid={`platform-inbound-steps-${x.country}`}>
              <li>Entra en my.zadarma.com → <b>Números virtuales</b> → {x.number} → <b>Configuración</b>.</li>
              <li>En «Recibir llamadas en», elige <b>SIP URI externo</b> (o «Desvío a SIP URI») y pega: <code className="font-mono">{x.sip_uri}</code></li>
              <li>Guarda y llama al número: contestará tu agente. (Si conectas la API de Zadarma en Super admin, este paso se hace solo.)</li>
            </ol>
          )}
        </div>
      ))}
    </Panel>
  );
}

export default function Telephony() {
  const [s, setS] = useState(null);
  const load = () => api.get("/telephony/status").then((r) => setS(r.data));
  useEffect(() => { load(); }, []);

  return (
    <div className="fade-up">
      <PageHeader eyebrow="Telefonía" title="Conexión telefónica" desc="Las llamadas salen por Vapi (voz IA y ambiente) con tus números de Zadarma en España y Chile." />
      <div className="grid gap-6 lg:grid-cols-2">
        <Panel className="space-y-4" data-testid="telephony-panel">
          <h3 className="text-xl font-semibold text-white">Estado</h3>
          <Row ok={s?.has_api_key} label="Clave de Vapi" testid="telephony-api-key-status" />
          {s && Object.entries(s.countries).map(([c, x]) => (
            <Row key={c} ok={x.configured} label={x.number ? `${x.name}: número ${x.number} conectado` : `${x.name}: falta conectar un número ${x.prefix}`} testid={`telephony-number-status-${c}`} />
          ))}
          <Row ok label="Webhook de resultados (se configura solo en cada llamada)" testid="telephony-webhook-status" />
          {s && <p className="break-all rounded-lg bg-slate-950 p-3 font-mono text-xs text-slate-400">{s.webhook_url}</p>}
          {s && !s.configured && <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200" data-testid="telephony-not-configured">Mientras falte algún dato, las llamadas se guardan como “Fallida” con el motivo.</p>}
          {s?.is_admin && s.has_api_key && Object.entries(s.countries).filter(([, x]) => !x.configured).map(([c, x]) => (
            <div key={c} className="space-y-3"><ConnectZadarma onDone={load} country={c} prefix={x.prefix} /></div>
          ))}
          {s && !s.is_admin && !s.configured && <p className="text-xs text-slate-500">Solo el administrador de la plataforma puede conectar el número.</p>}
        </Panel>
        <div className="space-y-6">
        <PlatformInbound />
        <MyNumber />
        <BusinessCountry />
        <Panel className="space-y-4">
          <h3 className="text-xl font-semibold text-white">Cómo conectarlo</h3>
          <ol className="space-y-3">
            {STEPS.map((t, i) => (
              <li key={i} className="flex gap-3 text-sm text-slate-300"><span className="font-mono text-emerald-400">0{i + 1}</span>{t}</li>
            ))}
          </ol>
          <p className="border-t border-slate-800 pt-4 text-xs text-slate-500">Coste aproximado: 0,09–0,14 $ por minuto en España y 0,11–0,17 $ en Chile (Vapi + modelo + voz + Zadarma).</p>
        </Panel>
        </div>
      </div>
    </div>
  );
}
