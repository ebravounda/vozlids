import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { ArrowDown, ArrowUp, Loader2 } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { api, errMsg } from "@/lib/api";
import { formatPrice } from "@/lib/currency";
import { fmtDate } from "@/lib/constants";

export function ChangePlanDialog({ plan, open, onClose, onDone }) {
  const [pv, setPv] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!open || !plan) return;
    setPv(null); setErr("");
    api.post("/billing/change-plan/preview", { plan_id: plan.id }).then((r) => setPv(r.data)).catch((e) => setErr(errMsg(e)));
  }, [open, plan]);
  const confirm = async () => {
    setBusy(true);
    try {
      const r = await api.post("/billing/change-plan", { plan_id: plan.id });
      toast.success(r.data.applied ? `¡Listo! Ya estás en el plan ${r.data.plan}` : `Cambiarás al plan ${r.data.plan} el ${fmtDate(r.data.effective_at)}`);
      onDone?.(); onClose();
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const up = pv?.direction === "up";
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="app-light max-w-md bg-white text-slate-700" data-testid="change-plan-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-slate-900">{pv && (up ? <ArrowUp className="h-5 w-5 text-blue-600" /> : <ArrowDown className="h-5 w-5 text-slate-500" />)}Cambiar al plan {plan?.name}</DialogTitle>
          <DialogDescription className="text-slate-500">{plan?.minutes?.toLocaleString("es-ES")} minutos al mes</DialogDescription>
        </DialogHeader>
        {!pv && !err && <Loader2 className="mx-auto my-6 h-6 w-6 animate-spin text-slate-400" />}
        {err && <div className="space-y-4" data-testid="change-plan-error"><p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">{err}</p>
          <Link to="/app/plan" onClick={onClose} className="inline-block text-sm font-semibold text-blue-600">Ver planes →</Link></div>}
        {pv && (
          <div className="space-y-4" data-testid="change-plan-summary">
            {up ? <>
              <div className="rounded-xl bg-blue-50 p-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-blue-700">Pagas hoy</p>
                <p className="mt-1 text-3xl font-bold text-slate-900" data-testid="change-plan-due">{formatPrice(pv.due_now, pv.currency, 2)}</p>
                <p className="mt-1 text-xs text-slate-600">Solo la diferencia por los días que quedan de este mes, con tu tarjeta guardada.</p>
              </div>
              <p className="text-sm text-slate-600">Los <b>{pv.minutes.toLocaleString("es-ES")} minutos</b> y las funciones del plan se activan al momento. Después pagarás <b>{formatPrice(pv.new_price, pv.currency)}/mes</b>.</p>
            </> : <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-600" data-testid="change-plan-down-info">El cambio se aplica en tu próxima renovación{pv.effective_at ? <>, el <b>{fmtDate(pv.effective_at)}</b></> : ""}. Hasta entonces mantienes tu plan actual. Después pagarás <b>{formatPrice(pv.new_price, pv.currency)}/mes</b>. Sin devoluciones.</p>}
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={onClose} data-testid="change-plan-cancel">Cancelar</Button>
              <Button onClick={confirm} disabled={busy} className="rounded-full bg-blue-600 text-white hover:bg-blue-700" data-testid="change-plan-confirm">{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}{up ? "Confirmar y pagar" : "Confirmar cambio"}</Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function useNextPlan(u) {
  const [plans, setPlans] = useState([]);
  useEffect(() => { if (u?.plan) api.get("/public/plans").then((r) => setPlans(r.data)).catch(() => {}); }, [u?.plan_id]); // eslint-disable-line react-hooks/exhaustive-deps
  return plans.filter((p) => p.minutes > (u?.plan?.minutes || 0)).sort((a, b) => a.minutes - b.minutes)[0];
}
