import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/Common";

const eur = (usd, fx, d = 2) => (usd == null ? "—" : `${(usd * fx).toLocaleString("es-ES", { minimumFractionDigits: d, maximumFractionDigits: d })} €`);
const pct = (v) => (v == null ? "—" : `${v.toFixed(0)} %`);

const Row = ({ label, value, strong, tone, testid }) => (
  <div className={`flex justify-between py-1.5 text-sm ${strong ? "border-t border-slate-800 pt-3 font-semibold" : ""}`} data-testid={testid}>
    <span className="text-slate-300">{label}</span><span className={`font-mono ${tone || "text-slate-100"}`}>{value}</span>
  </div>
);

export function ProfitSummary({ d, days }) {
  const p = d.profit;
  const fx = d.pricing.usd_eur;
  const net = p.net >= 0 ? "text-emerald-300" : "text-rose-300";
  return (
    <Panel className="lg:col-span-2" data-testid="profit-summary">
      <h3 className="text-lg font-semibold text-white">Beneficio real · últimos {days} días</h3>
      <p className="mb-3 text-xs text-slate-500">Ingresos de las suscripciones activas (precio de tarifa, sin promociones) menos todo lo que pagas a proveedores.</p>
      <Row label="Ingresos por suscripciones" value={eur(p.revenue, fx)} testid="profit-revenue" />
      <Row label="Llamadas (Vapi + IA + voz + línea)" value={`− ${eur(p.variable, fx)}`} testid="profit-variable" />
      <Row label="Números de clientes + comisiones Stripe" value={`− ${eur(p.per_client_fixed, fx)}`} testid="profit-per-client" />
      <Row label="Costes fijos" value={`− ${eur(p.fixed, fx)}`} testid="profit-fixed" />
      <Row label="Beneficio neto" value={eur(p.net, fx)} tone={net} strong testid="profit-net" />
      <Row label="Margen" value={pct(p.margin_pct)} tone={net} testid="profit-margin" />
      <SourcesNote d={d} />
    </Panel>
  );
}

function SourcesNote({ d }) {
  const z = d.zadarma_sync || {};
  const e = d.eleven_usage;
  return (
    <div className="mt-4 space-y-1.5 rounded-xl border border-slate-800 bg-slate-950/40 p-3 text-xs text-slate-400" data-testid="cost-sources">
      <p><span className="text-slate-200">Línea Zadarma:</span> {d.totals.line_real} de {d.totals.calls} llamadas con coste real de Zadarma.{" "}
        {z.error ? <span className="text-amber-300" data-testid="zadarma-sync-error">{z.error}</span> : "El resto usa la tarifa estimada hasta que Zadarma lo publique."}</p>
      <p><span className="text-slate-200">Voces HD:</span> se calculan con los caracteres de cada llamada y tu plan de ElevenLabs.
        {e && <> Uso este mes: <span className="font-mono text-slate-200" data-testid="eleven-usage">{(e.used || 0).toLocaleString("es-ES")} / {(e.limit || 0).toLocaleString("es-ES")}</span> créditos (plan {e.tier}).</>}</p>
    </div>
  );
}

export function FixedCostsEditor({ items, onChange }) {
  const set = (i, patch) => onChange(items.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  return (
    <div className="space-y-2" data-testid="fixed-costs-editor">
      <p className="text-xs text-slate-400">Costes fijos al mes ($). No pongas aquí ElevenLabs: ya se reparte por llamada.</p>
      {items.map((x, i) => (
        <div key={i} className="flex gap-2">
          <Input value={x.name} onChange={(e) => set(i, { name: e.target.value })} className="bg-slate-950/60 text-xs" data-testid={`fixed-cost-name-${i}`} />
          <Input type="number" step="0.01" value={x.usd} onChange={(e) => set(i, { usd: e.target.value })} className="w-24 bg-slate-950/60 font-mono text-xs" data-testid={`fixed-cost-usd-${i}`} />
          <Button variant="ghost" size="icon" onClick={() => onChange(items.filter((_, j) => j !== i))} data-testid={`fixed-cost-delete-${i}`}><Trash2 className="h-4 w-4" /></Button>
        </div>
      ))}
      <Button variant="outline" size="sm" onClick={() => onChange([...items, { name: "Nuevo coste", usd: 0 }])} className="rounded-full border-slate-700 bg-transparent" data-testid="fixed-cost-add"><Plus className="mr-1 h-4 w-4" /> Añadir coste fijo</Button>
    </div>
  );
}
