import { useEffect, useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, CreditCard, ExternalLink, Loader2, Mail, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageHeader, Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";

const ST = { pagada: "bg-emerald-100 text-emerald-800", pendiente: "bg-amber-100 text-amber-800", vencida: "bg-rose-100 text-rose-800", impagada: "bg-rose-100 text-rose-800" };
const money = (a, c) => new Intl.NumberFormat("es-ES", { style: "currency", currency: (c || "eur").toUpperCase(), maximumFractionDigits: c === "clp" ? 0 : 2 }).format(c === "clp" ? a : a / 100);
const day = (iso) => (iso ? new Date(iso).toLocaleDateString("es-ES", { day: "2-digit", month: "short", year: "numeric" }) : "—");
const FILTERS = [["all", "Todas"], ["pagada", "Pagadas"], ["pendiente", "Pendientes"], ["vencida", "Vencidas"]];

const Stat = ({ label, value, tone, t }) => (
  <Panel className="p-5" data-testid={t}><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</p><p className={`mt-2 text-3xl font-bold ${tone}`}>{value}</p></Panel>
);

function LinkDialog({ acc, plans, onClose }) {
  const [plan, setPlan] = useState(acc.plan_id || "");
  const [busy, setBusy] = useState(false);
  const send = async () => {
    setBusy(true);
    try { await api.post("/admin/payments/send-link", { user_id: acc.id, plan_id: plan }); toast.success(`Enlace enviado a ${acc.email}`); onClose(); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-md" data-testid="payments-link-dialog">
        <DialogHeader><DialogTitle>Enviar enlace de tarjeta a {acc.name}</DialogTitle></DialogHeader>
        <p className="text-sm text-slate-500">Le llega un email a {acc.email} con un enlace seguro de Stripe para registrar su tarjeta y activar la suscripción.</p>
        <Select value={plan || undefined} onValueChange={setPlan}>
          <SelectTrigger data-testid="payments-link-plan-select"><SelectValue placeholder="Elige el plan" /></SelectTrigger>
          <SelectContent>{plans.map((p) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}</SelectContent>
        </Select>
        <Button onClick={send} disabled={!plan || busy} className="w-full rounded-full" data-testid="payments-link-send-button">{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}<Mail className="mr-2 h-4 w-4" />Enviar enlace</Button>
      </DialogContent>
    </Dialog>
  );
}

export default function AdminPayments() {
  const [d, setD] = useState(null);
  const [plans, setPlans] = useState([]);
  const [f, setF] = useState("all");
  const [link, setLink] = useState(null);
  const [busy, setBusy] = useState("");
  const load = () => api.get("/admin/payments").then((r) => setD(r.data)).catch((e) => toast.error(errMsg(e)));
  useEffect(() => { load(); api.get("/admin/plans").then((r) => setPlans(r.data)).catch(() => {}); }, []);
  const charge = async (i) => {
    if (!window.confirm(`¿Cobrar ahora ${money(i.amount, i.currency)} a ${i.account} con su tarjeta guardada?`)) return;
    setBusy(i.id);
    try { await api.post(`/admin/payments/invoices/${i.id}/pay?mode=${i.mode}`); toast.success("Cobrado"); load(); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(""); }
  };
  const inv = (d?.invoices || []).filter((i) => f === "all" || i.status === f);
  return (
    <div className="fade-up" data-testid="admin-payments-page">
      <PageHeader eyebrow="Super admin" title="Pagos" desc="Cobros de Stripe de todas las cuentas: lo recibido, lo pendiente y cuándo vence cada suscripción." >
        <Button variant="outline" onClick={load} className="rounded-full" data-testid="payments-refresh-button"><RefreshCw className="mr-2 h-4 w-4" />Actualizar</Button>
      </PageHeader>
      {d && Object.values(d.errors).map((e) => <p key={e} className="mt-4 flex gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900" data-testid="payments-error"><AlertTriangle className="h-4 w-4 shrink-0" />{e}</p>)}
      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <Stat label="Pagos recibidos este mes" value={d ? d.totals.paid_month : "…"} tone="text-emerald-600" t="payments-stat-paid" />
        <Stat label="Facturas pendientes" value={d ? d.totals.pending : "…"} tone="text-amber-600" t="payments-stat-pending" />
        <Stat label="Facturas vencidas" value={d ? d.totals.overdue : "…"} tone="text-rose-600" t="payments-stat-overdue" />
      </div>
      <Panel className="mt-6 overflow-x-auto p-0" data-testid="payments-accounts">
        <p className="p-5 pb-2 font-semibold text-slate-900">Cuentas y vencimientos</p>
        <table className="w-full min-w-[820px] text-left text-sm">
          <thead className="text-[11px] uppercase tracking-wider text-slate-500"><tr><th className="px-5 py-2">Cuenta</th><th>Plan</th><th>Suscripción</th><th>Próximo cobro</th><th className="px-5 text-right">Acciones</th></tr></thead>
          <tbody>{(d?.accounts || []).map((a) => (
            <tr key={a.id} className="border-t border-slate-100" data-testid={`payments-account-${a.id}`}>
              <td className="px-5 py-3"><p className="font-semibold text-slate-900">{a.name}</p><p className="text-xs text-slate-500">{a.email} · {a.country}</p></td>
              <td>{a.plan || "—"}</td>
              <td><span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${a.stripe && a.sub_status === "active" ? "bg-emerald-100 text-emerald-800" : a.stripe ? "bg-amber-100 text-amber-800" : "bg-slate-100 text-slate-600"}`}>{a.stripe ? ({ active: "Activa", past_due: "Pago atrasado", canceled: "Cancelada", unpaid: "Impagada", trialing: "Prueba" }[a.sub_status] || a.sub_status) : a.plan ? "Asignado a mano" : "Sin suscripción"}</span></td>
              <td className="tabular-nums">{a.renews ? `${day(a.renews)}${a.cancel_at_end ? " · se cancela" : ""}` : "—"}</td>
              <td className="px-5 text-right"><Button size="sm" variant="outline" onClick={() => setLink(a)} className="rounded-full" data-testid={`payments-send-link-${a.id}`}><CreditCard className="mr-1.5 h-4 w-4" />Enviar enlace de tarjeta</Button></td>
            </tr>))}</tbody>
        </table>
      </Panel>
      <Panel className="mt-6 overflow-x-auto p-0" data-testid="payments-invoices">
        <div className="flex flex-wrap items-center gap-2 p-5 pb-2">
          <p className="mr-auto font-semibold text-slate-900">Facturas</p>
          {FILTERS.map(([k, l]) => <button key={k} onClick={() => setF(k)} className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors ${f === k ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`} data-testid={`payments-filter-${k}`}>{l}</button>)}
        </div>
        <table className="w-full min-w-[820px] text-left text-sm">
          <thead className="text-[11px] uppercase tracking-wider text-slate-500"><tr><th className="px-5 py-2">Cuenta</th><th>Importe</th><th>Estado</th><th>Fecha</th><th>Vence</th><th className="px-5 text-right">Acciones</th></tr></thead>
          <tbody>{inv.map((i) => (
            <tr key={i.id} className="border-t border-slate-100" data-testid={`payments-invoice-${i.id}`}>
              <td className="px-5 py-3 font-semibold text-slate-900">{i.account || "—"}{i.mode === "test" && <span className="ml-2 text-xs text-slate-400">prueba</span>}</td>
              <td className="tabular-nums">{money(i.amount, i.currency)}</td>
              <td><span className={`rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${ST[i.status] || "bg-slate-100 text-slate-600"}`}>{i.status}</span></td>
              <td>{day(i.created)}</td><td>{day(i.due)}</td>
              <td className="px-5 text-right"><div className="flex justify-end gap-1.5">
                {["pendiente", "vencida"].includes(i.status) && <Button size="sm" onClick={() => charge(i)} disabled={busy === i.id} className="rounded-full" data-testid={`payments-charge-${i.id}`}>{busy === i.id && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}Cobrar ahora</Button>}
                {i.url && <a href={i.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 rounded-full border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50" data-testid={`payments-view-${i.id}`}><ExternalLink className="h-3.5 w-3.5" />Ver</a>}
              </div></td>
            </tr>))}</tbody>
        </table>
        {d && !inv.length && <p className="p-5 text-sm text-slate-500" data-testid="payments-empty">No hay facturas en este filtro.</p>}
      </Panel>
      {link && <LinkDialog acc={link} plans={plans} onClose={() => setLink(null)} />}
    </div>
  );
}
