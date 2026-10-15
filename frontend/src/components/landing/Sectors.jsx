import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Brain, Check, ChevronRight, Coffee, Dumbbell, GraduationCap, Home, Loader2, Pause, Play, Scale, Scissors, Smile, Sparkles, UtensilsCrossed, Wrench } from "lucide-react";
import { SEO_PAGES } from "@/components/Seo";
import { InfoForm } from "@/components/landing/InfoForm";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/public/sector-demo`;
const H = { fontFamily: "Plus Jakarta Sans" };
const ICONS = { Smile, Sparkles, Brain, Scissors, UtensilsCrossed, Coffee, Scale, Home, Wrench, Dumbbell, GraduationCap };
const player = { audio: null, stop: null };

export const sectorsFor = (country) => SEO_PAGES.filter((p) => p.type === "sector" && p.country === (country === "CL" ? "CL" : "ES"));
const src = (p) => `${API}/${p.country.toLowerCase()}/${p.sector}.mp3`;
const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

export function useDemo(page) {
  const [state, setState] = useState("idle");
  const [t, setT] = useState(0);
  const [dur, setDur] = useState(0);
  const [marks, setMarks] = useState(null);
  const ref = useRef(null);
  useEffect(() => () => { if (ref.current) { ref.current.pause(); ref.current = null; } }, [page.path]);
  const toggle = () => {
    if (state === "playing") { ref.current.pause(); setState("paused"); return; }
    if (player.audio && player.audio !== ref.current) player.stop?.();
    if (!ref.current) {
      const a = new Audio(src(page));
      a.ontimeupdate = () => setT(a.currentTime);
      a.onloadedmetadata = () => setDur(a.duration);
      a.onplaying = () => { setState("playing"); if (!marks) fetch(`${API}/${page.country.toLowerCase()}/${page.sector}/marks`).then((r) => r.json()).then((d) => setMarks(d.marks)).catch(() => {}); };
      a.onended = () => { setState("idle"); setT(0); };
      a.onerror = () => setState("error");
      ref.current = a;
    }
    player.audio = ref.current;
    player.stop = () => { ref.current?.pause(); setState("paused"); };
    setState("loading");
    ref.current.play().catch(() => setState("error"));
  };
  const active = marks ? marks.reduce((i, m, k) => (t >= m ? k : i), -1) : -1;
  return { state, t, dur, toggle, active };
}

const PlayIcon = ({ state, className }) => (state === "loading" ? <Loader2 className={`${className} animate-spin`} /> : state === "playing" ? <Pause className={className} /> : <Play className={`${className} translate-x-[1px]`} />);

export function SectorPlayer({ page }) {
  const d = useDemo(page);
  const agent = page.dialog[0][1].match(/(soy|habla|atiende) (\w+)/i)?.[2] || "Agente";
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[0_30px_80px_-30px_rgba(15,23,42,0.35)]" data-testid="sector-player">
      <div className="relative h-48 sm:h-56">
        <img src={page.img} alt={`${page.name}: recepción atendida por un asistente telefónico con IA`} className="h-full w-full object-cover" loading="eager" />
        <div className="absolute inset-0 bg-gradient-to-t from-slate-950/85 via-slate-950/30 to-transparent" />
        <div className="absolute inset-x-0 bottom-0 flex items-end gap-4 p-5">
          <button onClick={d.toggle} className="grid h-14 w-14 shrink-0 place-items-center rounded-full bg-blue-600 text-white shadow-lg transition-transform hover:scale-105 active:scale-95" aria-label="Escuchar llamada de ejemplo" data-testid="sector-player-play-button">
            <PlayIcon state={d.state} className="h-6 w-6" />
          </button>
          <div className="min-w-0 flex-1 text-white">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-200">Llamada de ejemplo</p>
            <p className="truncate font-semibold" data-testid="sector-player-biz">{page.biz}</p>
            <div className="mt-2 h-1 overflow-hidden rounded-full bg-white/25"><div className="h-full bg-white transition-[width] duration-200" style={{ width: `${d.dur ? (100 * d.t) / d.dur : 0}%` }} /></div>
          </div>
          <span className="font-mono text-xs text-white/80" data-testid="sector-player-time">{fmt(d.t)}{d.dur ? ` / ${fmt(d.dur)}` : ""}</span>
        </div>
      </div>
      {d.state === "error" && <p className="px-5 pt-3 text-xs text-rose-600" data-testid="sector-player-error">No se pudo cargar el audio. Inténtalo de nuevo en unos segundos.</p>}
      <ol className="max-h-[300px] space-y-2 overflow-auto p-5 text-[13px] leading-snug" aria-label="Transcripción de la llamada" data-testid="sector-transcript">
        {page.dialog.map(([who, text], i) => (
          <li key={i} className={`w-fit max-w-[90%] rounded-xl px-3 py-2 transition-colors duration-300 ${who === "caller" ? "ml-auto" : ""} ${d.active === i ? "bg-blue-600 text-white" : who === "caller" ? "bg-slate-900/90 text-white" : "bg-slate-100 text-slate-700"}`}>
            <span className={`mb-0.5 block text-[10px] font-semibold uppercase tracking-wider ${d.active === i ? "text-blue-100" : "opacity-60"}`}>{who === "caller" ? "Cliente" : `${agent} · IA`}</span>{text}
          </li>
        ))}
      </ol>
    </div>
  );
}

function SectorCard({ p }) {
  const d = useDemo(p);
  const Icon = ICONS[p.icon] || Smile;
  return (
    <article className="group overflow-hidden rounded-2xl border border-slate-200 bg-white transition-[transform,box-shadow] duration-300 hover:-translate-y-1 hover:shadow-[0_24px_50px_-24px_rgba(15,23,42,0.35)]" data-testid={`sector-card-${p.sector}`}>
      <div className="relative h-40 overflow-hidden">
        <img src={p.img} alt={`Asistente telefónico con IA para ${p.name.toLowerCase()}`} loading="lazy" className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105" />
        <div className="absolute inset-0 bg-gradient-to-t from-slate-950/70 to-transparent" />
        <span className="absolute left-4 top-4 grid h-9 w-9 place-items-center rounded-lg bg-white/90 text-blue-700 backdrop-blur"><Icon className="h-4 w-4" /></span>
        <button onClick={d.toggle} className="absolute bottom-3 right-3 flex items-center gap-2 rounded-full bg-white px-3.5 py-2 text-xs font-semibold text-slate-900 shadow transition-transform hover:scale-105" data-testid={`sector-card-play-${p.sector}`}>
          <PlayIcon state={d.state} className="h-3.5 w-3.5" />{d.state === "playing" ? fmt(d.t) : "Escuchar llamada"}
        </button>
      </div>
      <div className="p-5">
        <h3 className="font-semibold text-slate-900" style={H}>{p.name}</h3>
        <p className="mt-1.5 line-clamp-2 text-sm text-slate-600">{p.sections[0][0]}</p>
        <Link to={p.path} className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-blue-700" data-testid={`sector-card-link-${p.sector}`}>Ver solución <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" /></Link>
      </div>
    </article>
  );
}

export const Sectors = ({ country, exclude, title = "Un recepcionista con IA para tu tipo de negocio" }) => (
  <section id="sectores" className="vl-reveal scroll-mt-20 mx-auto max-w-6xl px-6 py-24" data-testid="sectors-section">
    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-600">Sectores</p>
    <h2 className="mt-3 max-w-3xl text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl" style={H}>{title}</h2>
    <p className="mt-3 max-w-2xl text-slate-600">Escucha cómo contesta en una clínica, una barbería o un restaurante. Cada ejemplo usa una voz natural con acento de {country === "CL" ? "Chile" : "España"}.</p>
    <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
      {sectorsFor(country).filter((p) => p.sector !== exclude).map((p) => <SectorCard key={p.path} p={p} />)}
      <a href="#solicitar" className="group flex flex-col justify-between rounded-2xl border border-dashed border-blue-300 bg-blue-50/50 p-6 transition-colors hover:bg-blue-50" data-testid="sector-card-other">
        <div><p className="font-semibold text-slate-900" style={H}>¿Otro tipo de negocio?</p><p className="mt-2 text-sm text-slate-600">Veterinarias, ópticas, fisioterapia, hoteles… Configuramos el agente con tu información y tus horarios.</p></div>
        <span className="mt-6 inline-flex items-center gap-1 text-sm font-semibold text-blue-700">Recibe una llamada de prueba <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" /></span>
      </a>
    </div>
  </section>
);

export const SectorHero = ({ page, m }) => (
  <section className="relative overflow-hidden border-b border-slate-200 bg-[#F8FAFC]" data-testid="sector-hero">
    <div className="pointer-events-none absolute inset-0 opacity-60 [background-image:radial-gradient(#CBD5E1_1px,transparent_1px)] [background-size:22px_22px] [mask-image:linear-gradient(to_bottom,black,transparent_75%)]" aria-hidden />
    <div className="relative mx-auto grid max-w-6xl items-start gap-12 px-6 py-12 lg:grid-cols-[1.1fr_1fr] lg:py-16">
      <div className="fade-up min-w-0">
        <nav aria-label="Ruta" className="mb-6 flex flex-wrap items-center gap-1 text-xs text-slate-500" data-testid="sector-breadcrumb">
          <Link to="/" className="hover:text-slate-900">VozLeads</Link><ChevronRight className="h-3 w-3" />
          <Link to={`/${page.country.toLowerCase()}`} className="hover:text-slate-900">{page.country === "CL" ? "Chile" : "España"}</Link><ChevronRight className="h-3 w-3" />
          <span className="text-slate-700">{page.name}</span>
        </nav>
        <p className="mb-5 inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm" data-testid="hero-eyebrow"><span className="h-2 w-2 rounded-full bg-emerald-500 vl-pulse" />{page.eyebrow}</p>
        <h1 className="text-4xl font-extrabold leading-[1.06] tracking-tight text-slate-900 sm:text-5xl" style={H} data-testid="hero-title">{page.h1}</h1>
        <p className="mt-5 max-w-xl text-lg leading-relaxed text-slate-600">{page.intro}</p>
        <ul className="mt-6 grid gap-2 text-sm text-slate-700 sm:grid-cols-2">
          {[m.t.short, "Contesta 24/7 al primer tono", `Agenda ${page.country === "CL" ? "horas" : "citas"} en tu calendario`, "Sin permanencia"].map((t) => <li key={t} className="flex items-center gap-2"><Check className="h-4 w-4 text-blue-600" />{t}</li>)}
        </ul>
        <div className="mt-8"><SectorPlayer page={page} /></div>
      </div>
      <div className="fade-up lg:sticky lg:top-24" style={{ animationDelay: "0.15s" }}><InfoForm m={m} page={page.path} title={`Pruébalo gratis en tu ${page.country === "CL" ? "negocio" : "negocio"}`} /></div>
    </div>
  </section>
);
