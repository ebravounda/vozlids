import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, ArrowRight, Bot, CalendarDays, Clock, CreditCard, Hash, LifeBuoy, MousePointerClick, PhoneCall, PhoneOutgoing, Sparkles, X } from "lucide-react";

const STEPS = [
  { icon: Sparkles, title: "¡Bienvenido a VozLeads!", text: "Te enseñamos tu panel en 1 minuto. Puedes cerrar este recorrido cuando quieras y volver a verlo desde «Ver tutorial» en el menú." },
  { target: "agents", icon: Bot, title: "1 · Crea tu agente IA", text: "Tu agente atiende y hace llamadas por ti. Elige su voz y su acento, cómo saluda, qué debe hacer (recepcionista, agendar citas, ventas…) y escúchalo antes de activarlo." },
  { target: "mynumber", icon: Hash, title: "2 · Tu número está en proceso", text: "Estamos asignando tu número de teléfono. Puede tardar de 1 a 24 horas, según las solicitudes en curso y la disponibilidad de números. Te avisaremos por email.", note: "Por ley, el número va a tu nombre: entra en «Mi número» y sube tus documentos de identidad (cédula, DNI o pasaporte). Sin ellos no podemos activarlo." },
  { target: "leads", icon: PhoneCall, title: "3 · Leads y llamadas", text: "Aquí verás cada llamada: quién llamó, un resumen hecho por la IA, la grabación, el idioma y si quedó como cita, venta o interesado." },
  { target: "agenda", icon: CalendarDays, title: "4 · Agenda y citas", text: "Las citas que agenda tu agente aparecen en tu calendario y te llega un recordatorio por email antes de cada una." },
  { target: "outbound", icon: PhoneOutgoing, title: "5 · Llamadas salientes", text: "Lanza llamadas a tus contactos: tu agente los llama, les presenta tu oferta y te deja anotado el resultado." },
  { target: "webwidget", icon: MousePointerClick, title: "6 · Botón para tu web", text: "Pon un botón en tu web para que tus visitantes reciban una llamada de tu agente al momento." },
  { target: "support", icon: LifeBuoy, title: "7 · Asistencia técnica", text: "¿Dudas o algo no va bien? Escríbenos desde aquí y te ayudamos." },
  { target: "plan", icon: CreditCard, title: "8 · Mi plan y minutos", text: "Revisa tus minutos usados, cuándo se renuevan y mejora tu plan si lo necesitas." },
  { icon: Clock, title: "¡Todo listo!", text: "Mientras preparamos tu número, crea tu primer agente: en unos minutos lo tendrás listo para atender.", cta: true },
];

function useRect(target, step) {
  const [rect, setRect] = useState(null);
  const measure = useCallback(() => {
    const el = target && document.querySelector(`[data-testid="sidebar-nav-${target}"]`);
    if (!el || !el.offsetParent) return setRect(null);
    el.scrollIntoView({ block: "nearest" });
    const r = el.getBoundingClientRect();
    setRect({ top: r.top - 6, left: r.left - 6, width: r.width + 12, height: r.height + 12 });
  }, [target]);
  useLayoutEffect(() => { measure(); }, [measure, step]);
  useEffect(() => { window.addEventListener("resize", measure); return () => window.removeEventListener("resize", measure); }, [measure]);
  return rect;
}

function Card({ s, i, rect, go, close, finish }) {
  const pos = rect ? { top: Math.min(Math.max(16, rect.top - 24), window.innerHeight - 360), left: rect.left + rect.width + 20 } : null;
  return (
    <div key={i} role="dialog" aria-label={s.title} data-testid="tour-card"
      className={`tour-pop fixed z-[102] w-[min(380px,calc(100vw-32px))] rounded-2xl border border-white/60 bg-white p-6 shadow-2xl ${pos ? "" : "left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2"}`} style={pos || undefined}>
      {pos && <span className="absolute -left-2 top-10 h-4 w-4 rotate-45 bg-white" aria-hidden />}
      <button onClick={close} className="absolute right-3 top-3 rounded-full p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700" aria-label="Cerrar" data-testid="tour-close"><X className="h-4 w-4" /></button>
      <span className="grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-br from-blue-600 to-cyan-500 text-white shadow-lg shadow-blue-500/30"><s.icon className="h-5 w-5" /></span>
      <h3 className="mt-4 pr-6 text-lg font-bold text-slate-900" data-testid="tour-title">{s.title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-slate-600">{s.text}</p>
      {s.note && <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-relaxed text-amber-900" data-testid="tour-kyc-note">{s.note}</p>}
      <div className="mt-5 flex items-center gap-1.5" aria-hidden>
        {STEPS.map((_, k) => <span key={k} className={`h-1.5 rounded-full transition-[width,background-color] duration-300 ${k === i ? "w-6 bg-blue-600" : k < i ? "w-1.5 bg-blue-300" : "w-1.5 bg-slate-200"}`} />)}
        <span className="ml-auto text-xs text-slate-400" data-testid="tour-progress">{i + 1} / {STEPS.length}</span>
      </div>
      <div className="mt-4 flex items-center gap-2">
        {i > 0 && <button onClick={() => go(-1)} className="inline-flex items-center gap-1 rounded-full px-3 py-2 text-sm font-medium text-slate-500 transition-colors hover:bg-slate-100" data-testid="tour-prev"><ArrowLeft className="h-4 w-4" />Atrás</button>}
        {i === 0 && <button onClick={close} className="rounded-full px-3 py-2 text-sm font-medium text-slate-500 transition-colors hover:bg-slate-100" data-testid="tour-skip">Saltar</button>}
        {s.cta ? <button onClick={finish} className="group ml-auto inline-flex items-center gap-2 rounded-full bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white transition-[transform,background-color] hover:-translate-y-0.5 hover:bg-blue-700" data-testid="tour-finish">Crear mi primer agente<ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" /></button>
          : <button onClick={() => go(1)} className="group ml-auto inline-flex items-center gap-2 rounded-full bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white transition-[transform,background-color] hover:-translate-y-0.5 hover:bg-blue-700" data-testid="tour-next">{i === 0 ? "Empezar" : "Siguiente"}<ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" /></button>}
      </div>
    </div>
  );
}

export function Tour({ onClose }) {
  const [i, setI] = useState(0);
  const nav = useNavigate();
  const s = STEPS[i];
  const rect = useRect(s.target, i);
  const go = useCallback((d) => setI((k) => Math.min(STEPS.length - 1, Math.max(0, k + d))), []);
  useEffect(() => {
    const key = (e) => { if (e.key === "Escape") onClose(); if (e.key === "ArrowRight") go(1); if (e.key === "ArrowLeft") go(-1); };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [go, onClose]);
  return (
    <div className="fixed inset-0 z-[100]" data-testid="tour-overlay">
      {rect ? <div className="pointer-events-none fixed z-[101] rounded-2xl ring-2 ring-blue-400 transition-[top,left,width,height] duration-500 ease-out"
        style={{ ...rect, boxShadow: "0 0 0 9999px rgba(15,23,42,0.62), 0 0 32px 4px rgba(59,130,246,0.55)" }} data-testid="tour-spotlight" />
        : <div className="fixed inset-0 backdrop-blur-[2px]" style={{ background: "rgba(15,23,42,0.62)" }} />}
      <div className="fixed inset-0" onClick={(e) => e.stopPropagation()} />
      <Card s={s} i={i} rect={rect} go={go} close={onClose} finish={() => { onClose(); nav("/app/agentes/nuevo"); }} />
    </div>
  );
}
