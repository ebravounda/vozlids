import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { Bot, CalendarDays, LogOut, PhoneCall, PhoneOff, Plus, Radio } from "lucide-react";
import { Logo } from "@/components/Common";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";

const NAV = [
  { to: "/app", label: "Leads y llamadas", icon: PhoneCall, id: "leads", end: true },
  { to: "/app/agentes", label: "Agentes IA", icon: Bot, id: "agents" },
  { to: "/app/agenda", label: "Agenda y citas", icon: CalendarDays, id: "agenda" },
  { to: "/app/no-llamar", label: "No llamar", icon: PhoneOff, id: "donotcall" },
  { to: "/app/telefonia", label: "Telefonía", icon: Radio, id: "settings" },
];

export default function DashboardLayout() {
  const { user, logout } = useAuth();
  const [tel, setTel] = useState(null);
  const location = useLocation();

  useEffect(() => {
    api.get("/telephony/status").then((r) => setTel(r.data)).catch(() => {});
  }, [location.pathname]);

  return (
    <div className="grain flex min-h-screen bg-[#0B0F17]">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-slate-800 bg-slate-950/80 p-5 md:flex">
        <Link to="/" className="mb-10 px-2"><Logo /></Link>
        <nav className="flex flex-1 flex-col gap-1">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} data-testid={`sidebar-nav-${n.id}`}
              className={({ isActive }) => `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors ${isActive ? "bg-emerald-500/10 text-emerald-300" : "text-slate-400 hover:bg-slate-900 hover:text-white"}`}>
              <n.icon className="h-4 w-4" /> {n.label}
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
        <header className="sticky top-0 z-30 flex items-center justify-between gap-3 border-b border-slate-800 bg-slate-950/90 px-5 py-3 backdrop-blur-xl md:px-10">
          <div className="flex items-center gap-3 md:hidden"><Logo /></div>
          <Link to="/app/telefonia" data-testid="telephony-status-badge"
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold ${tel?.configured ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300" : "border-amber-500/30 bg-amber-500/10 text-amber-300"}`}>
            <span className={`h-2 w-2 rounded-full ${tel?.configured ? "bg-emerald-400 animate-pulse" : "bg-amber-400"}`} />
            {tel?.configured ? "Telefonía conectada (Vapi + Zadarma)" : "Telefonía sin configurar"}
          </Link>
          <Link to="/app/agentes/nuevo" data-testid="header-create-agent-button" className="inline-flex items-center gap-2 rounded-full bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 transition-colors hover:bg-emerald-400">
            <Plus className="h-4 w-4" /> Crear agente
          </Link>
        </header>
        <nav className="flex gap-1 overflow-x-auto border-b border-slate-800 px-3 py-2 md:hidden">
          {NAV.map((n) => (
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
