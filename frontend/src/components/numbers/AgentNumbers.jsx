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

function Row({ n, agents, onAssign, onRemove }) {
  const [label, cls] = STATUS[n.status] || [n.status, "bg-slate-500/20 text-slate-300"];
  const mine = agents.filter((a) => (a.country || "ES") === n.country);
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-800 bg-slate-950/40 p-3" data-testid={`agent-number-${n.id}`}>
      <Phone className="h-4 w-4 text-slate-500" />
      <div className="min-w-[150px] flex-1">
        <p className="font-mono text-white">{n.number || "Número en camino"}</p>
        <p className="text-xs text-slate-500">{n.extra ? `Adicional · ${n.price}/mes` : "Incluido en tu plan"}</p>
      </div>
      <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${cls}`}>{label}</span>
      <Select value={n.agent_id || "none"} onValueChange={(v) => onAssign(n, v === "none" ? "" : v)}>
        <SelectTrigger className="w-56 bg-slate-950/60" data-testid={`agent-number-assign-${n.id}`}><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value="none">{n.extra ? "Sin agente (libre)" : "Nadie contesta"}</SelectItem>
          {mine.map((a) => <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>)}
        </SelectContent>
      </Select>
      {n.extra && <Button variant="ghost" size="icon" onClick={() => onRemove(n)} data-testid={`agent-number-remove-${n.id}`}><Trash2 className="h-4 w-4" /></Button>}
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
      <div className="space-y-2">{d.numbers.map((n) => <Row key={n.id} n={n} agents={agents} onAssign={assign} onRemove={(x) => setConfirm({ ...x, remove: true })} />)}</div>
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

export function PendingExtraNumbers() {
  const [rows, setRows] = useState([]);
  const load = () => api.get("/admin/numbers/extra").then((r) => setRows(r.data));
  useEffect(() => { load(); }, []);
  const approve = async (id) => { try { const r = await api.post(`/admin/numbers/extra/${id}/approve`); toast[r.data.status === "activo" ? "success" : "warning"](r.data.status === "activo" ? "Número activado" : r.data.error || "No se pudo activar"); load(); } catch (e) { toast.error(errMsg(e)); } };
  if (!rows.length) return null;
  return (
    <Panel className="space-y-3" data-testid="pending-extra-numbers">
      <h3 className="text-lg font-semibold text-white">Números adicionales por aprobar</h3>
      {rows.map((n) => (
        <div key={n.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-800 p-3 text-sm" data-testid={`pending-extra-${n.id}`}>
          <span className="flex-1 text-white">{n.business} · {n.country} · {n.price}/mes</span>
          {n.error && <span className="text-xs text-rose-300">{n.error}</span>}
          <Button size="sm" onClick={() => approve(n.id)} className="rounded-full" data-testid={`pending-extra-approve-${n.id}`}>Aprobar y comprar</Button>
        </div>
      ))}
    </Panel>
  );
}
