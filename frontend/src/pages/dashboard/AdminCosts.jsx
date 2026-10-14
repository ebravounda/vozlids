import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, RefreshCw, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageHeader, Panel, StatusBadge } from "@/components/Common";
import { api, errMsg } from "@/lib/api";
import { fmtDate } from "@/lib/constants";

const PARTS = [["voz", "Voz"], ["transcripcion", "Transcripción"], ["ia", "IA (GPT-4o)"], ["vapi", "Vapi plataforma"], ["analisis", "Resumen/análisis"], ["linea", "Línea Zadarma"], ["otros", "Otros"]];
const eur = (usd, fx, d = 3) => (usd == null ? "—" : `${(usd * fx).toLocaleString("es-ES", { minimumFractionDigits: d, maximumFractionDigits: d })} €`);
const planPrice = (v) => Math.max(9, Math.ceil(v / 10) * 10 - 1);

const Stat = ({ label, value, hint, testid }) => (
  <Panel className="p-5" data-testid={testid}>
    <p className="text-xs uppercase tracking-widest text-slate-500">{label}</p>
    <p className="mt-2 font-display text-2xl font-bold text-white">{value}</p>
    {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
  </Panel>
);

function PricingForm({ pricing, onSaved }) {
  const [f, setF] = useState(pricing);
  const [busy, setBusy] = useState(false);
  useEffect(() => setF(pricing), [pricing]);
  const save = async () => {
    setBusy(true);
    try { await api.put("/admin/pricing", { line_rate_usd_min: Number(f.line_rate_usd_min), usd_eur: Number(f.usd_eur), margin_pct: Number(f.margin_pct) }); toast.success("Parámetros guardados"); onSaved(); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const field = (k, label, step) => (
    <div className="space-y-1.5"><Label className="text-xs">{label}</Label><Input type="number" step={step} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} className="bg-slate-950/60 font-mono" data-testid={`pricing-${k}-input`} /></div>
  );
  return (
    <Panel className="space-y-4">
      <h3 className="text-lg font-semibold text-white">Parámetros</h3>
      {field("line_rate_usd_min", "Tarifa Zadarma a móviles ($/min)", "0.001")}
      {field("usd_eur", "Cambio 1 $ = … €", "0.01")}
      {field("margin_pct", "Margen deseado (%)", "10")}
      <Button onClick={save} disabled={busy} className="w-full rounded-full font-semibold" data-testid="pricing-save-button">{busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />} Guardar</Button>
    </Panel>
  );
}

function PriceAdvice({ d }) {
  const fx = d.pricing.usd_eur;
  const estimated = d.cost_per_min == null;
  const costMin = d.cost_per_min ?? 0.11;
  const priceMin = costMin * fx * (1 + d.pricing.margin_pct / 100);
  const callMin = d.minutes_per_call || 1.5;
  return (
    <Panel className="space-y-4 lg:col-span-2" data-testid="pricing-advice">
      <h3 className="text-lg font-semibold text-white">Cómo cobrar</h3>
      <p className="text-sm text-slate-400">
        Te cuesta <span className="font-mono text-white">{eur(costMin, fx)}</span> por minuto{estimated ? " (estimado; aún no hay llamadas con coste)" : " de media"}. Con un margen del {d.pricing.margin_pct}% deberías cobrar
        <span className="font-mono text-emerald-300"> {priceMin.toLocaleString("es-ES", { maximumFractionDigits: 2 })} €/min</span>. Cada lead llamado dura de media {callMin.toFixed(1)} min, así que te cuesta unos {eur(costMin * callMin, fx, 2)} y lo venderías a unos {(priceMin * callMin).toLocaleString("es-ES", { maximumFractionDigits: 2 })} €.
      </p>
      <div className="grid gap-3 sm:grid-cols-3">
        {[["Básico", 100], ["Pro", 300], ["Empresa", 1000]].map(([n, m]) => (
          <div key={n} className="rounded-xl border border-slate-800 bg-slate-950/40 p-4" data-testid={`plan-${n}`}>
            <p className="text-xs uppercase tracking-widest text-slate-500">{n} · {m} min/mes</p>
            <p className="mt-1 font-display text-2xl font-bold text-white">{planPrice(priceMin * m)} €<span className="text-sm font-normal text-slate-500">/mes</span></p>
            <p className="text-xs text-slate-500">≈ {Math.round(m / callMin)} leads · coste {eur(costMin * m, fx, 0)}</p>
          </div>
        ))}
      </div>
      <p className="text-xs text-slate-500">Precios sin IVA. Añade la cuota de Vapi (plan Core 29 $/mes si necesitas más de 4 llamadas simultáneas) y el número de Zadarma.</p>
    </Panel>
  );
}

export default function AdminCosts() {
  const [d, setD] = useState(null);
  const [days, setDays] = useState("30");
  const [syncing, setSyncing] = useState(false);
  const load = useCallback(() => api.get("/admin/costs", { params: { days } }).then((r) => setD(r.data)).catch((e) => toast.error(errMsg(e))), [days]);
  useEffect(() => { load(); }, [load]);

  const sync = async () => {
    setSyncing(true);
    try { const { data } = await api.post("/admin/costs/sync"); toast.success(`${data.updated} llamadas actualizadas`); load(); }
    catch (e) { toast.error(errMsg(e)); } finally { setSyncing(false); }
  };

  if (!d) return <p className="text-slate-400">Cargando…</p>;
  const fx = d.pricing.usd_eur;
  const t = d.totals;

  return (
    <div className="fade-up">
      <PageHeader eyebrow="Administrador" title="Costes y precios" desc="Lo que cuesta cada llamada (Vapi + voz + IA + línea Zadarma) y cuánto cobrar a tus clientes.">
        <Select value={days} onValueChange={setDays}>
          <SelectTrigger className="w-40 bg-slate-900/60" data-testid="costs-days-select"><SelectValue /></SelectTrigger>
          <SelectContent>{[["7", "Últimos 7 días"], ["30", "Últimos 30 días"], ["90", "Últimos 90 días"], ["365", "Último año"]].map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
        </Select>
        <Button variant="outline" onClick={sync} disabled={syncing} className="rounded-full border-slate-700 bg-transparent" data-testid="costs-sync-button">
          {syncing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />} Actualizar desde Vapi
        </Button>
      </PageHeader>
      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Llamadas" value={t.calls} hint={t.missing_cost ? `${t.missing_cost} sin coste aún` : "con coste registrado"} testid="costs-stat-calls" />
        <Stat label="Minutos" value={t.minutes.toFixed(1)} testid="costs-stat-minutes" />
        <Stat label="Coste total" value={eur(t.total, fx, 2)} hint={`${t.total.toFixed(3)} $`} testid="costs-stat-total" />
        <Stat label="Coste por minuto" value={eur(d.cost_per_min, fx)} hint={d.cost_per_call != null ? `${eur(d.cost_per_call, fx)} por llamada` : ""} testid="costs-stat-per-min" />
      </div>
      <div className="mb-6 grid gap-6 lg:grid-cols-3">
        <PriceAdvice d={d} />
        <PricingForm pricing={d.pricing} onSaved={load} />
      </div>
      <div className="mb-6 grid gap-6 lg:grid-cols-3">
        <Panel data-testid="costs-breakdown">
          <h3 className="mb-4 text-lg font-semibold text-white">Desglose</h3>
          {PARTS.map(([k, l]) => {
            const pct = t.total ? (d.breakdown[k] / t.total) * 100 : 0;
            return (
              <div key={k} className="mb-3">
                <div className="flex justify-between text-sm"><span className="text-slate-300">{l}</span><span className="font-mono text-slate-200">{eur(d.breakdown[k], fx)}</span></div>
                <div className="mt-1 h-1.5 rounded-full bg-slate-800"><div className="h-full rounded-full bg-emerald-400" style={{ width: `${pct}%` }} /></div>
              </div>
            );
          })}
        </Panel>
        <Panel className="overflow-x-auto p-0 lg:col-span-2">
          <h3 className="p-5 pb-2 text-lg font-semibold text-white">Por negocio</h3>
          <table className="w-full text-sm" data-testid="costs-tenants-table">
            <thead className="text-left text-xs uppercase tracking-wider text-slate-500"><tr><th className="p-4 font-medium">Negocio</th><th className="p-4 font-medium">Llamadas</th><th className="p-4 font-medium">Minutos</th><th className="p-4 font-medium">Coste</th><th className="p-4 font-medium">€/min</th></tr></thead>
            <tbody>
              {d.tenants.map((x) => (
                <tr key={x.tenant_id} className="border-t border-slate-800"><td className="p-4 text-white">{x.business}</td><td className="p-4">{x.calls}</td><td className="p-4 font-mono">{x.minutes.toFixed(1)}</td><td className="p-4 font-mono">{eur(x.total, fx, 2)}</td><td className="p-4 font-mono">{eur(x.cost_per_min, fx)}</td></tr>
              ))}
            </tbody>
          </table>
          {!d.tenants.length && <p className="p-6 text-sm text-slate-500">Aún no hay llamadas reales en este periodo.</p>}
        </Panel>
      </div>
      <Panel className="overflow-x-auto p-0">
        <h3 className="p-5 pb-2 text-lg font-semibold text-white">Cada llamada</h3>
        <table className="w-full min-w-[960px] text-sm" data-testid="costs-calls-table">
          <thead className="text-left text-xs uppercase tracking-wider text-slate-500">
            <tr><th className="p-3 font-medium">Fecha</th><th className="p-3 font-medium">Negocio / lead</th><th className="p-3 font-medium">Estado</th><th className="p-3 font-medium">Min</th>{PARTS.slice(0, 6).map(([k, l]) => <th key={k} className="p-3 font-medium">{l}</th>)}<th className="p-3 font-medium">Total</th></tr>
          </thead>
          <tbody>
            {d.calls.map((c) => (
              <tr key={c.id} className="border-t border-slate-800" data-testid={`costs-call-${c.id}`}>
                <td className="p-3 text-xs text-slate-400">{fmtDate(c.created_at)}</td>
                <td className="p-3"><p className="text-white">{c.business}</p><p className="text-xs text-slate-500">{c.lead}{c.is_test ? " · prueba" : ""}</p></td>
                <td className="p-3"><StatusBadge status={c.status} testid={`costs-call-status-${c.id}`} /></td>
                <td className="p-3 font-mono">{c.minutes.toFixed(2)}</td>
                {PARTS.slice(0, 6).map(([k]) => <td key={k} className="p-3 font-mono text-xs text-slate-300">{eur(c[k], fx, 4)}</td>)}
                <td className="p-3 font-mono font-semibold text-emerald-300">{eur(c.total, fx, 3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}
