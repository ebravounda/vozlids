import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Check, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHeader, Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";
import { formatPrice, planOverage } from "@/lib/currency";
import { fmtDate } from "@/lib/constants";
import { ChangePlanDialog } from "@/components/ChangePlan";
import { usePlan } from "@/components/PlanGate";
import { limitLines, PlanBadge, PlanPrice, promoPrice } from "@/components/PlanPrice";

const STATUS = { active: "Activa", past_due: "Pago pendiente", canceled: "Cancelada", trialing: "En prueba" };

function useCheckoutReturn(reload) {
  const [params, setParams] = useSearchParams();
  const [checking, setChecking] = useState(false);
  useEffect(() => {
    const sid = params.get("session_id");
    if (params.get("cancelado")) { toast("Pago cancelado"); setParams({}); }
    if (!sid) return;
    setChecking(true);
    let tries = 0;
    const poll = async () => {
      const r = await api.get(`/billing/status/${sid}`).catch(() => null);
      if (r?.data.payment_status === "paid") { toast.success("¡Pago confirmado! Tu plan ya está activo."); setChecking(false); setParams({}); reload(); return; }
      if (r?.data.status === "expired" || ++tries >= 10) { toast.error("No pudimos confirmar el pago. Revisa tu email o inténtalo de nuevo."); setChecking(false); setParams({}); return; }
      setTimeout(poll, 2000);
    };
    poll();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return checking;
}

const PlanCard = ({ p, cur, current, onBuy, busy, change, pending, currentMinutes }) => (
  <Panel className={`relative flex flex-col p-6 ${current ? "border-emerald-500/60" : promoPrice(p, cur) ? "border-rose-500/70" : p.recommended ? "border-blue-500/70" : ""}`} data-testid={`billing-plan-${p.id}`}>
    {!current && <PlanBadge p={p} currency={cur} />}
    <p className="font-semibold text-white">{p.name}</p>
    <div className="mt-3" data-testid={`billing-plan-price-${p.id}`}><PlanPrice p={p} currency={cur} className="font-display text-3xl font-bold text-white" /></div>
    <p className="mt-1 text-xs text-slate-400">{p.minutes} min incluidos · minuto extra {formatPrice(planOverage(p, cur), cur, 2)}</p>
    <ul className="mt-4 flex-1 space-y-1.5 text-sm text-slate-300"><li className="flex gap-2 font-semibold text-emerald-300" data-testid={`billing-plan-number-${p.id}`}><Check className="h-4 w-4 text-emerald-400" />Número de {cur === "CLP" ? "Chile (+56)" : "España (+34)"} gratis</li>{[...limitLines(p), ...(p.features || [])].map((f) => <li key={f} className="flex gap-2"><Check className="h-4 w-4 text-emerald-400" />{f}</li>)}</ul>
    {current ? <p className="mt-5 text-center text-sm font-semibold text-emerald-300" data-testid={`billing-plan-current-${p.id}`}>Tu plan actual</p>
      : pending ? <p className="mt-5 text-center text-sm font-semibold text-slate-500" data-testid={`billing-plan-pending-${p.id}`}>Cambio programado</p>
      : change ? <Button onClick={() => change(p)} className={`mt-5 rounded-full ${p.minutes > currentMinutes ? "bg-blue-600 text-white hover:bg-blue-700" : ""}`} variant={p.minutes > currentMinutes ? "default" : "outline"} data-testid={`billing-plan-change-${p.id}`}>{p.minutes > currentMinutes ? "Subir a este plan" : "Bajar a este plan"}</Button>
      : <Button onClick={() => onBuy(p.id)} disabled={!!busy} className="mt-5 rounded-full" data-testid={`billing-plan-buy-${p.id}`}>{busy === p.id && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Contratar</Button>}
  </Panel>
);

export default function Billing() {
  const [me, setMe] = useState(null);
  const [plans, setPlans] = useState([]);
  const [busy, setBusy] = useState(null);
  const [target, setTarget] = useState(null);
  const { reload } = usePlan();
  const load = () => { api.get("/billing/me").then((r) => setMe(r.data)); api.get("/public/plans").then((r) => setPlans(r.data)); };
  useEffect(() => { load(); }, []);
  const checking = useCheckoutReturn(load);
  const buy = async (plan_id) => {
    setBusy(plan_id);
    try { const r = await api.post("/billing/checkout", { plan_id, origin_url: window.location.origin }); window.location.href = r.data.checkout_url; }
    catch (e) { toast.error(errMsg(e)); setBusy(null); }
  };
  const cancel = async () => {
    if (!window.confirm("¿Cancelar la suscripción? Seguirá activa hasta el final del periodo pagado.")) return;
    try { await api.post("/billing/cancel"); toast.success("Suscripción cancelada al final del periodo"); load(); } catch (e) { toast.error(errMsg(e)); }
  };
  const portal = async () => {
    try { const r = await api.post("/billing/portal", { origin_url: window.location.origin }); window.location.href = r.data.url; } catch (e) { toast.error(errMsg(e)); }
  };
  const undoChange = async () => { try { await api.delete("/billing/change-plan"); toast.success("Cambio de plan anulado"); load(); } catch (e) { toast.error(errMsg(e)); } };
  if (!me) return null;
  const cur = me.currency;
  return (
    <div className="fade-up">
      <PageHeader eyebrow="Mi plan" title="Suscripción y facturación" desc={`Pago mensual con tarjeta. Precios en ${cur === "CLP" ? "pesos chilenos" : "euros"}, IVA no incluido.`} />
      {checking && <Panel className="mb-6 flex items-center gap-3 text-sm text-slate-200" data-testid="billing-checking"><Loader2 className="h-4 w-4 animate-spin" /> Confirmando tu pago…</Panel>}
      <Panel className="mb-6 flex flex-wrap items-center justify-between gap-4 p-5" data-testid="billing-current">
        <div>
          <p className="text-xs uppercase tracking-widest text-slate-500">Plan actual</p>
          <p className="mt-1 text-lg font-semibold text-white">{me.plan_name || "Sin plan contratado"}{me.billing_status && <span className="ml-2 text-sm font-normal text-slate-400" data-testid="billing-status">· {STATUS[me.billing_status] || me.billing_status}{me.cancel_at_period_end ? " · se cancela al final del periodo" : ""}</span>}</p>
        </div>
        {me.has_subscription && (
          <div className="flex gap-2">
            <Button variant="outline" onClick={portal} className="rounded-full" data-testid="billing-portal-button">Facturas y tarjeta</Button>
            {!me.cancel_at_period_end && <Button variant="ghost" onClick={cancel} className="rounded-full text-rose-300" data-testid="billing-cancel-button">Cancelar suscripción</Button>}
          </div>
        )}
      </Panel>
      {me.pending_plan_id && <Panel className="mb-6 flex flex-wrap items-center justify-between gap-3 border-amber-300 bg-amber-50 p-4 text-sm text-amber-900" data-testid="billing-pending-change">
        <span>Pasarás al plan <b>{plans.find((p) => p.id === me.pending_plan_id)?.name}</b> el {fmtDate(me.pending_plan_at)}. Hasta entonces mantienes tu plan actual.</span>
        <Button size="sm" variant="outline" onClick={undoChange} className="rounded-full" data-testid="billing-pending-undo">Anular cambio</Button>
      </Panel>}
      <div className="grid gap-5 pt-3 md:grid-cols-3">{plans.map((p) => <PlanCard key={p.id} p={p} cur={cur} current={me.plan_id === p.id && me.billing_status === "active"} onBuy={buy} busy={busy}
        change={me.has_subscription && me.billing_status === "active" ? setTarget : null} pending={me.pending_plan_id === p.id} currentMinutes={plans.find((x) => x.id === me.plan_id)?.minutes || 0} />)}</div>
      <ChangePlanDialog plan={target} open={!!target} onClose={() => setTarget(null)} onDone={() => { load(); reload(); }} />
    </div>
  );
}
