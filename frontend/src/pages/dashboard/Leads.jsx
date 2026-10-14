import { useCallback, useEffect, useState } from "react";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageHeader, Panel, StatusBadge } from "@/components/Common";
import { LeadDetail } from "@/pages/dashboard/LeadDetail";
import { api } from "@/lib/api";
import { STATUS, fmtDate } from "@/lib/constants";

const STAT_KEYS = [
  ["total", "Leads totales", "text-white"],
  ["calificado", "Calificados", "text-emerald-300"],
  ["cita_agendada", "Citas agendadas", "text-teal-200"],
  ["venta", "Ventas", "text-lime-200"],
];

function Stats({ stats }) {
  return (
    <div className="mb-8 grid grid-cols-2 gap-4 lg:grid-cols-4">
      {STAT_KEYS.map(([k, label, cls]) => (
        <Panel key={k} className="p-5" data-testid={`stat-${k}`}>
          <p className="text-xs uppercase tracking-widest text-slate-500">{label}</p>
          <p className={`mt-2 font-display text-3xl font-bold ${cls}`}>{k === "total" ? stats?.total ?? "–" : stats?.by_status?.[k] ?? 0}</p>
        </Panel>
      ))}
    </div>
  );
}

export default function Leads() {
  const [leads, setLeads] = useState(null);
  const [stats, setStats] = useState(null);
  const [status, setStatus] = useState("all");
  const [q, setQ] = useState("");
  const [openId, setOpenId] = useState(null);

  const load = useCallback(() => {
    const params = {};
    if (status !== "all") params.status = status;
    if (q.trim()) params.q = q.trim();
    api.get("/leads", { params }).then((r) => setLeads(r.data)).catch(() => setLeads([]));
    api.get("/stats").then((r) => setStats(r.data)).catch(() => {});
  }, [status, q]);

  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load]);

  return (
    <div className="fade-up">
      <PageHeader eyebrow="Panel" title="Leads y llamadas" desc="Cada lead de tu formulario y el resultado de su llamada. Se actualiza solo cada pocos segundos." />
      <Stats stats={stats} />
      <div className="mb-4 flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar por nombre, teléfono o email" className="h-10 bg-slate-900/60 pl-9" data-testid="leads-search-input" />
        </div>
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="h-10 w-full bg-slate-900/60 sm:w-56" data-testid="leads-status-filter"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos los estados</SelectItem>
            {Object.entries(STATUS).map(([k, s]) => <SelectItem key={k} value={k}>{s.label}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
      <Panel className="overflow-x-auto p-0">
        <table className="w-full min-w-[720px] text-sm" data-testid="leads-table">
          <thead className="border-b border-slate-800 text-left text-xs uppercase tracking-wider text-slate-500">
            <tr><th className="p-4 font-medium">Lead</th><th className="p-4 font-medium">Teléfono</th><th className="p-4 font-medium">Agente</th><th className="p-4 font-medium">Estado</th><th className="p-4 font-medium">Interés</th><th className="p-4 font-medium">Fecha</th></tr>
          </thead>
          <tbody>
            {leads?.map((l) => (
              <tr key={l.id} onClick={() => setOpenId(l.id)} data-testid={`lead-row-${l.id}`} className="cursor-pointer border-b border-slate-800/70 transition-colors hover:bg-slate-800/40">
                <td className="p-4">
                  <p className="font-semibold text-white">{l.name}</p>
                  <p className="text-xs text-slate-500">{l.is_sample ? "Ejemplo" : l.is_test ? "Llamada de prueba" : l.email || "—"}</p>
                </td>
                <td className="p-4 font-mono text-xs text-slate-300">{l.phone}</td>
                <td className="p-4 text-slate-300">{l.agent_name}</td>
                <td className="p-4"><StatusBadge status={l.status} testid={`lead-status-badge-${l.id}`} /></td>
                <td className="p-4">{l.interest_score != null ? <span className="font-mono text-slate-200">{l.interest_score}%</span> : <span className="text-slate-600">—</span>}</td>
                <td className="p-4 text-xs text-slate-400">{fmtDate(l.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {leads && !leads.length && (
          <p className="p-10 text-center text-sm text-slate-500" data-testid="leads-empty">Aún no hay llamadas. Crea un agente y pulsa “Llamarme ahora” para probarlo.</p>
        )}
      </Panel>
      <LeadDetail id={openId} onClose={() => setOpenId(null)} />
    </div>
  );
}
