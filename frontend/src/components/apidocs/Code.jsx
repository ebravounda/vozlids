import { useState } from "react";
import { Check, Copy } from "lucide-react";

export const BASE = "https://vozleads.com/api/v1";

export function Code({ tabs, testid }) {
  const names = Object.keys(tabs);
  const [tab, setTab] = useState(names[0]);
  const [copied, setCopied] = useState(false);
  const copy = () => { navigator.clipboard?.writeText(tabs[tab]); setCopied(true); setTimeout(() => setCopied(false), 1500); };
  return (
    <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-950" data-testid={testid}>
      <div className="flex items-center justify-between border-b border-slate-800 px-3">
        <div className="flex">{names.map((n) => <button key={n} onClick={() => setTab(n)} className={`px-3 py-2.5 text-xs font-semibold transition-colors ${tab === n ? "border-b-2 border-blue-400 text-white" : "text-slate-400 hover:text-slate-200"}`} data-testid={`${testid}-tab-${n.toLowerCase()}`}>{n}</button>)}</div>
        <button onClick={copy} className="flex items-center gap-1 text-xs text-slate-400 hover:text-white" data-testid={`${testid}-copy`}>{copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}{copied ? "Copiado" : "Copiar"}</button>
      </div>
      <pre className="overflow-x-auto p-4 font-mono text-[12.5px] leading-relaxed text-slate-200">{tabs[tab]}</pre>
    </div>
  );
}

export const QUICKSTART = {
  cURL: `curl -X POST ${BASE}/calls \\
  -H "X-API-Key: vl_test_TU_CLAVE" \\
  -H "Content-Type: application/json" \\
  -H "Idempotency-Key: pedido-1234" \\
  -d '{
    "agent_id": "AGENTE_ID",
    "name": "Laura Pérez",
    "phone": "+34612345678",
    "type": "recordatorio",
    "legal_basis": "contract",
    "context": { "cita": "jueves 19:00" },
    "metadata": { "crm_id": "1234" }
  }'`,
  Python: `import requests

r = requests.post(
    "${BASE}/calls",
    headers={"X-API-Key": "vl_test_TU_CLAVE", "Idempotency-Key": "pedido-1234"},
    json={
        "agent_id": "AGENTE_ID",
        "name": "Laura Pérez",
        "phone": "+34612345678",
        "type": "recordatorio",
        "legal_basis": "contract",
        "context": {"cita": "jueves 19:00"},
    },
)
print(r.status_code, r.json()["id"])`,
  "Node.js": `const r = await fetch("${BASE}/calls", {
  method: "POST",
  headers: {
    "X-API-Key": "vl_test_TU_CLAVE",
    "Content-Type": "application/json",
    "Idempotency-Key": "pedido-1234",
  },
  body: JSON.stringify({
    agent_id: "AGENTE_ID",
    name: "Laura Pérez",
    phone: "+34612345678",
    type: "recordatorio",
    legal_basis: "contract",
    context: { cita: "jueves 19:00" },
  }),
});
console.log(r.status, (await r.json()).id);`,
};

export const WEBHOOK_VERIFY = {
  Python: `import hmac, hashlib, time

def verificar(cabecera: str, cuerpo: bytes, secreto: str) -> bool:
    partes = dict(p.split("=", 1) for p in cabecera.split(","))
    if abs(time.time() - int(partes["t"])) > 300:
        return False  # evita reenvíos antiguos
    firmado = f'{partes["t"]}.'.encode() + cuerpo
    esperado = hmac.new(secreto.encode(), firmado, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, partes["v1"])`,
  "Node.js": `import crypto from "node:crypto";

export function verificar(cabecera, cuerpo, secreto) {
  const p = Object.fromEntries(cabecera.split(",").map((x) => x.split("=")));
  if (Math.abs(Date.now() / 1000 - Number(p.t)) > 300) return false;
  const esperado = crypto.createHmac("sha256", secreto)
    .update(\`\${p.t}.\${cuerpo}\`).digest("hex");
  return crypto.timingSafeEqual(Buffer.from(esperado), Buffer.from(p.v1));
}`,
};

export const WEBHOOK_PAYLOAD = {
  JSON: `{
  "id": "evt_8f2c…",
  "type": "call.completed",
  "schema_version": "2026-06-01",
  "created_at": "2026-07-01T10:31:12+00:00",
  "data": {
    "id": "6650f…",
    "object": "call",
    "status": "completed",
    "direction": "outbound",
    "to": "+34612345678",
    "duration_seconds": 94,
    "metadata": { "crm_id": "1234" },
    "result": {
      "summary": "Confirma la cita del jueves a las 19:00.",
      "outcome": "cita_agendada",
      "appointment_booked": true,
      "interest_score": 82,
      "billed_minutes": 1.57
    },
    "transcript": [ … ]
  }
}`,
};
