import { useEffect, useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, CheckCircle2, Loader2, RefreshCw, Wrench, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHeader, Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";
import { AgentDialog, LineDialog } from "@/components/lines/LineDialog";

const ROLE = { main: "Principal", agent: "Agente", platform: "Plataforma" };
const Check = ({ ok, label, t }) => (
  <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ${ok ? "bg-emerald-100 text-emerald-800" : "bg-rose-100 text-rose-800"}`} data-testid={t}>
    {ok ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}{label}
  </span>
);

function Row({ l, act, busy }) {
  const id = l.number.slice(1);
  const B = ({ k, children, v = "outline" }) => <Button size="sm" variant={v} disabled={busy} onClick={() => act(k, l)} className="h-8 rounded-full px-3 text-xs" data-testid={`line-${k}-${id}`}>{children}</Button>;
  return (
    <tr className="border-t border-slate-800 align-top" data-testid={`line-row-${id}`}>
      <td className="py-3 pr-3"><p className="font-mono font-semibold text-white">{l.number}</p><p className="text-xs text-slate-500">{[l.country === "CL" ? "Chile" : l.country === "ES" ? "España" : "", l.description, l.stop_date && `pagado hasta ${l.stop_date}`].filter(Boolean).join(" · ")}</p></td>
      <td className="py-3 pr-3 text-sm">{l.connected
        ? <><p className="font-semibold text-white">{l.role === "platform" ? "Plataforma VozLeads" : l.owner}</p><p className="text-xs text-slate-400">{ROLE[l.role]}{l.agent ? ` · contesta ${l.agent}` : ""}</p></>
        : <span className={`text-xs font-semibold ${l.usable ? "text-blue-400" : "text-slate-500"}`}>{l.usable ? "Libre" : "Inactivo o vencido en Zadarma"}</span>}</td>
      <td className="py-3 pr-3 font-mono text-xs text-slate-300">{l.sip_id || "—"}</td>
      <td className="py-3 pr-3">{l.connected && <div className="flex flex-wrap gap-1">
        <Check ok={l.ok_in} label="Entrantes" t={`line-in-${id}`} /><Check ok={l.ok_out} label="Salientes" t={`line-out-${id}`} /><Check ok={l.ok_docs} label="Documentos" t={`line-docs-${id}`} />
        {l.error && <p className="mt-1 w-full text-xs text-rose-300">{l.error}</p>}</div>}</td>
      <td className="py-3"><div className="flex flex-wrap justify-end gap-1.5">
        {!l.connected && l.usable && <B k="connect" v="default">Conectar</B>}
        {l.connected && <><B k="agent">Cambiar agente</B><B k="move">Mover</B><B k="reconfigure">Reconfigurar</B><B k="disconnect">Desconectar</B></>}
      </div></td>
    </tr>
  );
}

export default function AdminLines() {
  const [data, setData] = useState(null);
  const [opts, setOpts] = useState(null);
  const [dlg, setDlg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState(null);
  const load = async () => {
    setBusy(true);
    try { const [a, b] = await Promise.all([api.get("/admin/lines"), api.get("/admin/lines/options")]); setData(a.data); setOpts(b.data); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  useEffect(() => { load(); }, []);
  const act = async (k, l) => {
    if (k !== "disconnect") return setDlg({ k, l });
    if (!window.confirm(`¿Desconectar ${l.number}? Dejará de recibir y hacer llamadas en VozLeads (el número sigue en tu Zadarma).`)) return;
    setBusy(true);
    try { await api.post(`/admin/lines/${encodeURIComponent(l.number)}/disconnect`); toast.success("Desconectado"); await load(); }
    catch (e) { toast.error(errMsg(e)); setBusy(false); }
  };
  const all = async () => {
    if (!window.confirm("Se reconfiguran desde cero todos los números conectados con su línea SIP actual. Puede haber cortes de 1-2 minutos por número. ¿Continuar?")) return;
    setBusy(true);
    try { setResults((await api.post("/admin/lines/reconfigure-all", {}, { timeout: 600000 })).data); await load(); }
    catch (e) { toast.error(errMsg(e)); setBusy(false); }
  };
  const done = () => { setDlg(null); load(); };
  const lines = data?.lines || [];
  return (
    <div className="fade-up" data-testid="admin-lines-page">
      <PageHeader eyebrow="Super admin" title="Líneas" desc="Todos tus números de Zadarma en un solo sitio: conéctalos a un cliente, a un agente o a la plataforma, y VozLeads lo configura todo." />
      <Panel className="mt-6 space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <p className="mr-auto text-sm text-slate-400" data-testid="lines-summary">{data ? `${lines.length} números · ${lines.filter((l) => l.connected).length} conectados · ${lines.filter((l) => !l.connected && l.usable).length} libres · Líneas SIP: ${data.sips.length} (${data.sips.filter((s) => !s.used_by).length} sin usar, puedes crear ${data.sips_left} más)` : "Cargando…"}</p>
          <Button size="sm" variant="outline" onClick={load} disabled={busy} className="rounded-full" data-testid="lines-refresh-button">{busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}Actualizar</Button>
          <Button size="sm" onClick={all} disabled={busy || !lines.some((l) => l.connected)} className="rounded-full" data-testid="lines-reconfigure-all-button"><Wrench className="mr-2 h-4 w-4" />Reconfigurar todo</Button>
        </div>
        {results && <div className="rounded-xl border border-slate-700 p-3 text-xs" data-testid="lines-results">{results.map((r) => <p key={r.number} className={r.ok ? "text-emerald-400" : "text-rose-300"}>{r.number}: {r.detail}</p>)}</div>}
        {data?.orphans?.length > 0 && <p className="flex gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200" data-testid="lines-orphans"><AlertTriangle className="h-4 w-4 shrink-0" />Conectados en VozLeads pero no están en tu Zadarma: {data.orphans.map((o) => `${o.number} (${o.owner})`).join(", ")}.</p>}
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] text-left" data-testid="lines-table">
            <thead><tr className="text-[11px] uppercase tracking-wider text-slate-500"><th className="pb-2">Número</th><th className="pb-2">De quién es</th><th className="pb-2">Línea SIP</th><th className="pb-2">Estado</th><th className="pb-2 text-right">Acciones</th></tr></thead>
            <tbody>{lines.map((l) => <Row key={l.number} l={l} act={act} busy={busy} />)}</tbody>
          </table>
          {data && !lines.length && <p className="py-6 text-sm text-slate-500" data-testid="lines-empty">No hay números en tu Zadarma.</p>}
        </div>
      </Panel>
      {dlg && opts && (dlg.k === "agent"
        ? <AgentDialog line={dlg.l} opts={opts} onClose={() => setDlg(null)} onDone={done} />
        : <LineDialog mode={dlg.k} line={dlg.l} data={data} opts={opts} onClose={() => setDlg(null)} onDone={done} />)}
    </div>
  );
}
