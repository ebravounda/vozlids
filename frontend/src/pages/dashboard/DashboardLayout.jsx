import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { BellRing, Bot, CalendarDays, Code2, CreditCard, Euro, LifeBuoy, LogOut, PhoneCall, PhoneOff, PhoneOutgoing, Plus, Radio, Shield } from "lucide-react";
import { Logo } from "@/components/Common";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { formatPrice } from "@/lib/currency";

const NAV = [
  { to: "/app", label: "Leads y llamadas", icon: PhoneCall, id: "leads", end: true },
  { to: "/app/agentes", label: "Agentes IA", icon: Bot, id: "agents" },
  { to: "/app/llamadas", label: "Llamadas salientes", icon: PhoneOutgoing, id: "outbound" },
  { to: "/app/agenda", label: "Agenda y citas", icon: CalendarDays, id: "agenda" },
  { to: "/app/asistencia", label: "Asistencia técnica", icon: LifeBuoy, id: "support" },
  { to: "/app/no-llamar", label: "No llamar", icon: PhoneOff, id: "donotcall" },
  { to: "/app/api", label: "API desarrolladores", icon: Code2, id: "api" },
  { to: "/app/plan", label: "Mi plan", icon: CreditCard, id: "plan" },
];
const ADMIN_NAV = [
  { to: "/app/admin", label: "Super admin", icon: Shield, id: "superadmin" },
  { to: "/app/costes", label: "Costes y precios", icon: Euro, id: "costs" },
  { to: "/app/telefonia", label: "Telefonía", icon: Radio, id: "settings" },
];

function UsageBadge() {
  const [u, setU] = useState(null);
  useEffect(() => { api.get("/account/usage").then((r) => setU(r.data)).catch(() => {}); }, []);
  if (!u?.plan) return <span />;
  const over = u.minutes_used >= u.plan.minutes;
  return <span data-testid="usage-badge" className={`rounded-full border px-3 py-1 text-xs font-semibold ${over ? "border-rose-500/40 text-rose-300" : "border-slate-700 text-slate-300"}`}>Plan {u.plan.name} ({formatPrice(u.plan.price, u.plan.currency)}/mes): {u.minutes_used} / {u.plan.minutes} min{over && !u.allow_overage ? " · llamadas en pausa" : ""}</span>;
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
  <Link to="/app/asistencia" data-testid="human-request-alert" className="flex items-center justify-center gap-2 bg-rose-500/15 px-4 py-2 text-sm font-semibold text-rose-200 hover:bg-rose-500/25">
    <BellRing className="h-4 w-4 animate-pulse" /> {n === 1 ? "Un cliente quiere hablar con una persona" : `${n} clientes quieren hablar con una persona`}. Llámales cuanto antes →
  </Link>
);

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
    <div className="grain flex min-h-screen bg-[#0B0F17]">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-slate-800 bg-slate-950/80 p-5 md:flex">
        <Link to="/" className="mb-10 px-2"><Logo /></Link>
        <nav className="flex flex-1 flex-col gap-1">
          {(user?.role === "admin" ? [...NAV, ...ADMIN_NAV] : NAV).map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} data-testid={`sidebar-nav-${n.id}`}
              className={({ isActive }) => `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors ${isActive ? "bg-emerald-500/10 text-emerald-300" : "text-slate-400 hover:bg-slate-900 hover:text-white"}`}>
              <n.icon className="h-4 w-4" /> {n.label}
              {n.id === "support" && tickets.open > 0 && <span className="ml-auto rounded-full bg-rose-500 px-2 text-xs font-bold text-white" data-testid="sidebar-support-count">{tickets.open}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="rounded-xl border border-slate-800 p-3">
          <p className="truncate text-sm font-semibold text-white" data-testid="sidebar-business-name">{user?.business_name}</p>
          <p className="truncate text-xs text-slate-500">{user?.email}</p>
          <button onClick={logout} data-testid="logout-button" className="mt-3 inline-flex items-center gap-2 text-xs text-slate-400 hover:text-rose-300">
            <LogOut className="h-3.5 w-3.5" /> Cerrar sesión
          </button>
        </div>
      </aside>
      <div className="relative z-10 flex min-w-0 flex-1 flex-col">
        {user?.impersonating && <ImpersonationBar />}
        {tickets.human > 0 && <HumanAlert n={tickets.human} />}
        <header className="sticky top-0 z-30 flex items-center justify-between gap-3 border-b border-slate-800 bg-slate-950/90 px-5 py-3 backdrop-blur-xl md:px-10">
          <div className="flex items-center gap-3 md:hidden"><Logo /></div>
          {user?.role === "admin" ? <Link to="/app/telefonia" data-testid="telephony-status-badge"
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold ${tel?.configured ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300" : "border-amber-500/30 bg-amber-500/10 text-amber-300"}`}>
            <span className={`h-2 w-2 rounded-full ${tel?.configured ? "bg-emerald-400 animate-pulse" : "bg-amber-400"}`} />
            {tel?.configured ? "Telefonía conectada" : "Telefonía sin configurar"}
          </Link> : <UsageBadge />}
          <Link to="/app/agentes/nuevo" data-testid="header-create-agent-button" className="inline-flex items-center gap-2 rounded-full bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 transition-colors hover:bg-emerald-400">
            <Plus className="h-4 w-4" /> Crear agente
          </Link>
        </header>
        <nav className="flex gap-1 overflow-x-auto border-b border-slate-800 px-3 py-2 md:hidden">
          {(user?.role === "admin" ? [...NAV, ...ADMIN_NAV] : NAV).map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} data-testid={`mobile-nav-${n.id}`} className={({ isActive }) => `whitespace-nowrap rounded-lg px-3 py-1.5 text-xs ${isActive ? "bg-emerald-500/10 text-emerald-300" : "text-slate-400"}`}>{n.label}</NavLink>
          ))}
        </nav>
        <main className="mx-auto w-full max-w-7xl flex-1 px-5 py-10 md:px-10">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
