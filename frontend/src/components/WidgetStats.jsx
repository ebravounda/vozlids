import { useEffect, useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Panel } from "@/components/Common";
import { api } from "@/lib/api";

const STEPS = [["views", "Vieron el botón", "#94A3B8"], ["opens", "Lo pulsaron", "#60A5FA"], ["submitted", "Dejaron su teléfono", "#2563EB"],
  ["answered", "Contestaron la llamada", "#10B981"], ["appointments", "Cita agendada", "#059669"]];
const pct = (a, b) => (b ? `${Math.round((100 * a) / b)}%` : "—");

export function WidgetStats({ url = "/widget/stats", title = "Resultados de tu botón" }) {
  const [days, setDays] = useState(30);
  const [d, setD] = useState(null);
  useEffect(() => { api.get(url, { params: { days } }).then((r) => setD(r.data)); }, [url, days]);
  const t = d?.totals;
  return (
    <Panel className="space-y-5" data-testid="widget-stats-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-lg font-semibold text-white">{title}</h3>
        <div className="flex rounded-full border border-slate-800 p-0.5" role="tablist">
          {[7, 30, 90].map((n) => (
            <button key={n} onClick={() => setDays(n)} className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors ${days === n ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"}`} data-testid={`widget-stats-days-${n}`}>{n} días</button>
          ))}
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-5" data-testid="widget-funnel">
        {STEPS.map(([k, label, color], i) => (
          <div key={k} className="rounded-xl border border-slate-800 p-4" data-testid={`widget-funnel-${k}`}>
            <p className="text-xs text-slate-500">{label}</p>
            <p className="mt-1 font-display text-2xl font-bold text-white" data-testid={`widget-funnel-${k}-value`}>{t ? t[k].toLocaleString("es-ES") : "…"}</p>
            {i > 0 && <p className="mt-1 text-xs font-semibold" style={{ color }}>{t ? pct(t[k], t[STEPS[i - 1][0]]) : ""} <span className="font-normal text-slate-500">del paso anterior</span></p>}
          </div>
        ))}
      </div>
      {t && <p className="text-sm text-slate-400" data-testid="widget-conversion">De cada 100 personas que pulsan el botón, <b className="text-white">{t.opens ? Math.round((100 * t.appointments) / t.opens) : 0}</b> acaban con una cita.</p>}
      <div className="h-56" data-testid="widget-stats-chart">
        {d && (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={d.daily} margin={{ left: -20, right: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
              <XAxis dataKey="day" tickFormatter={(v) => v.slice(8) + "/" + v.slice(5, 7)} tick={{ fontSize: 11, fill: "#64748B" }} minTickGap={16} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#64748B" }} />
              <Tooltip labelFormatter={(v) => new Date(v).toLocaleDateString("es-ES")} formatter={(v, k) => [v, STEPS.find((s) => s[0] === k)?.[1]]} />
              {STEPS.slice(1).map(([k, , color]) => <Area key={k} type="monotone" dataKey={k} stroke={color} fill={color} fillOpacity={0.12} strokeWidth={2} />)}
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </Panel>
  );
}
