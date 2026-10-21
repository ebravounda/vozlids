import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { Loader2, MousePointerClick, BellRing, Bot, CalendarDays, Code2, CreditCard, Hash, LifeBuoy, Lock, LogOut, PhoneCall, PhoneOff, PhoneOutgoing, Plus, Shield } from "lucide-react";
import { Logo } from "@/components/Common";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { ADMIN_PATHS, AdminTabs, PlanProvider, UsageBanner, UsageMeter, useFeature, usePlan } from "@/components/PlanGate";
import { KycBanner } from "@/components/kyc/KycPanel";

const NAV = [
  { to: "/app", label: "Leads y llamadas", icon: PhoneCall, id: "leads", end: true },
  { to: "/app/agentes", label: "Agentes IA", icon: Bot, id: "agents" },
  { to: "/app/llamadas", label: "Llamadas salientes", icon: PhoneOutgoing, id: "outbound" },
  { to: "/app/agenda", label: "Agenda y citas", icon: CalendarDays, id: "agenda" },
  { to: "/app/asistencia", label: "Asistencia técnica", icon: LifeBuoy, id: "support" },
  { to: "/app/numero", label: "Mi número", icon: Hash, id: "mynumber" },
  { to: "/app/boton-web", label: "Botón para tu web", icon: MousePointerClick, id: "webwidget" },
  { to: "/app/no-llamar", label: "No llamar", icon: PhoneOff, id: "donotcall" },
  { to: "/app/api", label: "API desarrolladores", icon: Code2, id: "api" },
  { to: "/app/privacidad", label: "Privacidad (RGPD)", icon: Lock, id: "privacy" },
  { to: "/app/plan", label: "Mi plan", icon: CreditCard, id: "plan" },
];
const ADMIN_NAV = [{ to: "/app/admin", label: "Super admin", icon: Shield, id: "superadmin", admin: true }];
const LOCK = { outbound: "outbound", webwidget: "widget", api: "api" };

function CreateAgentButton() {
  const { u } = usePlan();
  const full = u && !u.is_admin && u.limits?.max_agents > 0 && u.agents >= u.limits.max_agents;
  return (
    <Link to={full ? "/app/plan" : "/app/agentes/nuevo"} data-testid="header-create-agent-button" title={full ? "Has llegado al máximo de agentes de tu plan" : undefined}
      className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold shadow-sm transition-[transform,background-color,box-shadow] hover:-translate-y-0.5 hover:shadow-md ${full ? "border border-slate-300 bg-white text-slate-700" : "bg-blue-600 text-white hover:bg-blue-700"}`}>
      {full ? <><Lock className="h-4 w-4" /> <span className="whitespace-nowrap">Mejorar plan</span></> : <><Plus className="h-4 w-4" /> <span className="whitespace-nowrap">Crear agente</span></>}
    </Link>
  );
}

function NavItem({ n, tickets, path }) {
  const ok = useFeature(LOCK[n.id] || "outbound");
  const active = n.admin && ADMIN_PATHS.includes(path);
  return (
    <NavLink to={n.to} end={n.end} data-testid={`sidebar-nav-${n.id}`}
      className={({ isActive }) => `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors ${isActive || active ? "bg-blue-50 text-blue-700 shadow-[inset_3px_0_0_#2563EB]" : "text-slate-500 hover:bg-slate-50 hover:text-slate-900"}`}>
      <n.icon className="h-4 w-4" /> {n.label}
      {LOCK[n.id] && !ok && <Lock className="ml-auto h-3.5 w-3.5 text-slate-400" data-testid={`sidebar-lock-${n.id}`} />}
      {n.id === "support" && tickets.open > 0 && <span className="ml-auto rounded-full bg-rose-500 px-2 text-xs font-bold text-white" data-testid="sidebar-support-count">{tickets.open}</span>}
    </NavLink>
  );
}

function useOpenTickets(path) {
  const [c, setC] = useState({ open: 0, human: 0 });
  useEffect(() => {
    const load = () => api.get("/support-tickets/open-count").then((r) => setC(r.data)).catch(() => {});
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [path]);
  return c;
}

const HumanAlert = ({ n }) => (
  <Link to="/app/asistencia" data-testid="human-request-alert" className="flex items-center justify-center gap-2 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-700 hover:bg-rose-100">
    <BellRing className="h-4 w-4 animate-pulse" /> {n === 1 ? "Un cliente quiere hablar con una persona" : `${n} clientes quieren hablar con una persona`}. Llámales cuanto antes →
  </Link>
);

function ProvisioningBar() {
  const [st, setSt] = useState(null);
  useEffect(() => { api.get("/my-number").then((r) => setSt(r.data.status)).catch(() => {}); }, []);
  if (!["pendiente", "comprando", "error"].includes(st)) return null;
  return (
    <Link to="/app/numero" className="flex items-center justify-center gap-2 bg-amber-50 px-4 py-2 text-sm font-semibold text-amber-800 hover:bg-amber-100" data-testid="provisioning-bar">
      <Loader2 className="h-4 w-4 animate-spin" /> Aprovisionando línea · Recibirás un email cuando tu línea esté lista para operar
    </Link>
  );
}

function ImpersonationBar() {
  const stop = async () => { await api.post("/auth/stop-impersonation"); window.location.href = "/app/admin"; };
  return (
    <div className="flex items-center justify-center gap-4 bg-amber-500 px-4 py-2 text-sm font-semibold text-slate-950" data-testid="impersonation-bar">
      Estás dentro de una cuenta de cliente como super admin.
      <button onClick={stop} className="rounded-full bg-slate-950 px-3 py-1 text-xs text-amber-200" data-testid="stop-impersonation-button">Volver a mi cuenta</button>
    </div>
  );
}

export default function DashboardLayout() {
  const { user, logout } = useAuth();
  const [tel, setTel] = useState(null);
  const location = useLocation();
  const tickets = useOpenTickets(location.pathname);

  useEffect(() => {
    if (user?.role === "admin") api.get("/telephony/status").then((r) => setTel(r.data)).catch(() => {});
  }, [location.pathname, user?.role]);

  return (
    <PlanProvider path={location.pathname}>
    <div className="app-light flex min-h-screen bg-[#F8FAFC] text-slate-700">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-slate-200 bg-white p-5 md:flex">
        <Link to="/" className="mb-6 shrink-0 px-2"><Logo /></Link>
        <p className="mb-2 shrink-0 px-3 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Menú</p>
        <nav className="-mx-2 flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto overscroll-contain px-2 pb-3 [scrollbar-width:thin]" data-testid="sidebar-nav">
          {(user?.role === "admin" ? [...NAV, ...ADMIN_NAV] : NAV).map((n) => <NavItem key={n.to} n={n} tickets={tickets} path={location.pathname} />)}
        </nav>
        <UsageMeter />
        <div className="mt-3 shrink-0 rounded-xl border border-slate-200 bg-slate-50 p-3">
          <p className="truncate text-sm font-semibold text-white" data-testid="sidebar-business-name">{user?.business_name}</p>
          <p className="truncate text-xs text-slate-500">{user?.email}</p>
          <button onClick={logout} data-testid="logout-button" className="mt-3 inline-flex items-center gap-2 text-xs text-slate-400 hover:text-rose-600">
            <LogOut className="h-3.5 w-3.5" /> Cerrar sesión
          </button>
        </div>
      </aside>
      <div className="relative z-10 flex min-w-0 flex-1 flex-col">
        {user?.impersonating && <ImpersonationBar />}
        {tickets.human > 0 && <HumanAlert n={tickets.human} />}
        {user?.role !== "admin" && <ProvisioningBar />}
        {user?.role !== "admin" && <KycBanner />}
        <UsageBanner />
        <header className="sticky top-0 z-30 flex items-center justify-between gap-3 border-b border-slate-200 bg-white/80 px-5 py-3 backdrop-blur-xl md:px-10">
          <div className="flex items-center gap-3 md:hidden"><Logo /></div>
          {user?.role === "admin" ? <Link to="/app/telefonia" data-testid="telephony-status-badge"
            className={`hidden items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold sm:inline-flex ${tel?.configured ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300" : "border-amber-500/30 bg-amber-500/10 text-amber-300"}`}>
            <span className={`h-2 w-2 rounded-full ${tel?.configured ? "bg-emerald-400 animate-pulse" : "bg-amber-400"}`} />
            {tel?.configured ? "Telefonía conectada" : "Telefonía sin configurar"}
          </Link> : <span />}
          <CreateAgentButton />
        </header>
        <nav className="flex gap-1 overflow-x-auto border-b border-slate-800 px-3 py-2 md:hidden">
          {(user?.role === "admin" ? [...NAV, ...ADMIN_NAV] : NAV).map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} data-testid={`mobile-nav-${n.id}`} className={({ isActive }) => `whitespace-nowrap rounded-lg px-3 py-1.5 text-xs ${isActive ? "bg-blue-50 text-blue-700" : "text-slate-500"}`}>{n.label}</NavLink>
          ))}
        </nav>
        <main className="mx-auto w-full max-w-7xl flex-1 px-5 py-10 md:px-10">
          {user?.role === "admin" && ADMIN_PATHS.includes(location.pathname) && <AdminTabs />}
          <div key={location.pathname} className="fade-up"><Outlet /></div>
        </main>
      </div>
    </div>
    </PlanProvider>
  );
}
