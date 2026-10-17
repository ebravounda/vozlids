import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, BarChart3, BellRing, Bot, Brain, CalendarCheck, CalendarHeart, Clock3, Code2, Ear, FileSpreadsheet, FileText, Gauge, Globe2, Headphones, Languages, Lock, MessageCircle, Mic, MousePointerClick, PhoneCall, PhoneForwarded, PhoneIncoming, PhoneOff, PhoneOutgoing, Plug, Quote, Repeat2, Server, ShieldCheck, Target, Users, WandSparkles } from "lucide-react";

const H = { fontFamily: "Plus Jakarta Sans" };

const FEATURES = [
  [PhoneIncoming, "Recepcionista 24/7", "Atiende llamadas entrantes, resuelve dudas y toma recados."],
  [PhoneOutgoing, "Llamadas a leads y campañas", "Llama en segundos a cada formulario o programa campañas."],
  [Server, "Número incluido", "Línea +34 o +56 lista, sin contratar operador."],
  [Mic, "Voces 100% realistas", "Voces HD de España y Latinoamérica con ambiente de oficina real."],
  [Users, "Equipo de ejecutivos", "Hasta 5 voces y nombres que se turnan en cada llamada."],
  [CalendarCheck, "Citas en línea 24/7", "Cierra citas en tus huecos libres durante la llamada; vista día, semana y mes."],
  [Repeat2, "Rellamadas automáticas", "Si dicen «llámame más tarde», el agente vuelve a llamar solo."],
  [Ear, "Escucha en directo", "Oye cualquier llamada en curso, cuélgala o pásala a tu equipo."],
  [Target, "Solo habla de tu negocio", "Rechaza con amabilidad cualquier tema que no sea tuyo."],
  [FileText, "Grabación y transcripción", "Cada llamada grabada, transcrita y resumida por IA."],
  [Gauge, "Puntuación de interés", "Sabes a quién llamar primero tu equipo."],
  [BellRing, "Avisos al instante", "Email cuando hay cita o el cliente pide una persona."],
  [MousePointerClick, "Botón para tu web", "“Te llamamos ahora” con estadísticas de conversión."],
  [Code2, "API y webhooks", "Integra tu CRM, ERP o facturación en minutos."],
  [PhoneOff, "Lista “No llamar”", "Nunca se vuelve a llamar a quien lo pide."],
  [Clock3, "Horario legal por país", "Las llamadas comerciales solo salen en horario permitido."],
  [Lock, "RGPD integrado", "Exporta o borra datos y elige cuánto guardar grabaciones."],
  [Headphones, "Paso a una persona", "Si hace falta, tu equipo recibe el aviso con el motivo."],
  [Globe2, "España y Chile", "Precios en euros o pesos y voces locales."],
  [ShieldCheck, "Sin permanencia", "Cancela cuando quieras desde tu panel."],
];

const SOON = [
  [MessageCircle, "WhatsApp tras la llamada", "Confirmación de la cita con dirección y botón para cambiarla."],
  [Brain, "Memoria de cada cliente", "Recuerda lo que se habló la última vez y lo retoma."],
  [PhoneForwarded, "Paso con resumen al oído", "Tu equipo oye en 5 segundos quién llama y qué quiere."],
  [WandSparkles, "Tu propia voz clonada", "Graba 1 minuto y el agente habla con la voz de tu negocio."],
  [BarChart3, "Informe semanal de ventas", "Llamadas, citas y euros recuperados, cada lunes en tu email."],
  [PhoneCall, "Llamadas perdidas al minuto", "Si no contestas, el agente devuelve la llamada al momento."],
  [CalendarHeart, "Campañas por calendario", "Cumpleaños, revisiones y promociones de temporada."],
  [FileSpreadsheet, "Subir leads desde Excel", "Carga tu lista y lanza una campaña en un clic."],
  [Plug, "Conexión con tu CRM", "HubSpot y formularios de Facebook e Instagram."],
  [Gauge, "Mejora automática del agente", "La IA te dice qué añadir para cerrar más citas."],
  [Languages, "Varios idiomas en la llamada", "Cambia a inglés o catalán si el cliente lo habla."],
];

const Card = ({ I, t, d, soon }) => (
  <div className={`group rounded-xl border p-5 transition-[transform,box-shadow,border-color] hover:-translate-y-0.5 hover:shadow-md ${soon ? "border-dashed border-slate-300 bg-white/60" : "border-slate-200 bg-white hover:border-blue-200"}`} data-testid={soon ? "feature-soon-card" : "feature-card"}>
    <div className="flex items-start justify-between gap-2">
      <span className={`grid h-9 w-9 place-items-center rounded-lg transition-colors ${soon ? "bg-slate-100 text-slate-500" : "bg-blue-50 text-blue-700 group-hover:bg-blue-600 group-hover:text-white"}`}><I className="h-4 w-4" /></span>
      {soon && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-amber-700">Próximamente</span>}
    </div>
    <p className="mt-4 font-semibold text-slate-900">{t}</p><p className="mt-1 text-sm leading-relaxed text-slate-500">{d}</p>
  </div>
);

export const FeatureGrid = () => (
  <section id="funciones" className="vl-reveal scroll-mt-20 border-b border-slate-200 bg-slate-50" data-testid="feature-grid">
    <div className="mx-auto max-w-6xl px-6 py-24">
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div><p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-600">Todo incluido</p>
          <h2 className="mt-3 max-w-2xl text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl" style={H}>{FEATURES.length} funciones en todos los planes. Sin extras escondidos.</h2></div>
        <Link to="/registro" className="group inline-flex items-center gap-2 text-sm font-semibold text-blue-700" data-testid="features-register-link">Crear mi cuenta <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" /></Link>
      </div>
      <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {FEATURES.map(([I, t, d]) => <Card key={t} I={I} t={t} d={d} />)}
      </div>
      <div className="mt-16" data-testid="feature-soon">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-amber-600">En camino</p>
        <h3 className="mt-2 text-2xl font-bold tracking-tight text-slate-900" style={H}>Lo que llega a tu agente muy pronto</h3>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{SOON.map(([I, t, d]) => <Card key={t} I={I} t={t} d={d} soon />)}</div>
      </div>
    </div>
  </section>
);

const LOGOS = [["Tramilex Abogados", "/clients/tramilex.webp", "h-12"], ["IberoAcademy", "/clients/iberoacademy.webp", "h-16"], ["GoRoky.com", "/clients/goroky.webp", "h-10"], ["Bridge Industrial Solutions", "/clients/bridge.webp", "h-16"]];

export const LogoStrip = () => (
  <section className="border-b border-slate-200 bg-white" aria-label="Clientes" data-testid="logo-strip">
    <div className="mx-auto flex max-w-6xl flex-col items-center gap-6 px-6 py-10 md:flex-row md:justify-between">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">Confían en VozLeads</p>
      <div className="flex flex-wrap items-center justify-center gap-x-14 gap-y-6">
        {LOGOS.map(([n, src, h]) => <img key={n} src={src} alt={n} loading="lazy" className={`${h} w-auto object-contain opacity-70 grayscale transition-[filter,opacity] duration-300 hover:opacity-100 hover:grayscale-0`} data-testid={`client-logo-${n.split(" ")[0].toLowerCase()}`} />)}
      </div>
    </div>
  </section>
);

const IMG = (id) => `https://images.unsplash.com/${id}?auto=format&fit=crop&w=900&q=70`;
const TESTIMONIALS = [
  ["Tramilex Abogados", "Despacho de abogados · Málaga, España", IMG("photo-1758518731462-d091b0b4ed0d"), "Recepcionista IA + Agenda",
    "Cuando estábamos en juicio o reunidos se nos escapaban consultas. Ahora el agente atiende cada llamada, identifica si es un asunto de extranjería, laboral o civil y nos deja la cita en la agenda con un resumen. Llegamos a la primera reunión sabiendo de qué va el caso.", "Dirección del despacho"],
  ["IberoAcademy", "Academia · Las Condes, Santiago de Chile", IMG("photo-1664382953518-4a664ab8a8c9"), "Llamada a leads + clase de prueba",
    "Muchos interesados rellenaban el formulario por la noche y a la mañana siguiente ya habían elegido otra academia. Con VozLeads les llamamos en segundos, resolvemos dudas de horarios y precios y agendamos la clase de prueba sin que nadie del equipo tenga que estar pendiente del teléfono.", "Coordinación académica"],
  ["GoRoky.com", "Telefonía y fibra · Madrid, España", IMG("photo-1626863905121-3b0c0ed7b94c"), "API + webhooks",
    "Nuestro CRM lanza por API las llamadas de recordatorio de instalación y el seguimiento de portabilidades. El resultado vuelve por webhook y el equipo solo interviene cuando el cliente lo pide. Ha liberado horas de trabajo repetitivo cada semana.", "Operaciones · empresa del grupo"],
];

export const Testimonials = () => (
  <section id="clientes" className="vl-reveal scroll-mt-20 bg-white" data-testid="testimonials">
    <div className="mx-auto max-w-6xl px-6 py-24">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-600">Clientes</p>
      <h2 className="mt-3 max-w-2xl text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl" style={H}>Negocios que ya no pierden llamadas</h2>
      <div className="mt-12 grid gap-6 lg:grid-cols-3">
        {TESTIMONIALS.map(([biz, where, img, tag, quote, role], i) => (
          <figure key={biz} className="flex flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white transition-shadow hover:shadow-[0_24px_60px_-28px_rgba(15,23,42,0.35)]" data-testid={`testimonial-${i}`}>
            <div className="relative h-44 overflow-hidden"><img src={img} alt={`Equipo de ${biz}`} loading="lazy" className="h-full w-full object-cover transition-transform duration-700 hover:scale-105" />
              <span className="absolute left-3 top-3 rounded-full bg-white/90 px-2.5 py-1 text-[11px] font-semibold text-slate-800 backdrop-blur">{tag}</span></div>
            <div className="flex flex-1 flex-col p-6">
              <Quote className="h-6 w-6 text-blue-200" />
              <blockquote className="mt-3 flex-1 text-[15px] leading-relaxed text-slate-700">{quote}</blockquote>
              <figcaption className="mt-6 flex items-center gap-4 border-t border-slate-100 pt-4"><img src={LOGOS[i][1]} alt="" className="h-12 w-24 shrink-0 object-contain" /><div><p className="font-bold text-slate-900" style={H}>{biz}</p><p className="text-sm text-slate-500">{role} · {where}</p></div></figcaption>
            </div>
          </figure>
        ))}
      </div>
    </div>
  </section>
);

export function LostCalls({ m }) {
  const cl = m.market === "CL";
  const [calls, setCalls] = useState(40);
  const [value, setValue] = useState(cl ? 80000 : 120);
  const lost = Math.round(calls * 0.3 * value);
  const money = (v) => (cl ? `$${v.toLocaleString("es-CL")}` : `${v.toLocaleString("es-ES")} €`);
  const range = (label, v, set, min, max, step, fmt, id) => (
    <label className="block"><span className="flex justify-between text-sm text-slate-300">{label}<b className="font-mono text-white">{fmt(v)}</b></span>
      <input type="range" min={min} max={max} step={step} value={v} onChange={(e) => set(Number(e.target.value))} className="mt-3 w-full accent-blue-500" data-testid={id} /></label>
  );
  return (
    <section className="vl-reveal bg-slate-900" data-testid="lost-calls">
      <div className="mx-auto grid max-w-6xl items-center gap-12 px-6 py-24 lg:grid-cols-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-400">Calculadora</p>
          <h2 className="mt-3 text-3xl font-bold tracking-tight text-white sm:text-4xl" style={H}>¿Cuánto te cuestan las llamadas que no contestas?</h2>
          <p className="mt-4 text-slate-300">Mueve los valores con los datos de tu negocio. Estimamos que 3 de cada 10 llamadas o leads sin atender a tiempo terminan comprando a otro.</p>
          <div className="mt-8 space-y-6">
            {range("Llamadas o leads sin atender al mes", calls, setCalls, 5, 300, 5, (v) => v, "lost-calls-input")}
            {range("Valor medio de un cliente", value, setValue, cl ? 10000 : 20, cl ? 1000000 : 2000, cl ? 10000 : 10, money, "lost-value-input")}
          </div>
        </div>
        <div className="rounded-2xl border border-slate-700 bg-slate-800/60 p-8 text-center">
          <p className="text-sm text-slate-400">Estás dejando de ingresar cada mes unos</p>
          <p className="mt-3 text-5xl font-extrabold text-white sm:text-6xl" style={H} data-testid="lost-calls-result">{money(lost)}</p>
          <p className="mt-3 text-sm text-slate-400">Tu agente con IA contesta todas, de día y de noche, por menos de lo que cuesta un cliente.</p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:justify-center">
            <a href="#solicitar" className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-5 py-3 text-sm font-semibold text-white hover:bg-blue-500" data-testid="lost-calls-demo-button"><Bot className="h-4 w-4" />Que me llame el agente</a>
            <Link to="/registro" className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-600 px-5 py-3 text-sm font-semibold text-white hover:bg-slate-700" data-testid="lost-calls-register-button">Empezar ahora <ArrowRight className="h-4 w-4" /></Link>
          </div>
        </div>
      </div>
    </section>
  );
}
