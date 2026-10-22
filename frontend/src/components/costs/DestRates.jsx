import { useEffect, useState } from "react";
import { toast } from "sonner";
import { RotateCcw, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";

function RateRow({ r, onChange }) {
  const [v, setV] = useState(r.usd_min);
  useEffect(() => setV(r.usd_min), [r.usd_min]);
  const save = async () => {
    try { const { data } = await api.put(`/admin/pricing/dest-rates/${r.code}`, { usd_min: Number(v) }); onChange(data.rates); toast.success(`Tarifa de ${r.code} guardada`); }
    catch (e) { toast.error(errMsg(e)); }
  };
  const reset = async () => {
    try { const { data } = await api.delete(`/admin/pricing/dest-rates/${r.code}/manual`); onChange(data.rates); toast.success("Se actualizará con el precio de Zadarma en la próxima sincronización"); }
    catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <tr className="border-t border-slate-800" data-testid={`dest-rate-${r.code}`}>
      <td className="p-3 font-mono text-white">{r.code}</td>
      <td className="p-3 text-xs text-slate-400">{r.name}</td>
      <td className="p-3"><Input type="number" step="0.001" value={v} onChange={(e) => setV(e.target.value)} className="h-8 w-28 bg-slate-950/60 font-mono" data-testid={`dest-rate-input-${r.code}`} /></td>
      <td className="p-3 text-xs">{r.manual ? <span className="text-amber-300">Manual</span> : <span className="text-emerald-300">De Zadarma</span>}</td>
      <td className="p-3 text-right">
        <Button size="sm" variant="ghost" onClick={save} data-testid={`dest-rate-save-${r.code}`}><Save className="h-4 w-4" /></Button>
        {r.manual && <Button size="sm" variant="ghost" onClick={reset} title="Volver a la de Zadarma" data-testid={`dest-rate-reset-${r.code}`}><RotateCcw className="h-4 w-4" /></Button>}
      </td>
    </tr>
  );
}

export function DestRates({ reload }) {
  const [rates, setRates] = useState(null);
  useEffect(() => { api.get("/admin/pricing/dest-rates").then((r) => setRates(r.data.rates)).catch(() => setRates([])); }, [reload]);
  if (!rates) return null;
  return (
    <Panel className="mb-6 overflow-x-auto p-0" data-testid="dest-rates-panel">
      <div className="p-5 pb-2">
        <h3 className="text-lg font-semibold text-white">Tarifas de otros países</h3>
        <p className="text-xs text-slate-500">Se aprenden solas del precio por minuto que cobra Zadarma en cada llamada internacional. Si cambias una, queda fija hasta que la restablezcas. España y Chile usan las tarifas de «Parámetros».</p>
      </div>
      {rates.length ? (
        <table className="w-full min-w-[620px] text-sm">
          <thead className="text-left text-xs uppercase tracking-wider text-slate-500"><tr>{["País", "Destino en Zadarma", "$/min", "Origen", ""].map((h) => <th key={h} className="p-3 font-medium">{h}</th>)}</tr></thead>
          <tbody>{rates.map((r) => <RateRow key={r.code} r={r} onChange={setRates} />)}</tbody>
        </table>
      ) : <p className="p-5 pt-2 text-sm text-slate-500" data-testid="dest-rates-empty">Aún no hay llamadas internacionales. Aparecerán aquí al pulsar «Actualizar costes reales» o «Comparar con Zadarma».</p>}
    </Panel>
  );
}
