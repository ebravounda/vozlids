import { useEffect, useState } from "react";
import { CheckCircle2, CircleDashed } from "lucide-react";
import { PageHeader, Panel } from "@/components/Common";
import { api } from "@/lib/api";

const Row = ({ ok, label, testid }) => (
  <div className="flex items-center gap-3 text-sm" data-testid={testid}>
    {ok ? <CheckCircle2 className="h-5 w-5 text-emerald-400" /> : <CircleDashed className="h-5 w-5 text-amber-400" />}
    <span className={ok ? "text-white" : "text-slate-300"}>{label}</span>
  </div>
);

const STEPS = [
  "En Zadarma, contrata un número español (+34) y activa un identificador de llamada español/UE para llamar a móviles a ≈0,02 $/min.",
  "En Zadarma › Configuración › PBX, crea una extensión SIP y copia su usuario y contraseña.",
  "En el panel de Vapi › Phone Numbers › Import › BYO SIP Trunk, sigue la guía oficial de Zadarma (servidor sip.zadarma.com) y añade tu número +34.",
  "Copia el Phone Number ID que te da Vapi y tu API Key privada (Vapi › API Keys).",
  "Pásaselas al equipo técnico (o pégalas en el chat de Emergent) para activarlas en la plataforma.",
];

export default function Telephony() {
  const [s, setS] = useState(null);
  useEffect(() => { api.get("/telephony/status").then((r) => setS(r.data)); }, []);

  return (
    <div className="fade-up">
      <PageHeader eyebrow="Telefonía" title="Conexión telefónica" desc="Las llamadas salen por Vapi (voz IA y ambiente) con tu número español de Zadarma." />
      <div className="grid gap-6 lg:grid-cols-2">
        <Panel className="space-y-4" data-testid="telephony-panel">
          <h3 className="text-xl font-semibold text-white">Estado</h3>
          <Row ok={s?.has_api_key} label="Clave de Vapi" testid="telephony-api-key-status" />
          <Row ok={s?.has_phone_number} label="Número +34 de Zadarma conectado en Vapi" testid="telephony-number-status" />
          <Row ok label="Webhook de resultados (se configura solo en cada llamada)" testid="telephony-webhook-status" />
          {s && <p className="break-all rounded-lg bg-slate-950 p-3 font-mono text-xs text-slate-400">{s.webhook_url}</p>}
          {s && !s.configured && <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200" data-testid="telephony-not-configured">Mientras falte algún dato, las llamadas se guardan como “Fallida” con el motivo.</p>}
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
