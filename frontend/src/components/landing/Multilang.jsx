import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Globe2, Languages, Mic2, PhoneCall, Play, Square } from "lucide-react";

const H = { fontFamily: "Plus Jakarta Sans" };
const LANGS = [
  ["en", "🇬🇧", "English", "Jenny", "English, please.", "Of course! I'm Jenny and I'll help you in English. How can I help you?"],
  ["pt", "🇧🇷", "Português", "Francisca", "Português, por favor.", "Claro! Sou a Francisca e vou atendê-lo em português. Em que posso ajudar?"],
  ["fr", "🇫🇷", "Français", "Denise", "En français, s'il vous plaît.", "Bien sûr ! Je suis Denise, je vais vous aider en français. Comment puis-je vous aider ?"],
  ["ca", "CAT", "Català", "Joana", "En català, si us plau.", "I tant! Sóc la Joana i t'atendré en català. En què et puc ajudar?"],
  ["it", "🇮🇹", "Italiano", "Elsa", "In italiano, per favore.", "Certo! Sono Elsa e la assisto in italiano. Come posso aiutarla?"],
  ["de", "🇩🇪", "Deutsch", "Katja", "Auf Deutsch, bitte.", "Natürlich! Ich bin Katja und helfe Ihnen gerne auf Deutsch. Was kann ich für Sie tun?"],
];
const ACCENTS = ["España", "Chileno", "Argentino", "Mexicano", "Colombiano", "Peruano", "Latino neutro", "Americano", "Británico", "Brasileño", "Portugal", "Francia", "Catalán", "Italia", "Alemania"];

const Flag = ({ f }) => (f === "CAT"
  ? <span className="inline-block h-3.5 w-5 rounded-[2px]" style={{ background: "repeating-linear-gradient(#fcdd09 0 2.2px, #da121a 2.2px 3.9px)" }} aria-hidden />
  : <span className="text-lg leading-none">{f}</span>);

function Bubble({ who, text, me, delay, live }) {
  return (
    <div className={`ml-fade flex ${me ? "justify-end" : ""}`} style={{ animationDelay: `${delay}ms` }}>
      <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed transition-shadow duration-300 ${me ? "rounded-br-md bg-blue-600 text-white" : "rounded-bl-md bg-white text-slate-700 shadow-sm"} ${live ? "ring-2 ring-emerald-400 ring-offset-2" : ""}`}>
        <span className={`mb-0.5 block text-[11px] font-semibold ${me ? "text-blue-100" : "text-slate-400"}`}>{who}</span>{text}
      </div>
    </div>
  );
}

function CallMock() {
  const [i, setI] = useState(0);
  const [auto, setAuto] = useState(true);
  const [part, setPart] = useState(-1);
  const audio = useRef(null);
  const stop = () => { audio.current?.pause(); audio.current = null; setPart(-1); };
  useEffect(() => stop, []);
  const play = (code) => {
    stop(); setAuto(false);
    const seq = [`/demo/lang/q_${code}.wav`, `/demo/lang/c_${code}.mp3`, `/demo/lang/r_${code}.mp3`];
    const run = (k) => {
      if (k >= seq.length) return setPart(-1);
      const a = new Audio(seq[k]);
      audio.current = a; setPart(k);
      a.onended = () => { if (audio.current === a) setTimeout(() => audio.current === a && run(k + 1), 350); };
      a.play().catch(() => setPart(-1));
    };
    run(0);
  };
  useEffect(() => {
    if (!auto) return undefined;
    const t = setInterval(() => setI((k) => (k + 1) % LANGS.length), 5200);
    return () => clearInterval(t);
  }, [auto]);
  const [code, , native, name, ask, reply] = LANGS[i];
  return (
    <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5 shadow-xl shadow-slate-200/60" data-testid="multilang-demo">
      <div className="flex flex-wrap gap-2">
        {LANGS.map(([c, f, n], k) => (
          <button key={c} type="button" onClick={() => { stop(); setI(k); setAuto(false); }} data-testid={`multilang-tab-${c}`}
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors ${k === i ? "border-blue-600 bg-blue-600 text-white" : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"}`}>
            <Flag f={f} />{n}
          </button>
        ))}
      </div>
      <div className="mt-5 flex items-center gap-3 rounded-2xl bg-white p-3 shadow-sm">
        <span className="relative grid h-10 w-10 place-items-center rounded-full bg-emerald-500 text-white"><PhoneCall className="h-4 w-4" /><span className="absolute inset-0 animate-ping rounded-full bg-emerald-400/40" /></span>
        <div className="min-w-0 flex-1"><p className="text-sm font-semibold text-slate-900">Llamada entrante · Clínica Sonrisa</p><p className="text-xs text-slate-500">Atiende Marta · español</p></div>
        <button type="button" onClick={() => (part >= 0 ? stop() : play(code))} data-testid="multilang-play-button"
          className="inline-flex items-center gap-1.5 rounded-full bg-blue-600 px-3.5 py-1.5 text-xs font-semibold text-white transition-[transform,background-color] hover:-translate-y-0.5 hover:bg-blue-700">
          {part >= 0 ? <><Square className="h-3 w-3 fill-current" />Detener</> : <><Play className="h-3 w-3 fill-current" />Escuchar</>}
        </button>
      </div>
      <div key={code} className="mt-4 space-y-3" data-testid="multilang-dialog">
        <Bubble who="Marta · agente IA" text={`Hola, Clínica Sonrisa, te atiende Marta. ¿En qué idioma prefieres que te atienda: español o ${native}?`} delay={0} live={part === 0} />
        <Bubble who="Cliente" text={ask} me delay={700} live={part === 1} />
        <div className="ml-fade flex items-center gap-2 text-xs font-medium text-blue-700" style={{ animationDelay: "1300ms" }}>
          <span className="h-px flex-1 bg-blue-200" /><Languages className="h-3.5 w-3.5" />Marta pasa la llamada a {name}, ejecutiva nativa<span className="h-px flex-1 bg-blue-200" />
        </div>
        <Bubble who={`${name} · agente IA`} text={reply} delay={1900} live={part === 2} />
      </div>
    </div>
  );
}

export const Multilang = () => (
  <section id="idiomas" className="vl-reveal scroll-mt-20 border-b border-slate-200 bg-white" data-testid="multilang-section">
    <div className="mx-auto grid max-w-6xl items-center gap-14 px-6 py-24 lg:grid-cols-2">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-600">Atención en varios idiomas</p>
        <h2 className="mt-3 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl" style={H}>Tus clientes eligen el idioma. Contesta una voz nativa.</h2>
        <p className="mt-4 text-lg leading-relaxed text-slate-600">Tu agente pregunta en qué idioma prefieren que les atiendan y, si eligen otro, pasa la llamada al instante a un ejecutivo nativo de ese idioma. Se queda con todo lo hablado y sigue agendando citas, tomando recados o vendiendo.</p>
        <ul className="mt-6 space-y-3 text-slate-700">
          {[[Globe2, "Español, inglés, portugués, francés, catalán, italiano y alemán"], [Mic2, "Cada idioma con su propio ejecutivo: su nombre, su voz y su acento"], [Languages, "Tú decides en qué idiomas puede atender cada agente"]].map(([I, t]) => (
            <li key={t} className="flex items-start gap-3"><span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-blue-50 text-blue-700"><I className="h-4 w-4" /></span>{t}</li>
          ))}
        </ul>
        <p className="mt-8 text-sm font-semibold text-slate-900">Decenas de voces y acentos para elegir</p>
        <div className="mt-3 flex flex-wrap gap-2" data-testid="multilang-accents">
          {ACCENTS.map((a, k) => <span key={a} className="ml-fade rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600" style={{ animationDelay: `${k * 40}ms` }}>Acento {a}</span>)}
        </div>
        <Link to="/registro" className="group mt-8 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-3 text-sm font-semibold text-white hover:bg-blue-700" data-testid="multilang-register-button">Empezar ahora <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" /></Link>
      </div>
      <CallMock />
    </div>
  </section>
);
