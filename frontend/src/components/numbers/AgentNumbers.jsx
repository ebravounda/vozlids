import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Phone, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";

const STATUS = { activo: ["Activo", "bg-emerald-500/15 text-emerald-300"], comprando: ["Preparando", "bg-amber-500/15 text-amber-300"],
  pendiente_aprobacion: ["Pendiente de aprobar", "bg-amber-500/15 text-amber-300"], pendiente: ["Preparando", "bg-amber-500/15 text-amber-300"],
  error: ["Con incidencia", "bg-rose-500/15 text-rose-300"] };

function Row({ n, agents, taken, onAssign, onRemove }) {
  const [label, cls] = STATUS[n.status] || [n.status, "bg-slate-500/20 text-slate-300"];
  const mine = agents.filter((a) => (a.country || "ES") === n.country && (!n.extra || a.id === n.agent_id || !taken.has(a.id)));
  return (
    <div className="grid grid-cols-[auto_1fr_auto] items-center gap-3 rounded-xl border border-slate-800 bg-slate-950/40 p-3 sm:grid-cols-[auto_1fr_auto_14rem_2.25rem]" data-testid={`agent-number-${n.id}`}>
      <Phone className="h-4 w-4 text-slate-500" />
      <div className="min-w-0">
        <p className={n.number ? "font-mono text-white" : "text-sm font-medium text-slate-300"}>{n.number || "Número en camino"}</p>
        <p className="text-xs text-slate-500">{n.extra ? `Adicional · ${n.price}/mes` : "Incluido en tu plan"}</p>
      </div>
      <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${cls}`}>{label}</span>
      <Select value={n.agent_id || "none"} onValueChange={(v) => onAssign(n, v === "none" ? "" : v)}>
        <SelectTrigger className="col-span-2 bg-slate-950/60 sm:col-span-1" data-testid={`agent-number-assign-${n.id}`}><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value="none">{n.extra ? "Sin agente (libre)" : "Nadie contesta"}</SelectItem>
          {mine.map((a) => <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>)}
        </SelectContent>
      </Select>
      {n.extra ? <Button variant="ghost" size="icon" onClick={() => onRemove(n)} data-testid={`agent-number-remove-${n.id}`}><Trash2 className="h-4 w-4" /></Button> : <span />}
    </div>
  );
}

export function AgentNumbers() {
  const [d, setD] = useState(null);
  const [agents, setAgents] = useState([]);
  const [pick, setPick] = useState("");
  const [confirm, setConfirm] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = () => api.get("/numbers").then((r) => setD(r.data));
  useEffect(() => { load(); api.get("/agents").then((r) => setAgents(r.data)); }, []);
  if (!d) return null;
  const taken = new Set(d.numbers.filter((n) => n.extra).map((n) => n.agent_id));
  const free = agents.filter((a) => !taken.has(a.id));
  const chosen = agents.find((a) => a.id === pick);
  const assign = async (n, agent_id) => { try { await api.put(`/numbers/${n.id}`, { agent_id }); toast.success("Número asignado"); load(); } catch (e) { toast.error(errMsg(e)); } };
  const buy = async () => {
    setBusy(true);
    try { const r = await api.post("/numbers/extra", { agent_id: pick }); toast.success(r.data.status === "pendiente_aprobacion" ? "Pedido recibido: te avisaremos cuando el número esté activo" : "Número en camino"); setPick(""); setConfirm(null); load(); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const remove = async () => { try { await api.delete(`/numbers/${confirm.id}`); toast.success("Número dado de baja"); setConfirm(null); load(); } catch (e) { toast.error(errMsg(e)); } };
  return (
    <Panel className="space-y-4" data-testid="agent-numbers-panel">
      <div><h3 className="text-lg font-semibold text-white">Números por agente</h3>
        <p className="text-sm text-slate-400">Cada agente puede ser una sucursal o una empresa con su propio número: llama desde él y contesta las llamadas que entren. Tu plan incluye 1 número; cada número adicional cuesta {d.prices.ES}/mes en España y {d.prices.CL}/mes en Chile.</p></div>
      <div className="space-y-2">{d.numbers.map((n) => <Row key={n.id} n={n} agents={agents} taken={taken} onAssign={assign} onRemove={(x) => setConfirm({ ...x, remove: true })} />)}</div>
      <div className="flex flex-wrap gap-2 border-t border-slate-800 pt-4">
        <Select value={pick} onValueChange={setPick}>
          <SelectTrigger className="w-64 bg-slate-950/60" data-testid="agent-numbers-pick"><SelectValue placeholder="Elige el agente o sucursal" /></SelectTrigger>
          <SelectContent>{free.map((a) => <SelectItem key={a.id} value={a.id}>{a.name} · {a.country || "ES"}</SelectItem>)}</SelectContent>
        </Select>
        <Button disabled={!pick} onClick={() => setConfirm({ buy: true })} className="rounded-full" data-testid="agent-numbers-add-button"><Plus className="mr-1 h-4 w-4" />Añadir número</Button>
      </div>
      <AlertDialog open={!!confirm} onOpenChange={(o) => !o && setConfirm(null)}>
        <AlertDialogContent data-testid="agent-numbers-confirm">
          <AlertDialogHeader>
            <AlertDialogTitle>{confirm?.buy ? `¿Añadir un número para ${chosen?.name}?` : "¿Dar de baja este número?"}</AlertDialogTitle>
            <AlertDialogDescription>{confirm?.buy
              ? `Se añade a tu suscripción por ${d.prices[chosen?.country || "ES"]}/mes. Hoy pagas solo la parte proporcional del mes.`
              : "El número deja de funcionar y deja de cobrarse desde hoy. Puede que no se pueda recuperar el mismo número."}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="agent-numbers-cancel">Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={(e) => { e.preventDefault(); confirm?.buy ? buy() : remove(); }} disabled={busy} data-testid="agent-numbers-confirm-button">{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}{confirm?.buy ? "Confirmar y pagar" : "Dar de baja"}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Panel>
  );
}

export function PendingExtraBanner() {
  const [n, setN] = useState(0);
  useEffect(() => { api.get("/admin/numbers/extra").then((r) => setN(r.data.length)).catch(() => {}); }, []);
  if (!n) return null;
  const go = () => document.getElementById("pending-extra-numbers")?.scrollIntoView({ behavior: "smooth", block: "center" });
  return (
    <button onClick={go} className="mb-6 flex w-full items-center gap-3 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-left text-sm text-amber-900 transition-colors hover:bg-amber-100" data-testid="pending-extra-banner">
      <Phone className="h-4 w-4 shrink-0" />
      <span className="flex-1 font-semibold" data-testid="pending-extra-banner-count">{n === 1 ? "1 número adicional pendiente de aprobar" : `${n} números adicionales pendientes de aprobar`}</span>
      <span className="text-xs underline">Revisar</span>
    </button>
  );
}

function PendingRow({ n, onAct, busy }) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-800 p-3 text-sm" data-testid={`pending-extra-${n.id}`}>
      <div className="min-w-0 flex-1">
        <p className="text-white">{n.business} · {n.country} · {n.price}/mes</p>
        <p className="text-xs text-slate-500">{n.agent_name && `Agente: ${n.agent_name} · `}{n.created_at && new Date(n.created_at).toLocaleString("es-ES", { dateStyle: "short", timeStyle: "short" })}</p>
        {n.error && <p className="text-xs text-rose-300">{n.error}</p>}
      </div>
      <Button size="sm" disabled={!!busy} onClick={() => onAct(n.id, "approve")} className="rounded-full" data-testid={`pending-extra-approve-${n.id}`}>{busy === `${n.id}approve` && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}Aprobar y comprar</Button>
      <Button size="sm" variant="ghost" disabled={!!busy} onClick={() => onAct(n.id, "reject")} className="rounded-full text-rose-300" data-testid={`pending-extra-reject-${n.id}`}>{busy === `${n.id}reject` && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}Rechazar</Button>
    </div>
  );
}

export function PendingExtraNumbers() {
  const [rows, setRows] = useState([]);
  const [busy, setBusy] = useState("");
  const load = () => api.get("/admin/numbers/extra").then((r) => setRows(r.data));
  useEffect(() => { load(); }, []);
  const act = async (id, kind) => {
    if (kind === "reject" && !window.confirm("¿Rechazar la solicitud? Se anulará el cobro al cliente y se le avisará por email.")) return;
    setBusy(id + kind);
    try {
      const r = await api.post(`/admin/numbers/extra/${id}/${kind}`);
      if (kind === "reject") toast.success("Solicitud rechazada y cobro anulado");
      else toast[r.data.status === "activo" ? "success" : "warning"](r.data.status === "activo" ? "Número activado" : r.data.error || "No se pudo activar");
      load();
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(""); }
  };
  return (
    <Panel className="space-y-3" id="pending-extra-numbers" data-testid="pending-extra-numbers">
      <h3 className="text-lg font-semibold text-white">Números adicionales por aprobar</h3>
      {rows.length ? rows.map((n) => <PendingRow key={n.id} n={n} onAct={act} busy={busy} />)
        : <p className="text-sm text-slate-500" data-testid="pending-extra-empty">No hay solicitudes pendientes. Cuando un cliente pida un número adicional aparecerá aquí y te llegará un email.</p>}
    </Panel>
  );
}
