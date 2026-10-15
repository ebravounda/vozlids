import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Bot, CheckCircle2, Loader2, Mail, MousePointerClick, PartyPopper, XCircle } from "lucide-react";
import { Panel } from "@/components/Common";
import { api } from "@/lib/api";

const STEPS = [
  [CheckCircle2, "Pago confirmado", "Tu suscripción está activa y tu tarjeta queda vinculada para las próximas cuotas."],
  [Mail, "Estamos preparando tu línea", "Configuramos tu número de teléfono. Te enviaremos un email en cuanto tu línea esté lista para operar."],
  [Bot, "Mientras tanto, crea tu agente", "Elige su voz, su saludo y qué debe hacer en cada llamada."],
];

export default function Welcome() {
  const [params] = useSearchParams();
  const sid = params.get("session_id");
  const [state, setState] = useState(sid ? "checking" : "paid");
  useEffect(() => {
    if (!sid) return undefined;
    let tries = 0;
    const t = setInterval(async () => {
      tries += 1;
      try {
        const { data } = await api.get(`/billing/status/${sid}`);
        if (data.payment_status === "paid") { setState("paid"); clearInterval(t); }
        else if (data.status === "expired" || tries > 15) { setState(data.status === "expired" ? "failed" : "slow"); clearInterval(t); }
      } catch { if (tries > 15) { setState("slow"); clearInterval(t); } }
    }, 2000);
    return () => clearInterval(t);
  }, [sid]);

  if (state === "checking") return <div className="grid min-h-[60vh] place-items-center text-slate-500" data-testid="welcome-checking"><p><Loader2 className="mr-2 inline h-5 w-5 animate-spin" />Confirmando tu pago…</p></div>;
  if (state === "failed") return (
    <Panel className="mx-auto mt-10 max-w-lg text-center" data-testid="welcome-failed">
      <XCircle className="mx-auto h-12 w-12 text-rose-500" /><h1 className="mt-4 text-2xl font-bold text-slate-900">No se completó el pago</h1>
      <p className="mt-2 text-slate-500">No se ha cobrado nada. Puedes intentarlo de nuevo con otra tarjeta.</p>
      <Link to="/app/plan" className="mt-6 inline-block rounded-full bg-blue-600 px-6 py-2.5 font-semibold text-white" data-testid="welcome-retry-link">Volver a intentarlo</Link>
    </Panel>
  );
  return (
    <div className="fade-up mx-auto max-w-2xl py-6" data-testid="welcome-page">
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-blue-600 to-emerald-500 p-10 text-center text-white shadow-xl">
        <div className="pointer-events-none absolute inset-0 opacity-30 [background-image:radial-gradient(#fff_1.5px,transparent_1.5px)] [background-size:26px_26px]" aria-hidden />
        <PartyPopper className="relative mx-auto h-14 w-14 vl-float" />
        <h1 className="relative mt-5 text-4xl font-extrabold tracking-tight sm:text-5xl" style={{ fontFamily: "Plus Jakarta Sans" }} data-testid="welcome-title">¡Felicidades!</h1>
        <p className="relative mt-3 text-lg text-white/90">Ya estás a un paso de comenzar.</p>
        {state === "slow" && <p className="relative mt-3 text-sm text-white/80" data-testid="welcome-slow">Tu pago se está confirmando; en unos minutos lo verás reflejado en «Mi plan».</p>}
      </div>
      <ol className="mt-8 space-y-4">
        {STEPS.map(([I, t, d], i) => (
          <li key={t} className="flex gap-4 rounded-2xl border border-slate-200 bg-white p-5 vl-reveal is-in" style={{ animationDelay: `${i * 0.1}s` }}>
            <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-full ${i === 0 ? "bg-emerald-50 text-emerald-600" : "bg-blue-50 text-blue-600"}`}><I className="h-5 w-5" /></span>
            <div><p className="font-semibold text-slate-900">{t}</p><p className="mt-1 text-sm text-slate-500">{d}</p></div>
          </li>
        ))}
      </ol>
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        <Link to="/app/agentes/nuevo" className="rounded-full bg-blue-600 px-6 py-3 font-semibold text-white hover:bg-blue-700" data-testid="welcome-create-agent-link">Crear mi agente</Link>
        <Link to="/app/boton-web" className="inline-flex items-center gap-2 rounded-full border border-slate-300 px-6 py-3 font-semibold text-slate-800 hover:bg-slate-50" data-testid="welcome-widget-link"><MousePointerClick className="h-4 w-4" />Botón para mi web</Link>
      </div>
    </div>
  );
}
