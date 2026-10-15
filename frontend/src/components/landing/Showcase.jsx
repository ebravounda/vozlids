import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, BarChart3, CalendarDays, Check, Code2, Lock, MousePointerClick, PhoneCall } from "lucide-react";

const H = { fontFamily: "Plus Jakarta Sans" };
const Frame = ({ children, url }) => (
  <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[0_40px_90px_-40px_rgba(15,23,42,0.45)]">
    <div className="flex items-center gap-2 border-b border-slate-100 bg-slate-50 px-4 py-2.5">
      {["bg-rose-300", "bg-amber-300", "bg-emerald-300"].map((c) => <span key={c} className={`h-2.5 w-2.5 rounded-full ${c}`} />)}
      <span className="ml-3 rounded-md bg-white px-3 py-0.5 font-mono text-[11px] text-slate-400">vozleads.com/app/{url}</span>
    </div>
    <div className="p-5">{children}</div>
  </div>
);

const LEADS = [["Laura Pérez", "Cita agendada", 86, "bg-blue-50 text-blue-700"], ["Marcos Gil", "Calificado", 72, "bg-emerald-50 text-emerald-700"], ["Ana Torres", "Llamando…", null, "bg-cyan-50 text-cyan-700"], ["Jorge Ruiz", "Sin respuesta", 0, "bg-slate-100 text-slate-500"], ["Elena Sanz", "Pide hablar con alguien", 64, "bg-amber-50 text-amber-700"]];
const LeadsMock = () => (
  <Frame url="leads">
    <div className="mb-4 grid grid-cols-3 gap-3">{[["Leads hoy", "38"], ["Citas", "11"], ["Respuesta media", "14 s"]].map(([k, v]) => <div key={k} className="rounded-xl bg-slate-50 p-3"><p className="text-[11px] text-slate-500">{k}</p><p className="text-xl font-bold text-slate-900" style={H}>{v}</p></div>)}</div>
    <div className="divide-y divide-slate-100 text-sm">{LEADS.map(([n, s, sc, c]) => (
      <div key={n} className="flex items-center justify-between gap-3 py-2.5"><span className="font-medium text-slate-800">{n}</span>
        <span className="flex items-center gap-3">{sc != null && <span className="hidden h-1.5 w-20 overflow-hidden rounded-full bg-slate-100 sm:block"><span className="block h-full rounded-full bg-gradient-to-r from-amber-400 to-emerald-500" style={{ width: `${sc}%` }} /></span>}<span className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${c}`}>{s}</span></span></div>
    ))}</div>
  </Frame>
);

const EV = [[0, 1, 2, "Laura P.", "bg-blue-50 border-blue-300 text-blue-900"], [1, 3, 2, "Consulta laboral", "bg-blue-50 border-blue-300 text-blue-900"], [2, 0, 3, "Clase de prueba", "bg-emerald-50 border-emerald-300 text-emerald-900"], [3, 4, 2, "Marcos G.", "bg-blue-50 border-blue-300 text-blue-900"], [4, 2, 2, "Revisión", "bg-emerald-50 border-emerald-300 text-emerald-900"], [1, 6, 2, "Ana T.", "bg-blue-50 border-blue-300 text-blue-900"]];
const AgendaMock = () => (
  <Frame url="agenda">
    <div className="mb-3 flex items-center justify-between"><p className="font-bold text-slate-900" style={H}>Semana · 11 citas</p><span className="rounded-full bg-slate-100 p-0.5 text-[11px]"><span className="rounded-full px-2 text-slate-500">Día</span><span className="rounded-full bg-white px-2 font-semibold text-slate-900 shadow-sm">Semana</span><span className="rounded-full px-2 text-slate-500">Mes</span></span></div>
    <div className="grid grid-cols-5 gap-px overflow-hidden rounded-xl border border-slate-200 bg-slate-200 text-[11px]">
      {["Lun 12", "Mar 13", "Mié 14", "Jue 15", "Vie 16"].map((d, i) => (
        <div key={d} className="bg-white">
          <p className={`border-b border-slate-100 py-1.5 text-center font-semibold ${i === 3 ? "text-blue-600" : "text-slate-500"}`}>{d}</p>
          <div className="relative h-48">{EV.filter((e) => e[0] === i).map(([, top, h, t, c]) => <span key={t} className={`absolute inset-x-1 truncate rounded-md border-l-[3px] px-1.5 py-1 font-semibold ${c}`} style={{ top: top * 24 + 4, height: h * 22 }}>{t}</span>)}
            {i === 3 && <span className="absolute inset-x-0 top-[104px] h-px bg-rose-500" />}</div>
        </div>
      ))}
    </div>
    <p className="mt-3 text-xs text-slate-500">Arrastra para mover · clic en un hueco para crear · el agente solo ofrece huecos libres</p>
  </Frame>
);

const ResultMock = () => (
  <Frame url="leads/laura-perez">
    <div className="flex items-center justify-between"><div><p className="font-bold text-slate-900" style={H}>Laura Pérez</p><p className="font-mono text-xs text-slate-500">+34 6•• ••• 412 · 01:12</p></div><span className="rounded-full bg-blue-50 px-2.5 py-0.5 text-[11px] font-semibold text-blue-700">Cita agendada</span></div>
    <div className="mt-4 flex h-9 items-center gap-[3px] rounded-xl bg-slate-50 px-3">{Array.from({ length: 48 }).map((_, i) => <span key={i} className="w-[3px] rounded-full bg-blue-500/70" style={{ height: 6 + ((i * 29) % 22) }} />)}</div>
    <p className="mt-4 text-[11px] font-semibold uppercase tracking-widest text-blue-600">Resumen IA</p>
    <p className="mt-1 text-sm text-slate-600">Interesada en primera visita de ortodoncia invisible. Prefiere mañanas. Cita confirmada el jueves 10:30.</p>
    <div className="mt-4 flex justify-between text-xs"><span className="text-slate-500">Interés</span><span className="font-mono font-semibold text-slate-900">86 %</span></div>
    <div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full w-[86%] rounded-full bg-gradient-to-r from-amber-400 to-emerald-500" /></div>
  </Frame>
);

const WidgetMock = () => (
  <Frame url="boton-web">
    <div className="grid grid-cols-4 gap-2 text-center">{[["Visitas", "2.140"], ["Abren", "312"], ["Envían", "96"], ["Citas", "31"]].map(([k, v], i) => <div key={k} className="rounded-xl bg-slate-50 p-2.5"><p className="text-[11px] text-slate-500">{k}</p><p className="font-bold text-slate-900" style={H}>{v}</p><div className="mx-auto mt-1.5 h-1 rounded-full bg-blue-600" style={{ width: `${100 - i * 22}%` }} /></div>)}</div>
    <div className="relative mt-4 h-40 rounded-xl border border-dashed border-slate-300 bg-[repeating-linear-gradient(0deg,#F8FAFC_0_18px,#fff_18px_36px)]">
      <div className="absolute bottom-3 right-3 w-52 rounded-xl border border-slate-200 bg-white p-3 shadow-lg"><p className="text-xs font-bold text-slate-900">¿Te llamamos ahora?</p><div className="mt-2 h-7 rounded-md border border-slate-200" /><div className="mt-2 flex h-7 items-center justify-center rounded-md bg-blue-600 text-[11px] font-semibold text-white">Llamadme en 30 s</div></div>
    </div>
    <p className="mt-3 font-mono text-[11px] text-slate-500">{'<script src="vozleads.com/widget.js" data-id="…">'}</p>
  </Frame>
);

const ApiMock = () => (
  <Frame url="api">
    <pre className="overflow-x-auto rounded-xl bg-slate-900 p-4 font-mono text-[11px] leading-relaxed text-slate-200">{`POST /v1/calls            → 202 queued
{ "agent_id": "…", "phone": "+34612345678",
  "type": "recordatorio", "legal_basis": "contract" }

webhook  call.completed   ✓ firmado HMAC-SHA256
{ "status": "completed", "appointment_booked": true,
  "interest_score": 86, "summary": "…" }`}</pre>
    <div className="mt-3 flex flex-wrap gap-2">{["Claves sandbox y producción", "Historial por clave", "Idempotencia", "OpenAPI 3.1"].map((t) => <span key={t} className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-semibold text-slate-600">{t}</span>)}</div>
  </Frame>
);

const PrivacyMock = () => (
  <Frame url="privacidad">
    <p className="font-bold text-slate-900" style={H}>Borrado automático de grabaciones</p>
    <div className="mt-3 flex flex-wrap gap-2">{["Nunca", "30 días", "90 días", "180 días", "1 año"].map((d) => <span key={d} className={`rounded-full border px-3 py-1 text-xs ${d === "90 días" ? "border-blue-500 bg-blue-50 font-semibold text-blue-700" : "border-slate-200 text-slate-500"}`}>{d}</span>)}</div>
    <div className="mt-5 rounded-xl bg-slate-50 p-3 text-sm"><p className="font-semibold text-slate-800">Solicitud de un contacto</p><p className="mt-1 font-mono text-xs text-slate-500">+34 6•• ••• 412</p>
      <div className="mt-3 flex gap-2"><span className="rounded-full border border-slate-300 bg-white px-3 py-1 text-xs font-semibold text-slate-700">Exportar datos</span><span className="rounded-full border border-rose-300 bg-white px-3 py-1 text-xs font-semibold text-rose-600">Borrar datos</span></div></div>
    <p className="mt-3 text-xs text-slate-500">Lista “No llamar”, horario legal por país y base jurídica en cada llamada.</p>
  </Frame>
);

const TABS = [
  ["leads", PhoneCall, "Leads y llamadas", "Cada lead, llamado en segundos", ["Llamada automática al recibir un formulario", "Grabación, transcripción y resumen de cada conversación", "Puntuación de interés para atender primero a quien va a comprar"], LeadsMock],
  ["agenda", CalendarDays, "Agenda", "Tu calendario se llena solo", ["El agente consulta tus huecos reales y reserva en la llamada", "Vista día, semana y mes; arrastra para mover citas", "Confirmación por email al cliente y a tu equipo"], AgendaMock],
  ["resultados", BarChart3, "Resultados", "Sabes qué pasó en cada llamada", ["Escucha la grabación o lee la transcripción completa", "Resumen y respuestas a tus preguntas de calificación", "Aviso inmediato si el cliente pide hablar con una persona"], ResultMock],
  ["widget", MousePointerClick, "Botón web", "Convierte visitas en llamadas", ["Un botón “Te llamamos ahora” para tu web en 1 minuto", "Embudo completo: visitas, aperturas, envíos y citas", "Funciona con WordPress, Wix, Shopify o cualquier web"], WidgetMock],
  ["api", Code2, "API y webhooks", "Conecta tu CRM o ERP", ["API REST con sandbox gratuito para probar", "Webhooks firmados con el resultado de cada llamada", "Historial de peticiones y permisos por clave"], ApiMock],
  ["rgpd", Lock, "Privacidad", "RGPD resuelto desde el primer día", ["Exporta o borra todos los datos de un contacto en un clic", "Borrado automático de grabaciones en el plazo que elijas", "Horario legal y lista de exclusión incluidos"], PrivacyMock],
];

export function PlatformTour() {
  const [tab, setTab] = useState("leads");
  const [auto, setAuto] = useState(true);
  useEffect(() => {
    if (!auto) return undefined;
    const t = setInterval(() => setTab((c) => TABS[(TABS.findIndex((x) => x[0] === c) + 1) % TABS.length][0]), 6000);
    return () => clearInterval(t);
  }, [auto]);
  const [, , , title, points, Mock] = TABS.find((x) => x[0] === tab);
  return (
    <section id="plataforma" className="vl-reveal scroll-mt-20 border-b border-slate-200 bg-white" data-testid="platform-tour">
      <div className="mx-auto max-w-6xl px-6 py-24">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-600">La plataforma</p>
        <h2 className="mt-3 max-w-3xl text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl" style={H}>Todo lo que necesitas para no perder ni un cliente, en un solo panel</h2>
        <div className="mt-10 flex gap-2 overflow-x-auto pb-2" role="tablist">
          {TABS.map(([id, I, label]) => (
            <button key={id} role="tab" aria-selected={tab === id} onClick={() => { setTab(id); setAuto(false); }}
              className={`flex shrink-0 items-center gap-2 rounded-full border px-4 py-2 text-sm font-semibold transition-colors ${tab === id ? "border-blue-600 bg-blue-600 text-white" : "border-slate-200 text-slate-600 hover:border-slate-300 hover:text-slate-900"}`} data-testid={`tour-tab-${id}`}>
              <I className="h-4 w-4" />{label}
            </button>
          ))}
        </div>
        <div key={tab} className="fade-up mt-10 grid items-center gap-12 lg:grid-cols-[1fr_1.25fr]" data-testid={`tour-panel-${tab}`}>
          <div>
            <h3 className="text-2xl font-bold text-slate-900 sm:text-3xl" style={H}>{title}</h3>
            <ul className="mt-6 space-y-3">{points.map((p) => <li key={p} className="flex gap-3 text-slate-700"><Check className="mt-0.5 h-5 w-5 shrink-0 text-blue-600" />{p}</li>)}</ul>
            <Link to="/registro" className="group mt-8 inline-flex items-center gap-2 rounded-lg bg-slate-900 px-5 py-3 text-sm font-semibold text-white hover:bg-slate-800" data-testid="tour-register-button">Empezar ahora <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" /></Link>
          </div>
          <Mock />
        </div>
      </div>
    </section>
  );
}
