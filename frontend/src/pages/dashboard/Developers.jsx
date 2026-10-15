import { useEffect, useState } from "react";
import { BookOpen, ExternalLink } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader, Panel } from "@/components/Common";
import { Code, Keys, Webhooks } from "@/components/DevParts";
import { API, api } from "@/lib/api";

const BASE = `${API}/v1`;
const EX = {
  cURL: `curl -X POST ${BASE}/calls \\
  -H "X-API-Key: vl_test_..." \\
  -H "Idempotency-Key: pedido-1234" \\
  -H "Content-Type: application/json" \\
  -d '{"agent_id":"AGENT_ID","name":"Ana López","phone":"+34612345678",
       "type":"recordatorio","legal_basis":"contract",
       "context":{"cita":"jueves 17:00"},"metadata":{"crm_id":"1234"}}'`,
  JavaScript: `const r = await fetch("${BASE}/calls", {
  method: "POST",
  headers: { "X-API-Key": process.env.VOZLEADS_KEY, "Idempotency-Key": crypto.randomUUID(),
             "Content-Type": "application/json" },
  body: JSON.stringify({ agent_id: "AGENT_ID", name: "Ana López", phone: "+34612345678",
                         type: "recordatorio", legal_basis: "contract" }),
});
const call = await r.json(); // 202 → { id, status: "queued", ... }`,
  Python: `import os, uuid, requests
r = requests.post("${BASE}/calls", timeout=15,
    headers={"X-API-Key": os.environ["VOZLEADS_KEY"], "Idempotency-Key": str(uuid.uuid4())},
    json={"agent_id": "AGENT_ID", "name": "Ana López", "phone": "+34612345678",
          "type": "recordatorio", "legal_basis": "contract"})
call = r.json()  # 202 → {"id": ..., "status": "queued"}`,
  "Verificar webhook": `# Cabecera: VozLeads-Signature: t=<timestamp>,v1=<hex>
import hmac, hashlib, time
def verify(secret: str, header: str, body: bytes) -> bool:
    parts = dict(p.split("=", 1) for p in header.split(","))
    if abs(time.time() - int(parts["t"])) > 300:   # protección contra repetición
        return False
    expected = hmac.new(secret.encode(), f"{parts['t']}.".encode() + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, parts["v1"])
# Guarda VozLeads-Event-Id y descarta los eventos ya procesados.`,
};
const STATES = [["scheduled", "Programada"], ["queued", "En cola"], ["ringing", "Sonando"], ["in_progress", "En curso"], ["completed", "Completada"], ["no_answer", "Sin respuesta / buzón"], ["busy", "Ocupado"], ["failed", "Fallida"], ["cancelled", "Cancelada"]];
const ERRORS = [["401", "invalid_api_key, api_key_expired"], ["402", "minutes_exhausted (se mantiene por compatibilidad)"], ["403", "missing_scope, ip_not_allowed"], ["404", "agent_not_found, call_not_found"], ["409", "outside_calling_hours, do_not_call, not_cancellable, idempotency_in_progress"], ["422", "validation_error, legal_basis_required, subject_required, invalid_retention, invalid_phone, destination_not_allowed, idempotency_mismatch"], ["429", "rate_limited, concurrency_limit, daily_limit (con Retry-After)"]];
const CHANGELOG = [["1.2.0 · jun 2026", "Permiso privacy:manage: POST /privacy/export y /privacy/erase (RGPD), GET/PUT /account/retention (borrado automático de transcripciones y grabaciones). Historial de peticiones por clave (30 días) en el panel."], ["1.1.0 · jun 2026", "Permisos por clave, sandbox vl_test_, caducidad e IPs; POST /calls asíncrono (202) con Idempotency-Key; estados estándar (status) manteniendo status_detail; GET /calls con paginación; cancelar; cuenta, límites, webhooks firmados y lista de exclusión; errores RFC 9457; horario legal por país; legal_basis (consent:true sigue aceptado)."], ["1.0.0", "GET /agents, POST /calls, GET /calls/{id}."]];

function Limits({ l, calls }) {
  const items = [["Peticiones/min por clave", l.requests_per_minute], ["Llamadas nuevas/min", l.calls_per_minute], ["Llamadas simultáneas", l.max_concurrent_calls], ["Llamadas por API al día", l.max_daily_calls], ["Llamadas por API (30 días)", calls]];
  return <div className="grid gap-3 sm:grid-cols-5" data-testid="dev-limits">{items.map(([k, v]) => <Panel key={k} className="p-4"><p className="text-xs text-slate-500">{k}</p><p className="mt-1 font-mono text-xl text-white">{v}</p></Panel>)}</div>;
}

export default function Developers() {
  const [d, setD] = useState(null);
  const load = () => api.get("/developer/overview").then((r) => setD(r.data));
  useEffect(() => { load(); }, []);
  return (
    <div className="fade-up space-y-6" data-testid="developers-page">
      <PageHeader eyebrow="API y desarrolladores" title="Integra VozLeads en tu CRM, ERP o app" desc="Lanza llamadas con tus agentes y recibe los resultados automáticamente.">
        <a href={`${BASE}/docs`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded-full bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white" data-testid="dev-docs-link"><BookOpen className="h-4 w-4" />Referencia OpenAPI<ExternalLink className="h-3.5 w-3.5" /></a>
      </PageHeader>
      {d && <Limits l={d.limits} calls={d.api_calls_30d} />}
      {d && <Keys d={d} reload={load} />}
      {d && <Webhooks d={d} reload={load} />}
      <Panel className="space-y-4" data-testid="dev-guide-panel">
        <h3 className="text-lg font-semibold text-white">Guía rápida</h3>
        <ol className="list-decimal space-y-1 pl-5 text-sm text-slate-300">
          <li>Crea una clave <b>Sandbox</b> y prueba: simula la llamada completa y los webhooks sin coste.</li>
          <li><span className="font-mono">GET /v1/agents</span> para obtener el <span className="font-mono">agent_id</span>.</li>
          <li><span className="font-mono">POST /v1/calls</span> con <span className="font-mono">legal_basis</span> y una <span className="font-mono">Idempotency-Key</span>. Responde <b>202</b> al instante.</li>
          <li>Recibe <span className="font-mono">call.completed</span> por webhook (o consulta <span className="font-mono">GET /v1/calls/{"{id}"}</span>).</li>
          <li>Cambia a una clave de Producción cuando esté listo.</li>
        </ol>
        <Tabs defaultValue="cURL"><TabsList className="flex-wrap">{Object.keys(EX).map((k) => <TabsTrigger key={k} value={k} data-testid={`dev-example-tab-${k}`}>{k}</TabsTrigger>)}</TabsList>
          {Object.entries(EX).map(([k, v]) => <TabsContent key={k} value={k}><Code testid={`dev-example-${k}`}>{v}</Code></TabsContent>)}</Tabs>
      </Panel>
      <div className="grid gap-6 lg:grid-cols-2">
        <Panel className="space-y-2" data-testid="dev-states-panel"><h3 className="font-semibold text-white">Estados de llamada</h3>{STATES.map(([k, v]) => <p key={k} className="text-sm text-slate-300"><span className="font-mono text-emerald-300">{k}</span> · {v}</p>)}</Panel>
        <Panel className="space-y-2" data-testid="dev-errors-panel"><h3 className="font-semibold text-white">Errores (application/problem+json)</h3>{ERRORS.map(([k, v]) => <p key={k} className="text-sm text-slate-300"><span className="font-mono text-amber-300">{k}</span> · {v}</p>)}</Panel>
      </div>
      <Panel className="space-y-2 text-sm text-slate-300" data-testid="dev-legal-panel">
        <h3 className="font-semibold text-white">Seguridad y cumplimiento</h3>
        <p>Las llamadas comerciales y contractuales solo salen en el horario permitido del país (por defecto L-V 09:00–21:00, S 10:00–14:00). Los recordatorios e informativas no se bloquean. Los números de tu lista de exclusión nunca se llaman.</p>
        <p>Debes declarar la base jurídica (<span className="font-mono">legal_basis</span>) y puedes adjuntar la evidencia del consentimiento. Declararla no acredita por sí sola que sea válida: la responsabilidad es de tu empresa. Revisa con tu asesor legal el RGPD, la LSSI y la normativa de llamadas comerciales de cada país.</p>
      </Panel>
      <Panel className="space-y-2" data-testid="dev-changelog-panel"><h3 className="font-semibold text-white">Changelog</h3>{CHANGELOG.map(([v, t]) => <p key={v} className="text-sm text-slate-300"><b className="text-white">{v}</b> · {t}</p>)}</Panel>
    </div>
  );
}
