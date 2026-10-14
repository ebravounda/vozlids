import { Link } from "react-router-dom";
import { ArrowRight, BarChart3, CalendarCheck, Check, Code2, Globe2, Headphones, LifeBuoy, PhoneCall, ShieldCheck, Timer, Wallet } from "lucide-react";
import { AmbiencePreview } from "@/components/AmbiencePreview";
import { Pricing } from "@/components/Pricing";

const DEMO = "Hola Laura, soy Marta, asistente virtual de Clínica Sonrisa. Te llamo porque acabas de pedir información en nuestra web. ¿Tienes un minuto?";
const USES = [
  [Timer, "Respuesta inmediata a nuevos leads", "Cada formulario recibido genera una llamada en menos de 30 segundos, de día o de noche."],
  [CalendarCheck, "Citas agendadas en tu calendario", "El agente consulta tu disponibilidad real y confirma la cita por email al cliente y a tu equipo."],
  [Wallet, "Gestión de cobros", "Recordatorios de pagos pendientes con importe y vencimiento, sin pedir nunca datos de tarjeta."],
  [Headphones, "Seguimiento y encuestas", "Llamadas programadas para conocer la satisfacción del cliente y detectar incidencias a tiempo."],
  [LifeBuoy, "Derivación a soporte técnico", "Si el cliente necesita ayuda, se abre una solicitud y tu equipo recibe un aviso por email."],
  [Code2, "API para tus sistemas", "Lanza llamadas desde tu CRM, ERP o plataforma de facturación con una sola petición."],
];
const STEPS = [["Configura", "Define el objetivo, el guion, la voz y el horario de tu agente."], ["Conecta", "Inserta el formulario en tu web o integra la API con tu CRM."], ["Mide", "Revisa grabaciones, transcripciones, resúmenes y resultados de cada llamada."]];
const FAQ = [
  ["¿El cliente sabe que habla con un asistente virtual?", "Sí. El agente se presenta como asistente virtual y avisa de la grabación, como exige la normativa europea y chilena."],
  ["¿En qué países funciona?", "España (+34) y Chile (+56), con voces, horarios y formatos adaptados a cada país."],
  ["¿Qué pasa si alguien no quiere más llamadas?", "Se añade automáticamente a la lista de exclusión y no vuelve a ser contactado."],
  ["¿Cómo se factura?", "Por planes mensuales de minutos. Puedes ampliar tu plan en cualquier momento."],
];

const Nav = () => (
  <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/90 backdrop-blur">
    <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
      <span className="flex items-center gap-2 text-lg font-bold tracking-tight text-slate-900" style={{ fontFamily: "Outfit" }}>
        <span className="grid h-8 w-8 place-items-center rounded-md bg-slate-900 text-white"><PhoneCall className="h-4 w-4" /></span>VozLeads
      </span>
      <nav className="hidden gap-8 text-sm text-slate-600 md:flex">
        <a href="#soluciones" className="hover:text-slate-900">Soluciones</a><a href="#como" className="hover:text-slate-900">Cómo funciona</a>
        <a href="#api" className="hover:text-slate-900">API</a><a href="#precios" className="hover:text-slate-900" data-testid="landing-nav-pricing-link">Precios</a><a href="#faq" className="hover:text-slate-900">Preguntas</a>
      </nav>
      <div className="flex items-center gap-2">
        <Link to="/login" data-testid="landing-nav-login-button" className="px-3 py-2 text-sm font-medium text-slate-700 hover:text-slate-900">Acceder</Link>
        <Link to="/registro" data-testid="landing-nav-register-button" className="rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800">Crear cuenta</Link>
      </div>
    </div>
  </header>
);

const CallCard = () => (
  <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-[0_20px_60px_-20px_rgba(15,23,42,0.25)]" data-testid="landing-call-card">
    <div className="flex items-center justify-between border-b border-slate-100 pb-4">
      <div><p className="text-sm font-semibold text-slate-900">Laura Pérez</p><p className="font-mono text-xs text-slate-500">+34 6•• ••• 412 · 01:12</p></div>
      <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700">Cita agendada</span>
    </div>
    <div className="space-y-2 py-4 text-sm">
      <p className="w-fit max-w-[85%] rounded-lg bg-slate-100 px-3 py-2 text-slate-700">¿Te viene bien el jueves a las diez y media?</p>
      <p className="ml-auto w-fit max-w-[85%] rounded-lg bg-slate-900 px-3 py-2 text-white">Sí, el jueves me va perfecto.</p>
    </div>
    <div className="grid grid-cols-3 gap-3 border-t border-slate-100 pt-4 text-center">
      {[["Interés", "86%"], ["Duración", "1:12"], ["Resultado", "Cita"]].map(([k, v]) => <div key={k}><p className="text-xs text-slate-500">{k}</p><p className="font-semibold text-slate-900">{v}</p></div>)}
    </div>
  </div>
);

export default function Landing() {
  return (
    <div className="min-h-screen bg-white text-slate-700" style={{ fontFamily: "'Plus Jakarta Sans', sans-serif" }}>
      <Nav />
      <section className="border-b border-slate-200 bg-slate-50">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-6 py-20 lg:grid-cols-2 lg:py-28">
          <div>
            <p className="mb-5 text-sm font-semibold text-emerald-700">Agentes telefónicos para España y Chile</p>
            <h1 className="text-4xl font-bold leading-tight tracking-tight text-slate-900 sm:text-5xl" style={{ fontFamily: "Outfit" }}>Atiende cada lead por teléfono en menos de 30 segundos.</h1>
            <p className="mt-6 max-w-lg text-lg text-slate-600">VozLeads llama a tus clientes potenciales, los califica, agenda citas, gestiona cobros y hace seguimiento. Tu equipo solo atiende las oportunidades reales.</p>
            <div className="mt-9 flex flex-wrap items-center gap-3">
              <Link to="/registro" data-testid="landing-hero-register-button" className="inline-flex items-center gap-2 rounded-md bg-slate-900 px-6 py-3 font-semibold text-white hover:bg-slate-800">Empezar ahora <ArrowRight className="h-4 w-4" /></Link>
              <AmbiencePreview ambience="oficina_real" volume={35} voice="p_marta" text={DEMO} label="Escuchar un ejemplo" testid="landing-hero-demo-button" className="!border-slate-300 !bg-white !text-slate-800 hover:!bg-slate-100" />
            </div>
            <ul className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm text-slate-600">
              {["Grabación y transcripción", "Lista de exclusión automática", "Sin permanencia"].map((t) => <li key={t} className="flex items-center gap-2"><Check className="h-4 w-4 text-emerald-600" />{t}</li>)}
            </ul>
          </div>
          <CallCard />
        </div>
      </section>

      <section id="soluciones" className="mx-auto max-w-6xl px-6 py-24">
        <h2 className="max-w-2xl text-3xl font-bold tracking-tight text-slate-900" style={{ fontFamily: "Outfit" }}>Una plataforma para todo el ciclo de llamadas</h2>
        <p className="mt-3 max-w-2xl text-slate-600">Desde el primer contacto hasta el cobro y la fidelización.</p>
        <div className="mt-12 grid gap-px overflow-hidden rounded-xl border border-slate-200 bg-slate-200 md:grid-cols-3">
          {USES.map(([Icon, t, d]) => (
            <div key={t} className="bg-white p-7"><Icon className="h-5 w-5 text-emerald-700" /><h3 className="mt-5 font-semibold text-slate-900">{t}</h3><p className="mt-2 text-sm leading-relaxed text-slate-600">{d}</p></div>
          ))}
        </div>
      </section>

      <section id="como" className="border-y border-slate-200 bg-slate-50">
        <div className="mx-auto grid max-w-6xl gap-10 px-6 py-20 md:grid-cols-3">
          {STEPS.map(([t, d], i) => (
            <div key={t}><span className="font-mono text-sm text-emerald-700">0{i + 1}</span><h3 className="mt-2 text-xl font-semibold text-slate-900">{t}</h3><p className="mt-2 text-sm text-slate-600">{d}</p></div>
          ))}
        </div>
      </section>

      <section id="api" className="mx-auto grid max-w-6xl gap-12 px-6 py-24 lg:grid-cols-2">
        <div>
          <h2 className="text-3xl font-bold tracking-tight text-slate-900" style={{ fontFamily: "Outfit" }}>Integración por API</h2>
          <p className="mt-3 text-slate-600">Automatiza llamadas de cobro, información de producto, recordatorios y encuestas desde tus propios sistemas.</p>
          <ul className="mt-8 space-y-4 text-sm">
            {[[Globe2, "España y Chile, con horario local de cada país"], [BarChart3, "Resultado, resumen y transcripción de cada llamada"], [ShieldCheck, "Claves de API por cuenta, revocables en cualquier momento"]].map(([I, t]) => (
              <li key={t} className="flex items-center gap-3"><I className="h-5 w-5 text-emerald-700" />{t}</li>
            ))}
          </ul>
        </div>
        <pre className="overflow-x-auto rounded-xl bg-slate-900 p-6 font-mono text-xs leading-relaxed text-slate-200">{`POST /api/v1/calls
X-API-Key: vl_live_…

{
  "agent_id": "…",
  "name": "Laura Pérez",
  "phone": "+56912345678",
  "type": "cobro",
  "consent": true,
  "context": { "importe": "$45.000", "vencimiento": "15/06" }
}`}</pre>
      </section>

      <Pricing />

      <section id="faq" className="border-t border-slate-200 bg-slate-50">
        <div className="mx-auto max-w-3xl px-6 py-20">
          <h2 className="text-3xl font-bold tracking-tight text-slate-900" style={{ fontFamily: "Outfit" }}>Preguntas frecuentes</h2>
          <dl className="mt-10 divide-y divide-slate-200">
            {FAQ.map(([q, a]) => <div key={q} className="py-5"><dt className="font-semibold text-slate-900">{q}</dt><dd className="mt-2 text-sm text-slate-600">{a}</dd></div>)}
          </dl>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-20">
        <div className="flex flex-col items-start justify-between gap-6 rounded-xl bg-slate-900 p-10 md:flex-row md:items-center">
          <div><h2 className="text-2xl font-bold text-white" style={{ fontFamily: "Outfit" }}>Empieza a convertir más leads esta semana</h2><p className="mt-2 text-slate-300">Configura tu primer agente en minutos y pruébalo en tu propio teléfono.</p></div>
          <Link to="/registro" data-testid="landing-cta-register-button" className="inline-flex items-center gap-2 rounded-md bg-white px-6 py-3 font-semibold text-slate-900 hover:bg-slate-100">Crear cuenta <ArrowRight className="h-4 w-4" /></Link>
        </div>
      </section>

      <footer className="border-t border-slate-200">
        <div className="mx-auto flex max-w-6xl flex-col justify-between gap-4 px-6 py-8 text-sm text-slate-500 md:flex-row">
          <p>© {new Date().getFullYear()} VozLeads · vozleads.com</p>
          <p>España · Chile</p>
        </div>
      </footer>
    </div>
  );
}
