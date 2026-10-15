import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, BarChart3, CalendarCheck, Check, Code2, Globe2, Headphones, LifeBuoy, Mic, PhoneCall, PhoneForwarded, Server, ShieldCheck, Timer, UserRound, Wallet } from "lucide-react";
import { AmbiencePreview } from "@/components/AmbiencePreview";
import { InfoForm } from "@/components/landing/InfoForm";

const H = { fontFamily: "Plus Jakarta Sans" };
const USES = [
  [Timer, "Respuesta inmediata a nuevos leads", "Cada formulario recibido genera una llamada en menos de 30 segundos, de día o de noche."],
  [CalendarCheck, "Citas agendadas en tu calendario", "El agente consulta tu disponibilidad real y confirma la cita por email al cliente y a tu equipo."],
  [Wallet, "Cobranza y recordatorios de pago", "Recuerda importes y vencimientos con amabilidad, sin pedir nunca datos de tarjeta."],
  [Headphones, "Seguimiento y encuestas", "Llamadas programadas para medir la satisfacción y detectar incidencias a tiempo."],
  [UserRound, "Paso a una persona cuando hace falta", "Si el cliente quiere hablar con alguien, tu equipo recibe el aviso al instante con el motivo."],
  [Code2, "API para tu CRM", "Lanza llamadas desde tu CRM, ERP o plataforma de facturación con una sola petición."],
];
const STEPS = [["Configura", "Elige objetivo, guion, voz y horario. Tu agente queda listo en minutos."], ["Conecta", "Pega el formulario en tu web o usa nuestra API. El número de España o Chile ya viene incluido."], ["Vende", "Revisa grabaciones, transcripciones y resultados, y atiende solo a quien está listo."]];

const LINES = [
  ["agent", "Hola Laura, soy Sara de Clínica Sonrisa. Te llamo por la solicitud que acabas de enviar. ¿Tienes un minuto?"],
  ["lead", "Sí, claro, dime."],
  ["agent", "Perfecto. ¿Te viene bien el jueves a las 10:30 para la primera visita?"],
  ["lead", "El jueves me va genial."],
  ["agent", "¡Listo! Te envío la confirmación por email. Gracias, Laura."],
];

function CallStudio() {
  const [n, setN] = useState(1);
  const [sec, setSec] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setN((x) => (x >= LINES.length ? 1 : x + 1)), 2600);
    const c = setInterval(() => setSec((x) => (x + 1) % 75), 1000);
    return () => { clearInterval(t); clearInterval(c); };
  }, []);
  return (
    <div className="vl-float relative rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_30px_80px_-30px_rgba(15,23,42,0.35)]" data-testid="hero-call-studio">
      <div className="flex items-center justify-between border-b border-slate-100 pb-4">
        <div className="flex items-center gap-3">
          <span className="relative grid h-10 w-10 place-items-center rounded-full bg-blue-600 text-sm font-bold text-white">LP<span className="absolute -right-0.5 -top-0.5 h-3 w-3 rounded-full border-2 border-white bg-emerald-500 vl-pulse" /></span>
          <div><p className="text-sm font-semibold text-slate-900">Laura Pérez · nuevo lead</p><p className="font-mono text-xs text-slate-500">+34 6•• ••• 412 · 00:{String(sec).padStart(2, "0")}</p></div>
        </div>
        <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700">En llamada</span>
      </div>
      <div className="flex h-12 items-center justify-center gap-[3px] py-2" aria-hidden>
        {Array.from({ length: 36 }).map((_, i) => (
          <span key={i} className="vl-wave w-[3px] rounded-full bg-blue-600/80" style={{ height: 8 + ((i * 37) % 28), animationDelay: `${(i % 9) * 0.09}s`, animationDuration: `${0.8 + (i % 5) * 0.12}s` }} />
        ))}
      </div>
      <div className="h-[168px] space-y-2 overflow-hidden text-[13px] leading-snug">
        {LINES.slice(Math.max(0, n - 3), n).map(([who, t], i, arr) => (
          <p key={`${n}-${i}`} className={`w-fit max-w-[88%] rounded-xl px-3 py-2 ${who === "lead" ? "ml-auto bg-slate-900 text-white" : "bg-slate-100 text-slate-700"} ${i === arr.length - 1 ? "vl-type" : ""}`}>{t}</p>
        ))}
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 border-t border-slate-100 pt-3 text-center">
        {[["Respuesta", "12 s"], ["Interés", "Alto"], ["Resultado", "Cita"]].map(([k, v]) => <div key={k}><p className="text-[11px] text-slate-500">{k}</p><p className="text-sm font-semibold text-slate-900">{v}</p></div>)}
      </div>
    </div>
  );
}

export const Hero = ({ page }) => (
  <section className="relative overflow-hidden border-b border-slate-200 bg-[#F8FAFC]">
    <div className="pointer-events-none absolute inset-0 opacity-60 [background-image:radial-gradient(#CBD5E1_1px,transparent_1px)] [background-size:22px_22px] [mask-image:linear-gradient(to_bottom,black,transparent_75%)]" aria-hidden />
    <div className="relative mx-auto grid max-w-6xl items-start gap-12 px-6 py-14 lg:grid-cols-[1.15fr_1fr] lg:py-20">
      <div className="fade-up">
        <p className="mb-6 inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm" data-testid="hero-eyebrow">
          <span className="h-2 w-2 rounded-full bg-emerald-500 vl-pulse" />{page.eyebrow}
        </p>
        <h1 className="text-4xl font-extrabold leading-[1.06] tracking-tight text-slate-900 sm:text-5xl lg:text-6xl" style={H} data-testid="hero-title">{page.h1}</h1>
        <p className="mt-6 max-w-xl text-lg leading-relaxed text-slate-600">{page.intro}</p>
        <div className="mt-8 flex flex-wrap items-center gap-3">
          <AmbiencePreview demo label="Escuchar una llamada real" testid="landing-hero-demo-button" className="!border-slate-300 !bg-white !text-slate-900 shadow-sm hover:!bg-slate-50" />
          <Link to="/registro" data-testid="landing-hero-register-button" className="group inline-flex items-center gap-1.5 px-2 py-2 text-sm font-semibold text-slate-700 hover:text-slate-900">Crear cuenta <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" /></Link>
        </div>
        <ul className="mt-8 grid gap-2 text-sm text-slate-700 sm:grid-cols-2">
          {[{ ES: "Número +34 de España gratis", CL: "Número +56 de Chile gratis" }[page.country] || "Número +34 o +56 gratis", "Llama en menos de 30 segundos", "Voz natural en español", "Sin permanencia"].map((t) => <li key={t} className="flex items-center gap-2"><Check className="h-4 w-4 text-blue-600" />{t}</li>)}
        </ul>
        <div className="mt-10 hidden max-w-md lg:block"><CallStudio /></div>
      </div>
      <div className="fade-up lg:sticky lg:top-24" style={{ animationDelay: "0.15s" }}><InfoForm country={page.country} page={page.path} /></div>
    </div>
  </section>
);

export const TrustBar = () => (
  <section className="border-b border-slate-200 bg-white" aria-label="Datos clave">
    <div className="mx-auto grid max-w-6xl grid-cols-2 gap-6 px-6 py-10 md:grid-cols-4">
      {[["< 30 s", "del formulario a la llamada"], ["24/7", "dentro del horario que elijas"], ["Gratis", "número de España o Chile incluido"], ["100 %", "llamadas grabadas y transcritas"]].map(([k, v]) => (
        <div key={k}><p className="text-3xl font-bold text-slate-900" style={H}>{k}</p><p className="mt-1 text-sm text-slate-500">{v}</p></div>
      ))}
    </div>
  </section>
);

export const WhyNow = () => (
  <section className="vl-reveal mx-auto grid max-w-6xl items-center gap-12 px-6 py-24 lg:grid-cols-2">
    <div>
      <h2 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl" style={H}>El lead que no llamas en 5 minutos, se enfría</h2>
      <p className="mt-4 text-slate-600">Según el estudio <i>Lead Response Management</i> del MIT, contactar a un lead en los primeros 5 minutos multiplica las posibilidades de calificarlo frente a hacerlo media hora después. Tu equipo no puede estar siempre al teléfono; tu agente con IA sí.</p>
      <ul className="mt-8 space-y-3 text-sm text-slate-700">
        {["Llama mientras el cliente aún tiene tu web abierta", "Califica con tus preguntas y descarta curiosos", "Deja la cita agendada y el resumen por escrito"].map((t) => <li key={t} className="flex gap-3"><Check className="h-5 w-5 shrink-0 text-blue-600" />{t}</li>)}
      </ul>
    </div>
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-[0_20px_60px_-24px_rgba(15,23,42,0.3)]" data-testid="landing-call-card">
      <div className="flex items-center justify-between border-b border-slate-100 pb-4">
        <div><p className="text-sm font-semibold text-slate-900">Laura Pérez</p><p className="font-mono text-xs text-slate-500">+34 6•• ••• 412 · 01:12</p></div>
        <span className="rounded-full bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-700">Cita agendada</span>
      </div>
      <div className="space-y-2 py-4 text-sm">
        <p className="w-fit max-w-[85%] rounded-lg bg-slate-100 px-3 py-2 text-slate-700">Hola Laura, te llamo de Clínica Sonrisa por tu solicitud. ¿Te viene bien el jueves a las diez y media?</p>
        <p className="ml-auto w-fit max-w-[85%] rounded-lg bg-slate-900 px-3 py-2 text-white">Sí, el jueves me va perfecto.</p>
        <p className="w-fit max-w-[85%] rounded-lg bg-slate-100 px-3 py-2 text-slate-700">¡Genial! Te envío la confirmación por email.</p>
      </div>
      <div className="grid grid-cols-3 gap-3 border-t border-slate-100 pt-4 text-center">
        {[["Interés", "86 %"], ["Duración", "1:12"], ["Resultado", "Cita"]].map(([k, v]) => <div key={k}><p className="text-xs text-slate-500">{k}</p><p className="font-semibold text-slate-900">{v}</p></div>)}
      </div>
    </div>
  </section>
);

export const Uses = () => (
  <section id="soluciones" className="vl-reveal scroll-mt-20 border-y border-slate-200 bg-slate-50">
    <div className="mx-auto max-w-6xl px-6 py-24">
      <h2 className="max-w-2xl text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl" style={H}>Un agente de voz para todo el ciclo de venta</h2>
      <p className="mt-3 max-w-2xl text-slate-600">Desde el primer contacto hasta el cobro y la fidelización, en España y en Chile.</p>
      <div className="mt-12 grid gap-px overflow-hidden rounded-xl border border-slate-200 bg-slate-200 md:grid-cols-3">
        {USES.map(([Icon, t, d]) => (
          <div key={t} className="bg-white p-7 transition-colors hover:bg-blue-50/40"><Icon className="h-5 w-5 text-blue-700" /><h3 className="mt-5 font-semibold text-slate-900">{t}</h3><p className="mt-2 text-sm leading-relaxed text-slate-600">{d}</p></div>
        ))}
      </div>
    </div>
  </section>
);

export const Compatible = () => (
  <section className="vl-reveal mx-auto max-w-6xl px-6 py-24" aria-labelledby="compat-title">
    <h2 id="compat-title" className="max-w-3xl text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl" style={H}>Número de España o Chile gratis. Y compatible con tu centralita</h2>
    <p className="mt-3 max-w-3xl text-slate-600">Te damos gratis un número de España (+34) o de Chile (+56) ya configurado: no necesitas contratar telefonía IP ni cuenta SIP. Si ya tienes centralita, central IP u oficina virtual, VozLeads trabaja a su lado sin tocarla.</p>
    <div className="mt-12 grid gap-5 md:grid-cols-3">
      {[[Server, "Número y línea incluidos", "Número +34 o +56 listo para llamar desde el primer día, sin contratar operador.", "/telefonia-ip-con-inteligencia-artificial"],
        [PhoneForwarded, "Centralita virtual y central IP", "Suma un agente que llama a tus leads sin tocar tu centralita.", "/centralita-virtual-con-ia"],
        [Globe2, "Oficina virtual y trabajo remoto", "Tu asistente telefónico con IA llama por ti estés donde estés.", "/oficina-virtual-con-asistente-telefonico-ia"]].map(([I, t, d, to]) => (
        <Link key={t} to={to} className="group rounded-xl border border-slate-200 p-7 transition-colors hover:border-blue-300 hover:bg-blue-50/40" data-testid={`compat-${to.slice(1)}`}>
          <I className="h-5 w-5 text-blue-700" /><h3 className="mt-5 font-semibold text-slate-900">{t}</h3><p className="mt-2 text-sm text-slate-600">{d}</p>
          <span className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-blue-700">Saber más <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" /></span>
        </Link>
      ))}
    </div>
  </section>
);

export const TopicSections = ({ sections }) => (
  <section className="mx-auto max-w-4xl px-6 py-20" data-testid="topic-sections">
    {sections.map(([t, p]) => <div key={t} className="mb-12 last:mb-0"><h2 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl" style={H}>{t}</h2><p className="mt-4 text-lg leading-relaxed text-slate-600">{p}</p></div>)}
  </section>
);

export const Steps = () => (
  <section id="como" className="scroll-mt-20 bg-slate-900 text-white">
    <div className="mx-auto max-w-6xl px-6 py-20">
      <h2 className="text-3xl font-bold tracking-tight sm:text-4xl" style={H}>Cómo funciona</h2>
      <div className="mt-12 grid gap-10 md:grid-cols-3">
        {STEPS.map(([t, d], i) => <div key={t}><span className="font-mono text-sm text-blue-400">0{i + 1}</span><h3 className="mt-2 text-xl font-semibold">{t}</h3><p className="mt-2 text-sm text-slate-300">{d}</p></div>)}
      </div>
    </div>
  </section>
);

export const Countries = () => (
  <section className="vl-reveal mx-auto max-w-6xl px-6 py-24">
    <h2 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl" style={H}>Pensado para España y Chile</h2>
    <div className="mt-10 grid gap-5 md:grid-cols-2">
      {[["/es", "España", ["Número +34 gratis", "Precios en euros", "Voces en español de España", "Cumple el RGPD"]], ["/cl", "Chile", ["Número +56 gratis", "Precios en pesos chilenos", "Voces latinas naturales", "Cumple la Ley 19.628"]]].map(([to, n, items]) => (
        <Link key={to} to={to} className="rounded-xl border border-slate-200 p-7 transition-colors hover:border-blue-300" data-testid={`country-card-${to.slice(1)}`}>
          <h3 className="text-xl font-semibold text-slate-900" style={H}>Agente telefónico con IA en {n}</h3>
          <ul className="mt-4 grid grid-cols-2 gap-2 text-sm text-slate-600">{items.map((t) => <li key={t} className="flex items-center gap-2"><Check className="h-4 w-4 text-blue-600" />{t}</li>)}</ul>
        </Link>
      ))}
    </div>
  </section>
);

export const ApiBlock = () => (
  <section id="api" className="scroll-mt-20 border-y border-slate-200 bg-slate-50">
    <div className="mx-auto grid max-w-6xl gap-12 px-6 py-24 lg:grid-cols-2">
      <div>
        <h2 className="text-3xl font-bold tracking-tight text-slate-900" style={H}>Integración por API</h2>
        <p className="mt-3 text-slate-600">Automatiza llamadas de cobro, información de producto, recordatorios y encuestas desde tus propios sistemas.</p>
        <ul className="mt-8 space-y-4 text-sm">
          {[[Mic, "Voces ultra naturales con ambiente de oficina real"], [BarChart3, "Resultado, resumen y transcripción de cada llamada"], [ShieldCheck, "Claves de API por cuenta, revocables en cualquier momento"], [LifeBuoy, "Soporte en español"]].map(([I, t]) => (
            <li key={t} className="flex items-center gap-3"><I className="h-5 w-5 text-blue-700" />{t}</li>
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
    </div>
  </section>
);

export const Faq = ({ items }) => (
  <section id="faq" className="scroll-mt-20 border-t border-slate-200">
    <div className="mx-auto max-w-3xl px-6 py-20">
      <h2 className="text-3xl font-bold tracking-tight text-slate-900" style={H}>Preguntas frecuentes</h2>
      <div className="mt-10 divide-y divide-slate-200">
        {items.map(([q, a]) => (
          <details key={q} className="group py-5" data-testid="faq-item">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-semibold text-slate-900">{q}<span className="text-xl text-blue-700 transition-transform group-open:rotate-45">+</span></summary>
            <p className="mt-3 text-sm leading-relaxed text-slate-600">{a}</p>
          </details>
        ))}
      </div>
    </div>
  </section>
);

export const FinalCta = ({ page }) => (
  <section className="bg-slate-900">
    <div className="mx-auto grid max-w-6xl items-center gap-10 px-6 py-20 lg:grid-cols-2">
      <div>
        <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl" style={H}>Escúchalo tú mismo en 30 segundos</h2>
        <p className="mt-4 text-slate-300">Déjanos tu teléfono y nuestro agente te llama ahora. Es la misma experiencia que tendrán tus clientes.</p>
        <p className="mt-6 flex items-center gap-2 text-sm text-slate-400"><PhoneCall className="h-4 w-4 text-blue-400" />Llamada gratuita · Número de España o Chile incluido en todos los planes</p>
      </div>
      <InfoForm country={page.country} page={page.path} id="solicitar-final" title="Solicita información" dark />
    </div>
  </section>
);
