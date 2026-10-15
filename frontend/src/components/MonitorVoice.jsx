import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Mic } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";
import { fmtDate } from "@/lib/constants";

const n = (v) => Number(v || 0).toLocaleString("es-ES", { useGrouping: "always" });

export function VapiCredit({ ai, onSaved }) {
  const [open, setOpen] = useState(false);
  const [v, setV] = useState("");
  const save = async () => {
    try { await api.put("/admin/monitor/vapi-credit", { amount: Number(v) }); toast.success("Saldo de Vapi anotado"); setOpen(false); setV(""); onSaved(); }
    catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div className="space-y-1.5" data-testid="vapi-credit">
      {ai.credit_left != null
        ? <p className="text-xs text-slate-400" data-testid="vapi-credit-left">Saldo estimado: <b className="font-mono text-white">{ai.credit_left.toFixed(2)} $</b> · anotado {ai.credit_set.toFixed(2)} $ el {fmtDate(ai.credit_set_at)}</p>
        : <p className="text-xs text-amber-300">Anota tu saldo de Vapi para recibir avisos antes de quedarte sin crédito.</p>}
      {open ? (
        <div className="flex gap-2">
          <Input type="number" min="0" step="0.01" autoFocus value={v} onChange={(e) => setV(e.target.value)} placeholder="Saldo en $ que ves en Vapi" className="h-8 bg-slate-950/60 font-mono text-xs" data-testid="vapi-credit-input" />
          <Button size="sm" onClick={save} disabled={v === ""} className="h-8 rounded-full" data-testid="vapi-credit-save">Guardar</Button>
        </div>
      ) : <button onClick={() => setOpen(true)} className="text-xs font-semibold text-emerald-300 underline" data-testid="vapi-credit-edit">{ai.credit_left != null ? "Actualizar saldo tras recargar" : "Anotar saldo actual"}</button>}
    </div>
  );
}

export function VoiceUsage() {
  const [d, setD] = useState(null);
  useEffect(() => { api.get("/admin/monitor/voice-usage").then((r) => setD(r.data)).catch(() => setD({ rows: [] })); }, []);
  const top = d?.rows?.[0]?.chars || 1;
  return (
    <Panel className="overflow-x-auto p-0" data-testid="voice-usage-panel">
      <div className="p-5 pb-2">
        <h3 className="flex items-center gap-2 text-lg font-semibold text-white"><Mic className="h-5 w-5 text-emerald-300" />Consumo de voz por cliente (este mes)</h3>
        <p className="text-xs text-slate-500">Estimación con lo que dijo el agente en cada llamada. {d?.plan_limit ? `Tu plan de ElevenLabs: ${n(d.plan_used)} de ${n(d.plan_limit)} caracteres usados.` : ""} “Por minuto” ayuda a fijar precios: más caracteres por minuto = cliente más caro de servir.</p>
      </div>
      <table className="w-full min-w-[760px] text-sm">
        <thead className="text-left text-xs uppercase tracking-wider text-slate-500"><tr>{["Cliente", "Plan", "Llamadas", "Minutos", "Caracteres", "% del total", "Por minuto"].map((h) => <th key={h} className="p-3">{h}</th>)}</tr></thead>
        <tbody>{d?.rows.map((r) => (
          <tr key={r.tenant_id} className="border-t border-slate-800" data-testid={`voice-usage-row-${r.tenant_id}`}>
            <td className="p-3"><p className="text-white">{r.business}</p><p className="text-xs text-slate-500">{r.email}</p></td>
            <td className="p-3 text-xs text-slate-300">{r.plan || "Sin plan"}</td>
            <td className="p-3 font-mono text-xs">{r.calls}</td><td className="p-3 font-mono text-xs">{r.minutes}</td>
            <td className="p-3"><p className="font-mono text-xs text-white">{n(r.chars)}</p><div className="mt-1 h-1 w-28 overflow-hidden rounded-full bg-slate-800"><div className="h-full bg-emerald-400" style={{ width: `${(100 * r.chars) / top}%` }} /></div></td>
            <td className="p-3 font-mono text-xs">{r.share}%</td>
            <td className="p-3 font-mono text-xs">{r.per_min != null ? n(r.per_min) : "—"}</td>
          </tr>
        ))}</tbody>
      </table>
      {d && !d.rows.length && <p className="p-5 text-sm text-slate-500" data-testid="voice-usage-empty">Sin llamadas con voz este mes.</p>}
    </Panel>
  );
}
