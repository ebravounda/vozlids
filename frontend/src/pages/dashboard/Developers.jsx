import { useEffect, useState } from "react";
import { toast } from "sonner";
import { KeyRound, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader, Panel } from "@/components/Common";
import { API, api, errMsg } from "@/lib/api";

const Code = ({ children }) => <pre className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950 p-4 font-mono text-xs leading-relaxed text-emerald-200">{children}</pre>;

const DOCS = [
  ["Autenticación", "Envía tu clave en la cabecera X-API-Key en cada petición."],
  ["GET /v1/agents", "Lista tus agentes (id, nombre, país)."],
  ["POST /v1/calls", "Lanza o programa una llamada. type: cobro | info | recordatorio | encuesta | seguimiento. consent: true es obligatorio. context: datos libres que el agente usará (importe, vencimiento, producto, fecha del evento…). scheduled_at opcional (YYYY-MM-DDTHH:MM, hora local del país del agente)."],
  ["GET /v1/calls/{call_id}", "Estado, resumen, puntuación de interés, respuestas y transcripción de la llamada."],
  ["Errores", "401 clave no válida · 400 sin consentimiento · 402 minutos del plan agotados · 422 datos o teléfono no válidos."],
];

export default function Developers() {
  const [keys, setKeys] = useState([]);
  const [name, setName] = useState("");
  const [fresh, setFresh] = useState(null);
  const load = () => api.get("/api-keys").then((r) => setKeys(r.data));
  useEffect(() => { load(); }, []);
  const create = async () => {
    try { const { data } = await api.post("/api-keys", { name }); setFresh(data.key); setName(""); load(); }
    catch (e) { toast.error(errMsg(e)); }
  };
  const revoke = async (id) => { if (window.confirm("¿Revocar esta clave? Las integraciones que la usen dejarán de funcionar.")) { await api.delete(`/api-keys/${id}`); load(); } };
  const base = `${API}/v1`;

  return (
    <div className="fade-up">
      <PageHeader eyebrow="Desarrolladores" title="API de VozLeads" desc="Integra tu CRM, ERP o plataforma de cobros para lanzar llamadas de cobro, información, recordatorios y encuestas." />
      <div className="grid gap-6 lg:grid-cols-5">
        <Panel className="space-y-4 lg:col-span-2" data-testid="api-keys-panel">
          <h3 className="text-lg font-semibold text-white">Claves de API</h3>
          <div className="flex gap-2">
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Nombre (ej. CRM)" className="bg-slate-950/60" data-testid="api-key-name-input" />
            <Button onClick={create} disabled={!name} className="rounded-full" data-testid="api-key-create-button"><KeyRound className="mr-2 h-4 w-4" /> Crear</Button>
          </div>
          {fresh && <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-100" data-testid="api-key-fresh">Copia tu clave ahora, no se volverá a mostrar:<p className="mt-2 break-all font-mono text-sm text-white">{fresh}</p></div>}
          {keys.map((k) => (
            <div key={k.id} className="flex items-center justify-between rounded-lg border border-slate-800 px-3 py-2" data-testid={`api-key-${k.id}`}>
              <div><p className="text-sm text-white">{k.name}</p><p className="font-mono text-xs text-slate-500">{k.prefix}…</p></div>
              <button onClick={() => revoke(k.id)} className="text-slate-500 hover:text-rose-300" data-testid={`api-key-revoke-${k.id}`}><Trash2 className="h-4 w-4" /></button>
            </div>
          ))}
        </Panel>
        <Panel className="space-y-5 lg:col-span-3" data-testid="api-docs">
          <h3 className="text-lg font-semibold text-white">Referencia</h3>
          <p className="text-sm text-slate-400">URL base: <span className="font-mono text-emerald-300">{base}</span></p>
          <dl className="space-y-3">{DOCS.map(([t, d]) => <div key={t}><dt className="font-mono text-sm text-white">{t}</dt><dd className="text-sm text-slate-400">{d}</dd></div>)}</dl>
          <p className="text-sm font-semibold text-white">Ejemplo: llamada de cobro</p>
          <Code>{`curl -X POST ${base}/calls \\
  -H "X-API-Key: vl_live_..." \\
  -H "Content-Type: application/json" \\
  -d '{
    "agent_id": "AGENT_ID",
    "name": "Laura Pérez",
    "phone": "+34600000000",
    "type": "cobro",
    "consent": true,
    "context": {"concepto": "Factura 1043", "importe": "120 €", "vencimiento": "15/06"},
    "scheduled_at": "2026-06-20T10:30"
  }'`}</Code>
          <p className="text-sm font-semibold text-white">Respuesta</p>
          <Code>{`{"call_id": "66a1…", "status": "llamando", "error": ""}
// programada: {"scheduled_id": "66a2…", "status": "pendiente"}`}</Code>
        </Panel>
      </div>
    </div>
  );
}
