import { useState } from "react";
import { CheckCircle2, XCircle } from "lucide-react";

const LEVEL = { ok: "bg-emerald-100 text-emerald-800", aviso: "bg-amber-100 text-amber-800", error: "bg-rose-100 text-rose-800" };
const DIR = { entrante: "Entrante", saliente: "Saliente", web: "Web" };
const when = (iso) => (iso ? new Date(iso).toLocaleString("es-ES", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—");
const dur = (s) => (s ? `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}` : "—");
const usd = (n) => `$${(n || 0).toFixed(n < 1 ? 3 : 2)}`;
const Empty = ({ t, children }) => <p className="py-6 text-sm text-slate-500" data-testid={t}>{children}</p>;
const Th = ({ children, r }) => <th className={`pb-2 ${r ? "text-right" : ""}`}>{children}</th>;

export const CallsTable = ({ rows }) => {
  const [f, setF] = useState("all");
  if (!rows) return <Empty t="vapi-calls-loading">Cargando llamadas…</Empty>;
  const list = rows.filter((r) => f === "all" || r.level === f || r.direction === f);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2" data-testid="vapi-calls-filters">
        {[["all", "Todas"], ["entrante", "Entrantes"], ["saliente", "Salientes"], ["error", "Con error"], ["aviso", "Avisos"]].map(([k, l]) => (
          <button key={k} onClick={() => setF(k)} className={`rounded-full border px-3 py-1 text-xs ${f === k ? "border-blue-500 bg-blue-500 text-white" : "border-slate-700 text-slate-400"}`} data-testid={`vapi-filter-${k}`}>{l}</button>
        ))}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[900px] text-left text-sm" data-testid="vapi-calls-table">
          <thead><tr className="text-[11px] uppercase tracking-wider text-slate-500"><Th>Fecha</Th><Th>Tipo</Th><Th>Número</Th><Th>Cliente</Th><Th>Llamante / destino</Th><Th r>Duración</Th><Th r>Coste</Th><Th>Cómo terminó</Th></tr></thead>
          <tbody>{list.map((r) => (
            <tr key={r.id} className="border-t border-slate-800" data-testid={`vapi-call-${r.id}`}>
              <td className="py-2 text-xs text-slate-400">{when(r.at)}</td><td>{DIR[r.direction]}</td><td className="font-mono text-xs">{r.number}</td>
              <td className="text-xs">{r.owner}</td><td className="font-mono text-xs">{r.customer}</td><td className="text-right">{dur(r.seconds)}</td>
              <td className="text-right">{usd(r.cost)}</td>
              <td><span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${LEVEL[r.level]}`} title={r.code}>{r.status !== "ended" ? "En curso" : r.reason}</span></td>
            </tr>
          ))}</tbody>
        </table>
        {!list.length && <Empty t="vapi-calls-empty">No hay llamadas con este filtro.</Empty>}
      </div>
    </div>
  );
};

export const NumbersTable = ({ data }) => {
  if (!data) return <Empty t="vapi-numbers-loading">Revisando números…</Empty>;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2 text-xs" data-testid="vapi-numbers-summary">
        <Pill ok={data.shared} label={data.shared ? "Conexión de entrada común creada" : "Falta la conexión de entrada común"} />
        <Pill ok={data.transfer_ready} label={data.transfer_ready ? "Lista para pasar llamadas a personas" : "Para pasar llamadas: pulsa «Reconfigurar» en un número de Líneas"} />
        <Pill ok={!data.duplicates} label={data.duplicates ? `${data.duplicates} conexión(es) de entrada duplicada(s)` : "Sin conexiones duplicadas"} />
        <Pill ok={data.zadarma} label={data.zadarma ? "Desvíos de Zadarma revisados" : "Zadarma no conectado: no se revisan desvíos"} />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-left text-sm" data-testid="vapi-numbers-table">
          <thead><tr className="text-[11px] uppercase tracking-wider text-slate-500"><Th>Número</Th><Th>De quién es</Th><Th>Identificador en Vapi</Th><Th>Estado</Th></tr></thead>
          <tbody>{data.numbers.map((n) => (
            <tr key={n.number} className="border-t border-slate-800 align-top" data-testid={`vapi-number-${n.number.slice(1)}`}>
              <td className="py-2 font-mono text-xs">{n.number}{n.extra && <span className="ml-1 text-slate-500">(agente)</span>}</td>
              <td className="text-xs">{n.owner}</td><td className="font-mono text-xs">{n.alias || "—"}</td>
              <td>{n.ok ? <Pill ok label="Recibe llamadas" /> : <ul className="space-y-1">{n.issues.map((i) => <li key={i}><Pill label={i} /></li>)}</ul>}</td>
            </tr>
          ))}</tbody>
        </table>
        {!data.numbers.length && <Empty t="vapi-numbers-empty">No hay números conectados.</Empty>}
      </div>
    </div>
  );
};

const Pill = ({ ok, label }) => (
  <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ${ok ? LEVEL.ok : LEVEL.error}`}>
    {ok ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}{label}
  </span>
);

const KIND = { no_disponible: "Respondió «no disponible»", webhook_rechazado: "Aviso de Vapi rechazado", auto_repair: "Reparación automática" };

export const ErrorsList = ({ data }) => {
  if (!data) return <Empty t="vapi-errors-loading">Cargando errores…</Empty>;
  if (!data.calls.length && !data.events.length) return <Empty t="vapi-errors-empty">Sin errores en las últimas llamadas.</Empty>;
  return (
    <div className="space-y-2" data-testid="vapi-errors-list">
      {data.events.map((e, i) => (
        <div key={`e${i}`} className="rounded-xl border border-slate-800 p-3 text-sm" data-testid={`vapi-event-${i}`}>
          <p className="font-semibold">{KIND[e.kind] || e.kind}{e.number && ` · ${e.number}`}</p>
          <p className="text-xs text-slate-400">{when(e.at)} · {e.detail}</p>
        </div>
      ))}
      {data.calls.map((r) => (
        <div key={r.id} className="rounded-xl border border-rose-500/30 p-3 text-sm" data-testid={`vapi-error-call-${r.id}`}>
          <p className="font-semibold">{r.reason}</p>
          <p className="text-xs text-slate-400">{when(r.at)} · {DIR[r.direction]} · {r.number} · {r.owner} · llamante {r.customer}</p>
        </div>
      ))}
    </div>
  );
};

const Bars = ({ rows, k, label }) => {
  const max = Math.max(...rows.map((r) => r.cost), 0.01);
  return (
    <div className="space-y-2">
      {rows.map((r) => (
        <div key={r[k]} className="grid grid-cols-[150px_1fr_150px] items-center gap-3 text-xs" data-testid={`vapi-spend-${label}-${r[k]}`}>
          <span className="truncate text-slate-400">{r[k]}</span>
          <span className="h-2 rounded-full bg-slate-800"><span className="block h-2 rounded-full bg-blue-500" style={{ width: `${(r.cost / max) * 100}%` }} /></span>
          <span className="text-right">{usd(r.cost)} · {r.minutes} min · {r.calls} llam.</span>
        </div>
      ))}
    </div>
  );
};

export const SpendView = ({ data }) => {
  if (!data) return <Empty t="vapi-spend-loading">Calculando gasto…</Empty>;
  const total = data.days.reduce((a, d) => a + d.cost, 0);
  return (
    <div className="grid gap-6 lg:grid-cols-2" data-testid="vapi-spend">
      <div><p className="mb-3 text-sm font-semibold" data-testid="vapi-spend-total">Por día · últimos 14 días · {usd(total)}</p><Bars rows={data.days} k="day" label="day" /></div>
      <div><p className="mb-3 text-sm font-semibold">Por cliente</p><Bars rows={data.owners} k="owner" label="owner" /></div>
    </div>
  );
};
