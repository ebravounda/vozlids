import { createContext, useContext, useEffect, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { Activity, AlertTriangle, Euro, Lock, Phone, Radio, Shield, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { ChangePlanDialog, useNextPlan } from "@/components/ChangePlan";

const Ctx = createContext({ u: null, reload: () => {} });
export const FEATURE_INFO = {
  outbound: ["Llamadas salientes", "Lanza campañas de seguimiento, cobros y recordatorios a tus clientes."],
  api: ["API para desarrolladores", "Conecta VozLeads con tu CRM, ERP o app y recibe los resultados por webhook."],
  widget: ["Botón para tu web", "Un botón en tu web para que tus visitantes reciban una llamada en segundos."],
  agenda_pro: ["Agenda avanzada", "Sincroniza Google Calendar y envía recordatorios automáticos de cita."],
  premium_voices: ["Voces ultra naturales HD", "Las voces más humanas, casi imposibles de distinguir de una persona."],
  multilang: ["Atención en varios idiomas", "El agente pregunta el idioma y pasa la llamada a un ejecutivo nativo: inglés, portugués, francés, catalán, italiano o alemán."],
  ambience: ["Ambiente de oficina", "Sonido de oficina de fondo para que la llamada suene más real."],
};

export function PlanProvider({ path, children }) {
  const [u, setU] = useState(null);
  const reload = () => api.get("/account/usage").then((r) => setU(r.data)).catch(() => {});
  useEffect(() => { reload(); }, [path]);
  return <Ctx.Provider value={{ u, reload }}>{children}</Ctx.Provider>;
}

export const usePlan = () => useContext(Ctx);
export const useFeature = (f) => { const { u } = usePlan(); return !u || u.is_admin || u.limits?.[f] !== false; };

export function LockedCard({ f, compact = false }) {
  const [title, desc] = FEATURE_INFO[f];
  return (
    <div className={`rounded-2xl border border-dashed border-slate-300 bg-white text-center ${compact ? "p-6" : "mx-auto max-w-xl p-10"}`} data-testid={`locked-${f}`}>
      <span className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-slate-100"><Lock className="h-5 w-5 text-slate-500" /></span>
      <p className="mt-4 text-lg font-bold text-slate-900">{title}</p>
      <p className="mt-1 text-sm text-slate-500">{desc}</p>
      <p className="mt-3 text-sm font-medium text-slate-700">No está incluido en tu plan actual.</p>
      <Link to="/app/plan" className="mt-5 inline-flex items-center gap-2 rounded-full bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-700" data-testid={`locked-${f}-upgrade`}><Sparkles className="h-4 w-4" />Mejorar plan</Link>
    </div>
  );
}

export function Gate({ f, children }) {
  const { u } = usePlan();
  if (!u) return null;
  return allowed(u, f) ? children : <div className="py-10"><LockedCard f={f} /></div>;
}
const allowed = (u, f) => u.is_admin || u.limits?.[f] !== false;

const pctOf = (u) => (u?.plan?.minutes ? Math.min(100, Math.round((100 * u.minutes_used) / u.plan.minutes)) : 0);
const tone = (p) => (p >= 100 ? "bg-rose-500" : p >= 80 ? "bg-amber-500" : "bg-blue-600");

export function UsageMeter() {
  const { u } = usePlan();
  if (!u?.plan || u.is_admin) return null;
  const p = pctOf(u);
  return (
    <Link to="/app/plan" className="mt-3 block shrink-0 rounded-xl border border-slate-200 bg-white p-3 hover:border-slate-300" data-testid="usage-meter">
      <div className="flex items-baseline justify-between text-xs"><span className="font-semibold text-slate-700">Plan {u.plan.name}</span><span className="font-mono text-slate-500" data-testid="usage-meter-pct">{p}%</span></div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100"><div className={`h-full rounded-full transition-[width] duration-700 ${tone(p)}`} style={{ width: `${Math.max(2, p)}%` }} /></div>
      <p className="mt-1.5 text-[11px] text-slate-500" data-testid="usage-meter-text">{Number(u.minutes_used).toLocaleString("es-ES")} de {u.plan.minutes.toLocaleString("es-ES")} min este mes</p>
    </Link>
  );
}

export function UsageBanner() {
  const { u, reload } = usePlan();
  const next = useNextPlan(u);
  const [open, setOpen] = useState(false);
  if (!u?.plan || u.is_admin) return null;
  const p = pctOf(u);
  if (p < 80) return null;
  const full = p >= 100;
  const msg = full ? (u.allow_overage ? "Has usado todos los minutos de tu plan: los minutos extra se cobran aparte." : "Has usado todos los minutos de tu plan: las llamadas están en pausa.")
    : `Has usado el ${p}% de los minutos de tu plan este mes.`;
  const cls = `flex w-full items-center justify-center gap-2 px-4 py-2 text-sm font-semibold ${full ? "bg-rose-50 text-rose-700 hover:bg-rose-100" : "bg-amber-50 text-amber-800 hover:bg-amber-100"}`;
  if (!next || !u.has_subscription) return <Link to="/app/plan" className={cls} data-testid="usage-banner"><AlertTriangle className="h-4 w-4" />{msg} Mejorar plan →</Link>;
  return (
    <>
      <button onClick={() => setOpen(true)} className={cls} data-testid="usage-banner"><AlertTriangle className="h-4 w-4" />{msg} <span className="underline" data-testid="usage-banner-upgrade">Subir a {next.name} ({next.minutes.toLocaleString("es-ES")} min) →</span></button>
      <ChangePlanDialog plan={next} open={open} onClose={() => setOpen(false)} onDone={reload} />
    </>
  );
}

const ADMIN_TABS = [["/app/admin", "Cuentas y planes", Shield, "superadmin"], ["/app/monitor", "Monitor en vivo", Activity, "monitor"], ["/app/costes", "Costes y precios", Euro, "costs"], ["/app/lineas", "Líneas", Phone, "lines"], ["/app/telefonia", "Telefonía", Radio, "settings"]];
export const ADMIN_PATHS = ADMIN_TABS.map((t) => t[0]);

export function AdminTabs() {
  return (
    <div className="mb-8 flex gap-1 overflow-x-auto rounded-xl border border-slate-200 bg-white p-1" data-testid="admin-tabs">
      {ADMIN_TABS.map(([to, label, I, id]) => (
        <NavLink key={to} to={to} data-testid={`admin-tab-${id}`} className={({ isActive }) => `inline-flex items-center gap-2 whitespace-nowrap rounded-lg px-4 py-2 text-sm font-semibold ${isActive ? "bg-slate-900 text-white" : "text-slate-500 hover:bg-slate-50 hover:text-slate-900"}`}><I className="h-4 w-4" />{label}</NavLink>
      ))}
    </div>
  );
}
