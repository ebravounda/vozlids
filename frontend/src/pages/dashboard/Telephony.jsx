import { useEffect, useState } from "react";
import { toast } from "sonner";
import { CheckCircle2, CircleDashed, Loader2, Plug } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader, Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";

function ConnectZadarma({ onDone }) {
  const [f, setF] = useState({ sip_login: "", sip_password: "", number: "" });
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
    <form onSubmit={submit} className="space-y-4 border-t border-slate-800 pt-5" data-testid="zadarma-connect-form">
      <h4 className="font-semibold text-white">Conectar mi número de Zadarma</h4>
      <div className="space-y-2"><Label>Número virtual +34</Label><Input required value={f.number} onChange={set("number")} placeholder="+34 910 000 000" className="bg-slate-950/60 font-mono" data-testid="zadarma-number-input" /></div>
      <div className="space-y-2"><Label>Usuario SIP (ej. 123456-100)</Label><Input required value={f.sip_login} onChange={set("sip_login")} className="bg-slate-950/60 font-mono" data-testid="zadarma-sip-login-input" /></div>
      <div className="space-y-2"><Label>Contraseña SIP</Label><Input required type="password" value={f.sip_password} onChange={set("sip_password")} className="bg-slate-950/60" data-testid="zadarma-sip-password-input" /></div>
      <p className="text-xs text-slate-500">Se envía directamente a Vapi; no la guardamos.</p>
      <Button type="submit" disabled={busy} className="rounded-full font-semibold" data-testid="zadarma-connect-button">
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
  "Entra en my.zadarma.com y contrata un número virtual español (+34). Te pedirán documentación (DNI/CIF y dirección) para activarlo.",
  "En Configuración › Centralita/PBX o «Números SIP», abre tu número SIP (tipo 123456-100) y copia su usuario y contraseña.",
  "En ese número SIP, en «CallerID», pon tu número +34 para que el lead vea un número español. Activa también la tarifa/identificador UE para pagar ≈0,02 $/min a móviles.",
  "Recarga algo de saldo en Zadarma (las llamadas salientes se pagan allí).",
  "Rellena aquí el número, el usuario y la contraseña SIP y pulsa «Conectar número». Nosotros lo damos de alta en Vapi.",
];

export default function Telephony() {
  const [s, setS] = useState(null);
  const load = () => api.get("/telephony/status").then((r) => setS(r.data));
  useEffect(() => { load(); }, []);

  return (
    <div className="fade-up">
      <PageHeader eyebrow="Telefonía" title="Conexión telefónica" desc="Las llamadas salen por Vapi (voz IA y ambiente) con tu número español de Zadarma." />
      <div className="grid gap-6 lg:grid-cols-2">
        <Panel className="space-y-4" data-testid="telephony-panel">
          <h3 className="text-xl font-semibold text-white">Estado</h3>
          <Row ok={s?.has_api_key} label="Clave de Vapi" testid="telephony-api-key-status" />
          <Row ok={s?.has_phone_number} label={s?.number ? `Número ${s.number} conectado en Vapi` : "Número +34 de Zadarma conectado en Vapi"} testid="telephony-number-status" />
          <Row ok label="Webhook de resultados (se configura solo en cada llamada)" testid="telephony-webhook-status" />
          {s && <p className="break-all rounded-lg bg-slate-950 p-3 font-mono text-xs text-slate-400">{s.webhook_url}</p>}
          {s && !s.configured && <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200" data-testid="telephony-not-configured">Mientras falte algún dato, las llamadas se guardan como “Fallida” con el motivo.</p>}
          {s?.is_admin && s.has_api_key && !s.has_phone_number && <ConnectZadarma onDone={load} />}
          {s && !s.is_admin && !s.configured && <p className="text-xs text-slate-500">Solo el administrador de la plataforma puede conectar el número.</p>}
        </Panel>
        <Panel className="space-y-4">
          <h3 className="text-xl font-semibold text-white">Cómo conectarlo</h3>
          <ol className="space-y-3">
            {STEPS.map((t, i) => (
              <li key={i} className="flex gap-3 text-sm text-slate-300"><span className="font-mono text-emerald-400">0{i + 1}</span>{t}</li>
            ))}
          </ol>
          <p className="border-t border-slate-800 pt-4 text-xs text-slate-500">Coste aproximado: 0,09–0,14 $ por minuto (Vapi + modelo + voz + Zadarma).</p>
        </Panel>
      </div>
    </div>
  );
}
