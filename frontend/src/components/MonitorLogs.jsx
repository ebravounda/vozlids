import { useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Panel, StatusBadge } from "@/components/Common";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/constants";
import { cur } from "@/components/MonitorParts";

const DAYS = [["1", "Hoy"], ["7", "7 días"], ["30", "30 días"], ["90", "90 días"]];
const COLS = [["ia", "IA"], ["voz", "Voz"], ["transcripcion", "Transcr."], ["vapi", "Plataf."], ["analisis", "Análisis"], ["linea", "Línea"], ["otros", "Otros"]];
const dur = (m) => `${Math.floor(m)}:${String(Math.round((m % 1) * 60)).padStart(2, "0")}`;

function DaysSelect({ value, onChange, testid }) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="h-9 w-32 bg-slate-950/60 text-xs" data-testid={testid}><SelectValue /></SelectTrigger>
      <SelectContent>{DAYS.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
    </Select>
  );
}

export function CallLog() {
  const [days, setDays] = useState("7");
  const [tenant, setTenant] = useState("all");
  const [q, setQ] = useState("");
  const [d, setD] = useState(null);
  useEffect(() => { setD(null); api.get("/admin/costs", { params: { days } }).then((r) => setD(r.data)); }, [days]);
  const fx = d?.pricing.usd_eur || 0.92;
  const rows = useMemo(() => (d?.calls || []).filter((c) => (tenant === "all" || c.tenant_id === tenant)
    && (!q || `${c.lead} ${c.phone} ${c.business}`.toLowerCase().includes(q.toLowerCase()))), [d, tenant, q]);
  const total = rows.reduce((s, c) => s + c.total, 0);
  return (
    <Panel className="space-y-3 p-0" data-testid="call-log-panel">
      <div className="flex flex-wrap items-center gap-2 p-5 pb-0">
        <h3 className="mr-auto text-lg font-semibold text-white">Registro de llamadas y coste</h3>
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar nombre o número" className="h-9 w-48 bg-slate-950/60 text-xs" data-testid="call-log-search-input" />
        <Select value={tenant} onValueChange={setTenant}>
          <SelectTrigger className="h-9 w-48 bg-slate-950/60 text-xs" data-testid="call-log-tenant-select"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="all">Todos los clientes</SelectItem>{d?.tenants.map((t) => <SelectItem key={t.tenant_id} value={t.tenant_id}>{t.business}</SelectItem>)}</SelectContent>
        </Select>
        <DaysSelect value={days} onChange={setDays} testid="call-log-days-select" />
      </div>
      <p className="px-5 text-xs text-slate-500" data-testid="call-log-summary">{rows.length} llamadas · coste total <b className="text-white">{cur(total * fx)}</b> · importes en € (convertidos desde $ a {fx})</p>
      {!d ? <p className="p-5 text-sm text-slate-400"><Loader2 className="mr-2 inline h-4 w-4 animate-spin" />Cargando…</p> : (
        <div className="max-h-[560px] overflow-auto">
          <table className="w-full min-w-[1100px] text-xs">
            <thead className="sticky top-0 bg-slate-950 text-left uppercase tracking-wider text-slate-500"><tr>
              {["Fecha", "Cliente", "Contacto", "Tipo", "Duración", ...COLS.map((c) => c[1]), "Total", "Fin"].map((h) => <th key={h} className="p-2.5">{h}</th>)}
            </tr></thead>
            <tbody>{rows.map((c) => (
              <tr key={c.id} className="border-t border-slate-800" data-testid={`call-log-row-${c.id}`}>
                <td className="whitespace-nowrap p-2.5 text-slate-400">{fmtDate(c.created_at)}</td>
                <td className="p-2.5 text-white">{c.business}{c.is_test && <span className="ml-1 text-slate-500">(prueba)</span>}</td>
                <td className="p-2.5"><p className="text-white">{c.lead}</p><p className="font-mono text-slate-500">{c.phone}</p></td>
                <td className="p-2.5 text-slate-300">{c.direction}</td>
                <td className="p-2.5 font-mono">{dur(c.minutes)}</td>
                {COLS.map(([k]) => <td key={k} className="p-2.5 font-mono text-slate-400">{cur(c[k] * fx, "EUR", 3)}</td>)}
                <td className="p-2.5 font-mono font-semibold text-white">{cur(c.total * fx, "EUR", 3)}</td>
                <td className="p-2.5"><StatusBadge status={c.status} testid={`call-log-status-${c.id}`} /><p className="mt-1 max-w-[160px] truncate text-slate-500" title={c.error || c.ended_reason}>{c.error || c.ended_reason}</p></td>
              </tr>
            ))}</tbody>
          </table>
          {!rows.length && <p className="p-5 text-sm text-slate-500">No hay llamadas en este periodo.</p>}
        </div>
      )}
    </Panel>
  );
}

export function SipLog() {
  const [days, setDays] = useState("7");
  const [d, setD] = useState(null);
  useEffect(() => { setD(null); api.get("/admin/monitor/sip-calls", { params: { days: Math.min(30, Number(days)) } }).then((r) => setD(r.data)); }, [days]);
  return (
    <Panel className="space-y-3 p-0" data-testid="sip-log-panel">
      <div className="flex items-center gap-2 p-5 pb-0">
        <h3 className="mr-auto text-lg font-semibold text-white">Llamadas facturadas por Zadarma</h3>
        <DaysSelect value={days} onChange={setDays} testid="sip-log-days-select" />
      </div>
      {!d ? <p className="p-5 text-sm text-slate-400"><Loader2 className="mr-2 inline h-4 w-4 animate-spin" />Cargando…</p> : d.error ? <p className="p-5 text-sm text-amber-300" data-testid="sip-log-error">{d.error}</p> : <>
        <p className="px-5 text-xs text-slate-500" data-testid="sip-log-summary">{d.count} llamadas · coste real de línea <b className="text-white">{cur(d.total, d.currency, 3)}</b> (máx. 30 días)</p>
        <div className="max-h-[420px] overflow-auto">
          <table className="w-full min-w-[720px] text-xs">
            <thead className="sticky top-0 bg-slate-950 text-left uppercase tracking-wider text-slate-500"><tr>{["Fecha", "Desde", "Hacia", "Destino", "Segundos", "Estado", "Coste"].map((h) => <th key={h} className="p-2.5">{h}</th>)}</tr></thead>
            <tbody>{d.calls.map((c, i) => (
              <tr key={c.id || i} className="border-t border-slate-800" data-testid={`sip-log-row-${i}`}>
                <td className="whitespace-nowrap p-2.5 text-slate-400">{c.start}</td><td className="p-2.5 font-mono">{c.from}</td><td className="p-2.5 font-mono">{c.to}</td>
                <td className="p-2.5 text-slate-400">{c.destination}</td><td className="p-2.5 font-mono">{c.seconds}</td>
                <td className={`p-2.5 ${c.disposition === "answered" ? "text-emerald-300" : "text-amber-300"}`}>{c.disposition}</td>
                <td className="p-2.5 font-mono text-white">{cur(c.cost, c.currency, 3)}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </>}
    </Panel>
  );
}
