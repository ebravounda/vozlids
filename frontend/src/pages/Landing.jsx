import { Link } from "react-router-dom";
import { ArrowRight, Clock, Keyboard, MessageSquareText, PhoneCall, ShieldCheck, CalendarCheck, Check, X } from "lucide-react";
import { Logo } from "@/components/Common";
import { AmbiencePreview } from "@/components/AmbiencePreview";

const DEMO = "Hola Laura, soy Marta, la asistente virtual de Clínica Dental Sonrisa. Te llamo porque acabas de pedir información sobre ortodoncia invisible. ¿Tienes un minuto?";

const FEATURES = [
  { icon: Clock, title: "Llamada en menos de 30 segundos", text: "El lead deja sus datos y su móvil suena antes de que cierre la pestaña. Contactar en el primer minuto multiplica la conversión." },
  { icon: Keyboard, title: "Ambiente de oficina real", text: "Teclados, murmullo de compañeros o call center, con el volumen que elijas. Suena a una persona trabajando en su mesa." },
  { icon: MessageSquareText, title: "Español de España natural", text: "Voces neuronales es-ES, pausas, “vale”, “perfecto”… y deja que la interrumpan como en una llamada de verdad." },
  { icon: CalendarCheck, title: "Agenda citas sola", text: "Consulta tus huecos libres y reserva durante la llamada, sin dobles reservas." },
];

const COMPARE = [
  ["Llama en menos de 30 s, 24/7", true, false, false],
  ["Conversación de voz natural", true, true, false],
  ["Coste por lead", "≈ 0,30 €", "≈ 8 €", "≈ 0,05 €"],
  ["Agenda cita en la llamada", true, true, false],
  ["Escala a cientos de leads/día", true, false, true],
];

const Cell = ({ v }) => (v === true ? <Check className="mx-auto h-5 w-5 text-emerald-400" /> : v === false ? <X className="mx-auto h-5 w-5 text-slate-600" /> : <span className="font-mono text-sm text-slate-200">{v}</span>);

function Hero() {
  return (
    <section className="relative mx-auto grid max-w-7xl gap-14 px-6 pb-24 pt-36 lg:grid-cols-12 lg:pt-44">
      <div className="lg:col-span-7 fade-up">
        <p className="mb-6 inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-emerald-300">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" /> Agentes de voz IA para España
        </p>
        <h1 className="text-4xl font-extrabold leading-[1.05] tracking-tight text-white sm:text-5xl lg:text-6xl">
          Tus leads, al teléfono <span className="text-emerald-400">en 30 segundos.</span> Con una voz que suena a oficina de verdad.
        </h1>
        <p className="mt-6 max-w-xl text-base text-slate-400 sm:text-lg">
          VozLead llama al instante a cada persona que rellena tu formulario, la califica, resuelve dudas y le agenda una cita. Teclados de fondo incluidos.
        </p>
        <div className="mt-10 flex flex-wrap items-center gap-4">
          <Link to="/registro" data-testid="landing-hero-register-button" className="inline-flex items-center gap-2 rounded-full bg-emerald-500 px-7 py-3.5 font-semibold text-slate-950 transition-colors hover:bg-emerald-400">
            Crear mi agente gratis <ArrowRight className="h-4 w-4" />
          </Link>
          <AmbiencePreview ambience="oficina" volume={40} voice="elvira" text={DEMO} label="Escuchar cómo suena" testid="landing-hero-demo-button" />
        </div>
        <p className="mt-4 text-xs text-slate-500">La demo usa la voz de tu navegador; en la llamada real suena la voz neuronal elegida.</p>
      </div>
      <div className="relative lg:col-span-5 fade-up" style={{ animationDelay: "0.15s" }}>
        <div className="relative overflow-hidden rounded-3xl border border-slate-800">
          <img src="https://images.unsplash.com/photo-1659186198156-f0372a4fdc5e?crop=entropy&cs=srgb&fm=jpg&q=80&w=1000" alt="Escritorio de oficina" className="h-[460px] w-full object-cover opacity-80" />
          <div className="absolute inset-0 bg-gradient-to-t from-[#0B0F17] via-transparent to-transparent" />
        </div>
        <div className="absolute -bottom-8 -left-6 w-[85%] rounded-2xl border border-slate-700 bg-slate-950/90 p-5 backdrop-blur-xl" data-testid="landing-call-card">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="ring-pulse grid h-10 w-10 place-items-center rounded-full bg-emerald-500 text-slate-950"><PhoneCall className="h-4 w-4" /></span>
              <div>
                <p className="text-sm font-semibold text-white">Laura P. · +34 6•• ••• 412</p>
                <p className="text-xs text-emerald-300">En llamada · 00:48</p>
              </div>
            </div>
            <span className="rounded-full bg-teal-400/15 px-2.5 py-0.5 text-xs font-semibold text-teal-200">Cita agendada</span>
          </div>
          <div className="mt-4 space-y-2 text-sm">
            <p className="rounded-xl rounded-tl-sm bg-slate-800 px-3 py-2 text-slate-200">¿Te viene bien el jueves a las diez y media?</p>
            <p className="ml-auto w-fit rounded-xl rounded-tr-sm bg-emerald-500/20 px-3 py-2 text-emerald-100">Perfecto, el jueves me va genial.</p>
          </div>
        </div>
      </div>
    </section>
  );
}

export default function Landing() {
  return (
    <div className="grain relative min-h-screen overflow-hidden bg-[#0B0F17] text-slate-100">
      <div className="grid-lines pointer-events-none absolute inset-x-0 top-0 h-[900px] [mask-image:linear-gradient(to_bottom,black,transparent)]" />
      <header className="fixed inset-x-0 top-4 z-50 mx-auto flex max-w-6xl items-center justify-between rounded-full border border-slate-800/80 bg-slate-950/80 px-5 py-3 backdrop-blur-xl" style={{ width: "calc(100% - 2rem)" }}>
        <Logo />
        <nav className="hidden gap-8 text-sm text-slate-400 md:flex">
          <a href="#ventajas" className="hover:text-white">Ventajas</a>
          <a href="#como" className="hover:text-white">Cómo funciona</a>
          <a href="#comparativa" className="hover:text-white">Comparativa</a>
        </nav>
        <div className="flex items-center gap-2">
          <Link to="/login" data-testid="landing-nav-login-button" className="rounded-full px-4 py-2 text-sm font-medium text-slate-300 hover:text-white">Iniciar sesión</Link>
          <Link to="/registro" data-testid="landing-nav-register-button" className="rounded-full bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 transition-colors hover:bg-emerald-400">Probar gratis</Link>
        </div>
      </header>

      <Hero />

      <section id="ventajas" className="relative mx-auto max-w-7xl px-6 py-24">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-400">Ventajas</p>
        <h2 className="mt-3 max-w-2xl text-3xl font-bold tracking-tight text-white sm:text-4xl">Todo lo que haría tu mejor comercial, en cada lead.</h2>
        <div className="mt-14 grid gap-5 md:grid-cols-6">
          {FEATURES.map((f, i) => (
            <div key={f.title} className={`rounded-3xl border border-slate-800 bg-slate-900/50 p-8 transition-colors hover:border-emerald-500/40 ${i === 0 || i === 3 ? "md:col-span-4" : "md:col-span-2"}`}>
              <f.icon className="h-6 w-6 text-emerald-400" />
              <h3 className="mt-6 text-xl font-semibold text-white">{f.title}</h3>
              <p className="mt-3 text-sm leading-relaxed text-slate-400">{f.text}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="como" className="relative mx-auto max-w-7xl px-6 py-24">
        <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">Cómo funciona</h2>
        <div className="mt-12 grid gap-10 md:grid-cols-3">
          {[
            ["01", "Crea tu agente", "Cuéntale qué vendes, qué preguntas hacer, elige su voz y el ambiente de fondo."],
            ["02", "Pega el formulario", "Copia el código en tu web. Cada envío dispara la llamada al momento."],
            ["03", "Mira los resultados", "Grabación, transcripción, resumen, puntuación de interés y citas en tu panel."],
          ].map(([n, t, d]) => (
            <div key={n} className="border-l border-slate-800 pl-6">
              <span className="font-mono text-sm text-emerald-400">{n}</span>
              <h3 className="mt-3 text-xl font-semibold text-white">{t}</h3>
              <p className="mt-2 text-sm text-slate-400">{d}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="comparativa" className="relative mx-auto max-w-5xl px-6 py-24">
        <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">VozLead frente a las alternativas</h2>
        <div className="mt-10 overflow-x-auto rounded-3xl border border-slate-800">
          <table className="w-full min-w-[560px] text-left text-sm" data-testid="landing-comparison-table">
            <thead className="bg-slate-900 text-slate-400">
              <tr><th className="p-4 font-medium"></th><th className="p-4 text-center font-semibold text-emerald-300">VozLead IA</th><th className="p-4 text-center font-medium">Agente humano</th><th className="p-4 text-center font-medium">Chatbot</th></tr>
            </thead>
            <tbody>
              {COMPARE.map(([label, ...vals]) => (
                <tr key={label} className="border-t border-slate-800">
                  <td className="p-4 text-slate-300">{label}</td>
                  {vals.map((v, i) => <td key={i} className={`p-4 text-center ${i === 0 ? "bg-emerald-500/5" : ""}`}><Cell v={v} /></td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-10 flex gap-4 rounded-2xl border border-slate-800 bg-slate-900/50 p-6">
          <ShieldCheck className="h-6 w-6 shrink-0 text-emerald-400" />
          <p className="text-sm text-slate-400">
            <span className="font-semibold text-white">Cumple la normativa española y europea.</span> El agente dice que es un asistente virtual, avisa de la grabación y solo llama a quien ha dado su consentimiento en tu formulario. Si alguien pide no ser llamado, pasa a tu lista de no llamar al momento.
          </p>
        </div>
      </section>

      <section className="relative mx-auto max-w-7xl px-6 pb-24">
        <div className="flex flex-col items-start justify-between gap-6 rounded-3xl border border-emerald-500/30 bg-emerald-500/10 p-10 md:flex-row md:items-center">
          <div>
            <h2 className="text-3xl font-bold tracking-tight text-white">Que ningún lead se enfríe más.</h2>
            <p className="mt-2 text-slate-300">Crea tu agente y pruébalo en tu propio móvil hoy mismo.</p>
          </div>
          <Link to="/registro" data-testid="landing-cta-register-button" className="inline-flex items-center gap-2 rounded-full bg-emerald-500 px-7 py-3.5 font-semibold text-slate-950 transition-colors hover:bg-emerald-400">
            Empezar gratis <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </section>
      <footer className="relative border-t border-slate-800 px-6 py-10 text-center text-xs text-slate-500">© {new Date().getFullYear()} VozLead · Hecho en España</footer>
    </div>
  );
}
