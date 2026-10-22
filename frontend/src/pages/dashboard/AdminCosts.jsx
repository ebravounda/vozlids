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
import { FixedCostsEditor, ProfitSummary } from "@/components/costs/ProfitParts";
import { ZadarmaCompare } from "@/components/costs/ZadarmaCompare";

const PARTS = [["voz", "Voz"], ["transcripcion", "Transcripción"], ["ia", "IA (GPT-4.1)"], ["vapi", "Vapi plataforma"], ["analisis", "Resumen/análisis"], ["linea", "Línea Zadarma"], ["otros", "Otros"]];
const eur = (usd, fx, d = 3) => (usd == null ? "—" : `${(usd * fx).toLocaleString("es-ES", { minimumFractionDigits: d, maximumFractionDigits: d })} €`);
const clp = (usd, fx) => (usd == null ? "—" : `$${Math.round(usd * fx).toLocaleString("es-CL")} CLP`);
const money = (usd, pricing, currency, d) => (currency === "CLP" ? clp(usd, pricing.usd_clp) : eur(usd, pricing.usd_eur, d));
const planPrice = (v) => Math.max(9, Math.ceil(v / 10) * 10 - 1);
const VOICE_NAMES = [["11labs", "ElevenLabs (más natural)"], ["cartesia", "Premium"], ["azure", "Estándar"]];
const baseMin = (d, country) => d.by_country[country].base_per_min ?? 0.07 + (country === "CL" ? d.pricing.line_rate_cl_usd_min : d.pricing.line_rate_usd_min);
const costWith = (d, country, provider) => baseMin(d, country) + d.voices[provider].per_min;

const Stat = ({ label, value, hint, testid }) => (
  <Panel className="p-5" data-testid={testid}>
    <p className="text-xs uppercase tracking-widest text-slate-500">{label}</p>
    <p className="mt-2 font-display text-2xl font-bold text-white">{value}</p>
    {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
  </Panel>
);

const NUM_FIELDS = ["line_rate_usd_min", "line_rate_cl_usd_min", "usd_eur", "usd_clp", "margin_pct", "voice_11labs_usd_min", "voice_cartesia_usd_min",
  "voice_azure_usd_min", "eleven_plan_usd", "eleven_plan_credits", "eleven_credits_per_char", "number_es_usd_month", "number_cl_usd_month", "stripe_pct", "stripe_fixed_eur"];

function PricingForm({ pricing, onSaved }) {
  const [f, setF] = useState(pricing);
  const [busy, setBusy] = useState(false);
  useEffect(() => setF(pricing), [pricing]);
  const save = async () => {
    setBusy(true);
    const body = Object.fromEntries(NUM_FIELDS.map((k) => [k, Number(f[k])]));
    body.fixed_costs = (f.fixed_costs || []).filter((x) => x.name.trim()).map((x) => ({ name: x.name.trim(), usd: Number(x.usd) || 0 }));
    try { await api.put("/admin/pricing", body); toast.success("Parámetros guardados"); onSaved(); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const field = (k, label, step) => (
    <div className="space-y-1.5"><Label className="text-xs">{label}</Label><Input type="number" step={step} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} className="bg-slate-950/60 font-mono" data-testid={`pricing-${k}-input`} /></div>
  );
  return (
    <Panel className="space-y-4">
      <h3 className="text-lg font-semibold text-white">Parámetros</h3>
      {field("line_rate_usd_min", "Tarifa Zadarma España ($/min)", "0.001")}
      {field("line_rate_cl_usd_min", "Tarifa Zadarma Chile ($/min)", "0.001")}
      {field("usd_eur", "Cambio 1 $ = … €", "0.01")}
      {field("usd_clp", "Cambio 1 $ = … CLP", "1")}
      {field("margin_pct", "Margen deseado (%)", "10")}
      {field("voice_cartesia_usd_min", "Voz Premium estimada ($/min)", "0.001")}
      {field("voice_azure_usd_min", "Voz Estándar estimada ($/min)", "0.001")}
      <p className="pt-2 text-xs font-semibold uppercase tracking-widest text-slate-500">Tu plan de ElevenLabs</p>
      <div className="grid grid-cols-3 gap-2">{field("eleven_plan_usd", "Precio ($/mes)", "1")}{field("eleven_plan_credits", "Créditos", "1000")}{field("eleven_credits_per_char", "Créditos/letra", "0.1")}</div>
      <p className="pt-2 text-xs font-semibold uppercase tracking-widest text-slate-500">Por cliente</p>
      <div className="grid grid-cols-2 gap-2">{field("number_es_usd_month", "Número España ($/mes)", "0.5")}{field("number_cl_usd_month", "Número Chile ($/mes)", "0.5")}</div>
      <div className="grid grid-cols-2 gap-2">{field("stripe_pct", "Stripe (%)", "0.1")}{field("stripe_fixed_eur", "Stripe fijo (€)", "0.05")}</div>
      <FixedCostsEditor items={f.fixed_costs || []} onChange={(fixed_costs) => setF({ ...f, fixed_costs })} />
      <Button onClick={save} disabled={busy} className="w-full rounded-full font-semibold" data-testid="pricing-save-button">{busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />} Guardar</Button>
    </Panel>
  );
}

function CountryAdvice({ d, country }) {
  const c = d.by_country[country];
  const isCL = country === "CL";
  const fx = isCL ? d.pricing.usd_clp : d.pricing.usd_eur;
  const fmt = (usd) => (isCL ? clp(usd, fx) : eur(usd, fx, 2));
  const estimated = c.cost_per_min == null;
  const costMin = costWith(d, country, "11labs");
  const priceMinUsd = costMin * (1 + d.pricing.margin_pct / 100);
  const callMin = c.minutes_per_call || 1.5;
  const plan = (usd) => (isCL ? `$${(Math.ceil((usd * fx) / 1000) * 1000 - 10).toLocaleString("es-CL")}` : `${planPrice(usd * fx)} €`);
  return (
    <div className="space-y-3" data-testid={`pricing-advice-${country}`}>
      <p className="text-sm text-slate-400">
        <span className="font-semibold text-white">{isCL ? "Chile" : "España"}:</span> con voces ElevenLabs te cuesta <span className="font-mono text-white">{fmt(costMin)}</span>/min{estimated ? " (estimado)" : ` (según ${c.calls} llamadas reales)`}. Con un margen del {d.pricing.margin_pct}% cobra
        <span className="font-mono text-emerald-300"> {fmt(priceMinUsd)}/min</span>. Un lead llamado (~{callMin.toFixed(1)} min) te cuesta {fmt(costMin * callMin)}.
      </p>
      <div className="grid gap-3 sm:grid-cols-3">
        {[["Básico", 100], ["Pro", 300], ["Empresa", 1000]].map(([n, m]) => (
          <div key={n} className="rounded-xl border border-slate-800 bg-slate-950/40 p-4" data-testid={`plan-${country}-${n}`}>
            <p className="text-xs uppercase tracking-widest text-slate-500">{n} · {m} min/mes</p>
            <p className="mt-1 font-display text-2xl font-bold text-white">{plan(priceMinUsd * m)}<span className="text-sm font-normal text-slate-500">/mes</span></p>
            <p className="text-xs text-slate-500">≈ {Math.round(m / callMin)} leads · coste {fmt(costMin * m)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function VoiceCompare({ d }) {
  const fx = d.pricing;
  const m = 1 + fx.margin_pct / 100;
  return (
    <Panel className="overflow-x-auto p-0 lg:col-span-3" data-testid="voice-cost-compare">
      <div className="p-5 pb-2"><h3 className="text-lg font-semibold text-white">Coste por tipo de voz</h3>
        <p className="text-xs text-slate-500">Coste total por minuto (Vapi + IA + transcripción + voz + línea). Se recalcula solo con las llamadas reales a partir de 5 minutos por tipo de voz.</p></div>
      <table className="w-full min-w-[760px] text-sm">
        <thead className="text-left text-xs uppercase tracking-wider text-slate-500"><tr><th className="p-4">Voz</th><th className="p-4">Solo voz /min</th><th className="p-4">Coste total España</th><th className="p-4">Cobrar España</th><th className="p-4">Coste total Chile</th><th className="p-4">Cobrar Chile</th></tr></thead>
        <tbody>{VOICE_NAMES.map(([k, n]) => {
          const v = d.voices[k];
          return (
            <tr key={k} className="border-t border-slate-800" data-testid={`voice-cost-${k}`}>
              <td className="p-4 text-white">{n}</td>
              <td className="p-4 font-mono">{eur(v.per_min, fx.usd_eur, 3)} <span className="text-xs text-slate-500">{v.measured_per_min != null && v.minutes >= 5 ? `medido (${v.minutes.toFixed(0)} min)` : "estimado"}</span></td>
              <td className="p-4 font-mono">{eur(costWith(d, "ES", k), fx.usd_eur, 3)}</td>
              <td className="p-4 font-mono text-emerald-300">{eur(costWith(d, "ES", k) * m, fx.usd_eur, 2)}/min</td>
              <td className="p-4 font-mono">{clp(costWith(d, "CL", k), fx.usd_clp)}</td>
              <td className="p-4 font-mono text-emerald-300">{clp(costWith(d, "CL", k) * m, fx.usd_clp)}/min</td>
            </tr>
          );
        })}</tbody>
      </table>
      <p className="p-4 pt-2 text-xs text-slate-400">ElevenLabs cuesta unos {eur(d.voices["11labs"].per_min - d.voices.cartesia.per_min, fx.usd_eur, 3)} más por minuto que la voz Premium: en un plan de 500 minutos son ≈ {eur((d.voices["11labs"].per_min - d.voices.cartesia.per_min) * 500, fx.usd_eur, 0)} al mes.</p>
    </Panel>
  );
}

function PriceAdvice({ d }) {
  return (
    <Panel className="space-y-6 lg:col-span-2" data-testid="pricing-advice">
      <h3 className="text-lg font-semibold text-white">Cómo cobrar</h3>
      <CountryAdvice d={d} country="ES" />
      <CountryAdvice d={d} country="CL" />
      <p className="text-xs text-slate-500">Precios sin IVA. Los costes fijos y los números de cada cliente se restan aparte en «Beneficio real».</p>
    </Panel>
  );
}

function TenantsTable({ d }) {
  const m = (v, x) => money(v, d.pricing, x.currency, 2);
  return (
    <Panel className="mb-6 overflow-x-auto p-0">
      <h3 className="p-5 pb-2 text-lg font-semibold text-white">Beneficio por cliente</h3>
      <table className="w-full min-w-[980px] text-sm" data-testid="costs-tenants-table">
        <thead className="text-left text-xs uppercase tracking-wider text-slate-500"><tr>{["Negocio", "Plan", "Llamadas", "Minutos", "Ingresos", "Coste llamadas", "Número", "Stripe", "Beneficio", "Margen"].map((h) => <th key={h} className="p-4 font-medium">{h}</th>)}</tr></thead>
        <tbody>
          {d.tenants.map((x) => (
            <tr key={x.tenant_id} className="border-t border-slate-800" data-testid={`costs-tenant-${x.tenant_id}`}>
              <td className="p-4 text-white">{x.business}</td><td className="p-4 text-xs text-slate-400">{x.plan || "Sin plan"}</td>
              <td className="p-4">{x.calls}</td><td className="p-4 font-mono">{x.minutes.toFixed(1)}</td>
              <td className="p-4 font-mono">{m(x.revenue, x)}</td><td className="p-4 font-mono">{m(x.total, x)}</td>
              <td className="p-4 font-mono">{m(x.number_fee, x)}</td><td className="p-4 font-mono">{m(x.stripe_fee, x)}</td>
              <td className={`p-4 font-mono font-semibold ${x.profit >= 0 ? "text-emerald-300" : "text-rose-300"}`} data-testid={`costs-tenant-profit-${x.tenant_id}`}>{m(x.profit, x)}</td>
              <td className="p-4 font-mono">{x.margin_pct == null ? "—" : `${x.margin_pct.toFixed(0)} %`}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {!d.tenants.length && <p className="p-6 text-sm text-slate-500">Aún no hay clientes con llamadas o suscripción en este periodo.</p>}
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
    try { const { data } = await api.post("/admin/costs/sync"); toast.success(`${data.updated} llamadas de Vapi y ${data.line_matched} de Zadarma actualizadas`); if (data.line_error) toast.warning(data.line_error); load(); }
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
          {syncing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />} Actualizar costes reales
        </Button>
        <ZadarmaCompare days={days} />
      </PageHeader>
      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Llamadas" value={t.calls} hint={t.missing_cost ? `${t.missing_cost} sin coste aún` : "con coste registrado"} testid="costs-stat-calls" />
        <Stat label="Minutos" value={t.minutes.toFixed(1)} testid="costs-stat-minutes" />
        <Stat label="Coste total" value={eur(t.total, fx, 2)} hint={`${t.total.toFixed(3)} $`} testid="costs-stat-total" />
        <Stat label="Coste por minuto" value={eur(d.cost_per_min, fx)} hint={d.cost_per_call != null ? `${eur(d.cost_per_call, fx)} por llamada` : ""} testid="costs-stat-per-min" />
      </div>
      <div className="mb-6 grid gap-6 lg:grid-cols-3">
        <ProfitSummary d={d} days={days} />
        <Panel data-testid="costs-breakdown">
          <h3 className="mb-4 text-lg font-semibold text-white">Desglose de llamadas</h3>
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
      </div>
      <div className="mb-6 grid gap-6 lg:grid-cols-3">
        <PriceAdvice d={d} />
        <PricingForm pricing={d.pricing} onSaved={load} />
        <VoiceCompare d={d} />
      </div>
      <TenantsTable d={d} />
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
                <td className="p-3"><p className="text-white">{c.business}</p><p className="text-xs text-slate-500">{c.lead}{c.is_test ? " · prueba" : ""} · {c.country === "CL" ? "Chile" : "España"}</p></td>
                <td className="p-3"><StatusBadge status={c.status} testid={`costs-call-status-${c.id}`} /></td>
                <td className="p-3 font-mono">{c.minutes.toFixed(2)}</td>
                {PARTS.slice(0, 6).map(([k]) => <td key={k} className="p-3 font-mono text-xs text-slate-300">{money(c[k], d.pricing, c.currency, 4)}{k === "linea" && <span className={`ml-1 text-[10px] ${c.line_real ? "text-emerald-400" : "text-slate-500"}`}>{c.line_real ? "real" : "est."}</span>}</td>)}
                <td className="p-3 font-mono font-semibold text-emerald-300">{money(c.total, d.pricing, c.currency, 3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}
