import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { ArrowRight, BookOpen, FlaskConical, KeyRound, Loader2, ShieldCheck, Webhook } from "lucide-react";
import { Footer, Nav } from "@/components/landing/Chrome";
import { Code, QUICKSTART, WEBHOOK_PAYLOAD, WEBHOOK_VERIFY } from "@/components/apidocs/Code";
import { Endpoint, Method } from "@/components/apidocs/Endpoint";

const H = { fontFamily: "Plus Jakarta Sans" };
const SPEC = `${process.env.REACT_APP_BACKEND_URL}/api/v1/openapi.json`;
const EVENTS = ["call.created", "call.started", "call.completed", "call.no_answer", "call.failed", "call.cancelled"];
const GUIDES = [["inicio", "Inicio rápido"], ["autenticacion", "Autenticación"], ["webhooks", "Webhooks"], ["errores", "Errores y límites"]];

function useSpec() {
  const [spec, setSpec] = useState(null);
  const [error, setError] = useState(false);
  useEffect(() => { axios.get(SPEC).then((r) => setSpec(r.data)).catch(() => setError(true)); }, []);
  return { spec, error };
}

const Section = ({ id, title, children }) => (
  <section id={id} className="scroll-mt-24 border-b border-slate-200 py-12" data-testid={`api-guide-${id}`}>
    <h2 className="text-2xl font-bold tracking-tight text-slate-900" style={H}>{title}</h2>
    <div className="mt-4 space-y-4 text-slate-600">{children}</div>
  </section>
);

const Pill = ({ c }) => <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[13px] text-slate-800">{c}</code>;

function Sidebar({ groups }) {
  return (
    <aside className="hidden lg:block">
      <nav className="sticky top-24 max-h-[calc(100vh-7rem)] space-y-6 overflow-y-auto pb-10 text-sm" data-testid="api-docs-sidebar">
        <div><p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-400">Guías</p>
          {GUIDES.map(([id, l]) => <a key={id} href={`#${id}`} className="block rounded-md px-2 py-1.5 text-slate-700 hover:bg-slate-100">{l}</a>)}</div>
        {groups.map(([tag, ops]) => (
          <div key={tag}><p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-400">{tag}</p>
            {ops.map((o) => <a key={o.op.operationId} href={`#${o.op.operationId}`} className="flex items-center gap-2 rounded-md px-2 py-1.5 text-slate-700 hover:bg-slate-100"><span className="font-mono text-[10px] font-bold uppercase text-slate-400">{o.method}</span><span className="truncate">{o.op.summary}</span></a>)}</div>
        ))}
      </nav>
    </aside>
  );
}

function Hero({ count }) {
  return (
    <div className="border-b border-slate-200 bg-slate-950">
      <div className="mx-auto max-w-6xl px-6 py-20">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-400">Desarrolladores · API REST v1</p>
        <h1 className="mt-4 max-w-3xl text-4xl font-extrabold tracking-tight text-white sm:text-5xl" style={H} data-testid="api-docs-title">Lanza llamadas con IA desde tu CRM en 5 minutos</h1>
        <p className="mt-5 max-w-2xl text-lg text-slate-300">Crea llamadas, recibe el resultado por webhook y cumple el RGPD con {count || 15} endpoints sencillos. Prueba gratis con claves de sandbox: simulan la llamada sin coste.</p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link to="/registro" className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-3 text-sm font-semibold text-white hover:bg-blue-500" data-testid="api-docs-register-button">Conseguir mi clave <ArrowRight className="h-4 w-4" /></Link>
          <a href={`${process.env.REACT_APP_BACKEND_URL}/api/v1/docs`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 rounded-lg border border-slate-700 px-5 py-3 text-sm font-semibold text-white hover:bg-slate-800" data-testid="api-docs-try-button"><FlaskConical className="h-4 w-4" /> Probar en vivo</a>
          <a href={SPEC} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 rounded-lg px-5 py-3 text-sm font-semibold text-slate-300 hover:text-white" data-testid="api-docs-openapi-link"><BookOpen className="h-4 w-4" /> OpenAPI 3.1</a>
        </div>
      </div>
    </div>
  );
}

function Guides() {
  return (
    <>
      <Section id="inicio" title="Inicio rápido">
        <p>1. Crea tu cuenta y un agente. 2. En <b>Panel → API desarrolladores</b> genera una clave <Pill c="vl_test_…" /> (sandbox) o <Pill c="vl_live_…" /> (llamadas reales). 3. Lanza tu primera llamada:</p>
        <Code tabs={QUICKSTART} testid="api-quickstart-code" />
        <p>La respuesta <Pill c="202" /> devuelve el <Pill c="id" /> de la llamada. Consulta su estado con <Pill c="GET /calls/{id}" /> o, mejor, recibe el resultado por webhook. Repite la misma <Pill c="Idempotency-Key" /> y nunca se duplicará una llamada.</p>
      </Section>
      <Section id="autenticacion" title="Autenticación">
        <p className="flex gap-3"><KeyRound className="mt-0.5 h-5 w-5 shrink-0 text-blue-600" />Envía tu clave en la cabecera <Pill c="X-API-Key" /> en cada petición, siempre desde tu servidor. Nunca la pongas en el código de una web o una app: quien la vea podría lanzar llamadas en tu nombre.</p>
        <p className="flex gap-3"><ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-blue-600" />Puedes tener varias claves con permisos distintos y revocarlas al instante desde el panel. Solo guardamos una huella irreversible de cada clave (nunca la clave): si la pierdes, crea otra.</p>
      </Section>
      <Section id="webhooks" title="Webhooks">
        <p className="flex gap-3"><Webhook className="mt-0.5 h-5 w-5 shrink-0 text-blue-600" />Registra una URL con <Pill c="POST /webhooks" /> y elige los eventos:</p>
        <div className="flex flex-wrap gap-2">{EVENTS.map((e) => <Pill key={e} c={e} />)}</div>
        <Code tabs={WEBHOOK_PAYLOAD} testid="api-webhook-payload" />
        <p>Cada envío lleva la cabecera <Pill c="VozLeads-Signature: t=<ts>,v1=<hex>" />, una firma HMAC-SHA256 de <Pill c={"\"<ts>.<cuerpo>\""} /> con el secreto del webhook. Compruébala siempre:</p>
        <Code tabs={WEBHOOK_VERIFY} testid="api-webhook-verify" />
      </Section>
      <Section id="errores" title="Errores y límites">
        <p>Los errores siguen el estándar RFC 9457 (<Pill c="application/problem+json" />) con un <Pill c="code" /> estable y un <Pill c="request_id" /> para soporte.</p>
        <ul className="grid gap-2 text-sm sm:grid-cols-2">
          {[["401", "Clave ausente o no válida"], ["402", "Minutos del plan agotados"], ["409", "Fuera de horario legal o número excluido"], ["422", "Datos no válidos"], ["429", "Límite superado: respeta Retry-After"]].map(([c, t]) => <li key={c} className="flex gap-3 rounded-lg border border-slate-200 bg-white p-3"><span className="font-mono font-bold text-slate-900">{c}</span>{t}</li>)}
        </ul>
        <p>Límites por defecto: 120 peticiones y 30 llamadas por minuto. Las llamadas simultáneas y diarias dependen de tu plan. Consúltalos con <Pill c="GET /account/limits" />.</p>
      </Section>
    </>
  );
}

export default function ApiDocs() {
  const { spec, error } = useSpec();
  const groups = useMemo(() => {
    if (!spec) return [];
    const by = {};
    Object.entries(spec.paths).forEach(([path, ms]) => Object.entries(ms).forEach(([method, op]) => (by[op.tags?.[0] || "Otros"] ||= []).push({ path, method, op })));
    return Object.entries(by);
  }, [spec]);
  useEffect(() => { document.title = "API para desarrolladores · VozLeads"; }, []);
  return (
    <div className="min-h-screen bg-white text-slate-700" style={{ fontFamily: "'DM Sans', sans-serif" }} data-testid="api-docs-page">
      <Nav home />
      <Hero count={groups.reduce((n, [, o]) => n + o.length, 0)} />
      <div className="mx-auto grid max-w-6xl gap-10 px-6 lg:grid-cols-[220px_1fr]">
        <Sidebar groups={groups} />
        <main className="min-w-0 pb-20">
          <Guides />
          {error && <p className="py-10 text-rose-600" data-testid="api-docs-error">No se pudo cargar la referencia. Recarga la página.</p>}
          {!spec && !error && <p className="flex items-center gap-2 py-10 text-slate-500"><Loader2 className="h-4 w-4 animate-spin" /> Cargando referencia…</p>}
          {groups.map(([tag, ops]) => (
            <section key={tag} className="py-12" data-testid={`api-group-${tag}`}>
              <h2 className="text-2xl font-bold tracking-tight text-slate-900" style={H}>{tag}</h2>
              <div className="mt-3 mb-6 space-y-1 rounded-xl border border-slate-200 bg-slate-50 p-3">{ops.map((o) => <a key={o.op.operationId} href={`#${o.op.operationId}`} className="flex items-center gap-3 rounded-md px-2 py-1 text-sm hover:bg-white"><Method m={o.method} /><code className="font-mono text-slate-800">{o.path}</code></a>)}</div>
              <div className="space-y-5">{ops.map((o) => <Endpoint key={o.op.operationId} {...o} schemas={spec.components?.schemas || {}} />)}</div>
            </section>
          ))}
        </main>
      </div>
      <Footer />
    </div>
  );
}
