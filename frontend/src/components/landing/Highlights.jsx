import { Link } from "react-router-dom";
import { ArrowRight, BellRing, CalendarCheck, CalendarClock, Check, Repeat2, Sparkles, Users } from "lucide-react";
import { AmbiencePreview } from "@/components/AmbiencePreview";

const H = { fontFamily: "Plus Jakarta Sans" };
const TEAM = [
  ["Blanca", "España", "Cálida y cercana", "bg-rose-100 text-rose-700"],
  ["Octavio", "España", "Natural y profesional", "bg-blue-100 text-blue-700"],
  ["Lucía", "España", "Alegre y luminosa", "bg-amber-100 text-amber-700"],
  ["Rafael", "España", "Asesor sereno", "bg-emerald-100 text-emerald-700"],
  ["Verónica", "Latinoamérica", "Cálida, ventas", "bg-violet-100 text-violet-700"],
  ["Rodrigo", "Latinoamérica", "Atención al cliente", "bg-cyan-100 text-cyan-700"],
];

export const AgentTeam = () => (
  <section id="voces" className="vl-reveal scroll-mt-20 border-b border-slate-200 bg-white" data-testid="agent-team">
    <div className="mx-auto grid max-w-6xl items-center gap-14 px-6 py-24 lg:grid-cols-2">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-600">Voces 100% realistas</p>
        <h2 className="mt-3 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl" style={H}>Un equipo de agentes, no un robot</h2>
        <p className="mt-4 text-lg leading-relaxed text-slate-600">Elige a tus ejecutivos entre decenas de voces con acento de España y de Latinoamérica. Respiran, hacen pausas y cambian de tono como una persona: tus clientes no notan la diferencia.</p>
        <ul className="mt-6 space-y-3 text-slate-700">
          {[[Users, "Hasta 5 ejecutivos por agente, cada uno con su nombre y su voz"], [Repeat2, "Se turnan solos en cada llamada: Blanca, Octavio, Lucía…"], [Sparkles, "Voces HD de última generación y ambiente de oficina real"]].map(([I, t]) => (
            <li key={t} className="flex items-start gap-3"><span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-blue-50 text-blue-700"><I className="h-4 w-4" /></span>{t}</li>
          ))}
        </ul>
        <div className="mt-8"><AmbiencePreview demo label="Escuchar una llamada real" testid="agent-team-demo-button" className="!border-slate-300 !bg-white !text-slate-900 shadow-sm hover:!bg-slate-50" /></div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {TEAM.map(([n, where, tone, c]) => (
          <div key={n} className="flex items-center gap-4 rounded-2xl border border-slate-200 bg-white p-4 transition-[transform,box-shadow] hover:-translate-y-0.5 hover:shadow-md" data-testid={`agent-team-${n.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase()}`}>
            <span className={`grid h-12 w-12 shrink-0 place-items-center rounded-full text-lg font-bold ${c}`} style={H}>{n[0]}</span>
            <div className="min-w-0"><p className="font-semibold text-slate-900">{n}</p><p className="truncate text-sm text-slate-500">{tone}</p><p className="text-xs text-slate-400">{where}</p></div>
          </div>
        ))}
      </div>
    </div>
  </section>
);

const SLOTS = [["Lun 10:00", "Laura P. · Primera visita", true], ["Lun 12:30", "Libre", false], ["Mar 17:30", "Javier M. · Revisión", true], ["Jue 19:00", "Ana R. · Agendada por teléfono", true]];

export const OnlineBooking = () => (
  <section id="citas" className="vl-reveal scroll-mt-20 border-b border-slate-200 bg-slate-50" data-testid="online-booking">
    <div className="mx-auto grid max-w-6xl items-center gap-14 px-6 py-24 lg:grid-cols-2">
      <div className="order-2 rounded-2xl border border-slate-200 bg-white p-6 shadow-[0_24px_60px_-28px_rgba(15,23,42,0.35)] lg:order-1" data-testid="online-booking-mock">
        <div className="flex items-center justify-between"><p className="font-semibold text-slate-900" style={H}>Agenda de esta semana</p><span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700">+3 citas hoy</span></div>
        <div className="mt-5 space-y-2">
          {SLOTS.map(([t, w, busy]) => (
            <div key={t} className={`flex items-center gap-4 rounded-xl border p-3 text-sm ${busy ? "border-blue-200 bg-blue-50/60" : "border-dashed border-slate-200"}`}>
              <span className="w-20 font-mono text-xs text-slate-500">{t}</span><span className={busy ? "font-medium text-slate-900" : "text-slate-400"}>{w}</span>
              {busy && <CalendarCheck className="ml-auto h-4 w-4 text-blue-600" />}
            </div>
          ))}
        </div>
      </div>
      <div className="order-1 lg:order-2">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-600">Citas en línea 24/7</p>
        <h2 className="mt-3 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl" style={H}>Tu agenda se llena sola, incluso a las 3 de la mañana</h2>
        <p className="mt-4 text-lg leading-relaxed text-slate-600">El agente mira tus huecos libres en tiempo real y cierra la cita durante la llamada. Tú solo abres el calendario y ves quién viene.</p>
        <ul className="mt-6 grid gap-3 text-slate-700 sm:grid-cols-2">
          {["Reserva en tus huecos libres", "Nunca dos citas a la misma hora", "Recordatorio 24 h antes", "Si dicen «llámame luego», vuelve a llamar", "Vista día, semana y mes", "Aviso por email de cada cita"].map((t) => <li key={t} className="flex items-start gap-2"><Check className="mt-0.5 h-4 w-4 shrink-0 text-blue-600" />{t}</li>)}
        </ul>
        <div className="mt-8 flex flex-wrap gap-4 text-sm">
          <span className="inline-flex items-center gap-2 text-slate-600"><CalendarClock className="h-4 w-4 text-blue-600" /> Disponible las 24 horas, los 365 días</span>
          <span className="inline-flex items-center gap-2 text-slate-600"><BellRing className="h-4 w-4 text-blue-600" /> Menos ausencias</span>
        </div>
        <Link to="/registro" className="group mt-8 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-3 text-sm font-semibold text-white hover:bg-blue-700" data-testid="online-booking-register-button">Quiero mi agenda automática <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" /></Link>
      </div>
    </div>
  </section>
);
