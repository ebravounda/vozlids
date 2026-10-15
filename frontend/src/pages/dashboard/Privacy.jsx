import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Clock, Search, ShieldCheck } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader, Panel } from "@/components/Common";
import { SubjectActions } from "@/components/PrivacyParts";
import { api, errMsg } from "@/lib/api";
import { fmtDate } from "@/lib/constants";

const label = (d) => (d === 0 ? "Nunca" : d === 365 ? "1 año" : `${d} días`);

function Retention({ s, reload }) {
  const save = (days) => api.put("/privacy/retention", { days }).then(() => { toast.success(days ? `Se borrarán a los ${label(days)}` : "Borrado automático desactivado"); reload(); }).catch((e) => toast.error(errMsg(e)));
  return (
    <Panel className="space-y-4" data-testid="privacy-retention-panel">
      <div className="flex items-center gap-2"><Clock className="h-5 w-5 text-blue-400" /><h3 className="text-lg font-semibold text-white">Borrado automático de transcripciones y grabaciones</h3></div>
      <p className="text-sm text-slate-400">Pasado el plazo se eliminan la transcripción y el audio de cada llamada. El lead, su estado, el resumen y las estadísticas se conservan.</p>
      <div className="flex flex-wrap gap-2">{s.choices.map((d) => (
        <button key={d} onClick={() => save(d)} className={`rounded-full border px-4 py-1.5 text-sm transition-colors ${s.retention_days === d ? "border-blue-500 bg-blue-500/15 text-blue-200" : "border-slate-700 text-slate-400 hover:text-white"}`} data-testid={`privacy-retention-${d}`}>{label(d)}</button>
      ))}</div>
      <p className="text-xs text-slate-500" data-testid="privacy-purged-count">{s.purged_calls} llamadas ya depuradas · se revisa cada hora</p>
    </Panel>
  );
}

function Subject({ reload }) {
  const [f, setF] = useState({ phone: "", email: "" });
  const ready = f.phone.trim() || f.email.trim();
  return (
    <Panel className="space-y-4" data-testid="privacy-subject-panel">
      <div className="flex items-center gap-2"><Search className="h-5 w-5 text-blue-400" /><h3 className="text-lg font-semibold text-white">Solicitud de un contacto (acceso o supresión)</h3></div>
      <p className="text-sm text-slate-400">Busca por teléfono o email. Exportar descarga un JSON con todo lo que guardamos; borrar lo elimina definitivamente.</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5"><Label className="text-xs">Teléfono</Label><Input value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} placeholder="+34 612 345 678" className="bg-slate-950/60 font-mono" data-testid="privacy-phone-input" /></div>
        <div className="space-y-1.5"><Label className="text-xs">Email</Label><Input value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} placeholder="contacto@ejemplo.com" className="bg-slate-950/60" data-testid="privacy-email-input" /></div>
      </div>
      {ready ? <SubjectActions subject={f} onErased={() => { setF({ phone: "", email: "" }); reload(); }} /> : <p className="text-xs text-slate-500">Indica al menos un dato.</p>}
    </Panel>
  );
}

function History({ rows }) {
  return (
    <Panel className="space-y-2" data-testid="privacy-history-panel">
      <h3 className="font-semibold text-white">Registro de solicitudes</h3>
      <p className="text-xs text-slate-500">Sirve como prueba de cumplimiento; no guarda el teléfono ni el email.</p>
      {!rows.length && <p className="text-sm text-slate-500">Todavía no hay solicitudes.</p>}
      {rows.map((r, i) => (
        <p key={i} className="flex flex-wrap gap-2 text-sm text-slate-300" data-testid={`privacy-history-row-${i}`}>
          <span className={r.action === "erase" ? "text-rose-300" : "text-emerald-300"}>{r.action === "erase" ? "Borrado" : "Exportación"}</span>
          <span className="font-mono text-xs text-slate-500">ref {r.subject_ref}</span>· {r.counts.calls} llamadas · {fmtDate(r.created_at)}
        </p>
      ))}
    </Panel>
  );
}

export default function Privacy() {
  const [s, setS] = useState(null);
  const load = () => api.get("/privacy/settings").then((r) => setS(r.data));
  useEffect(() => { load(); }, []);
  return (
    <div className="fade-up space-y-6" data-testid="privacy-page">
      <PageHeader eyebrow="Privacidad (RGPD)" title="Datos de tus contactos bajo control" desc="Atiende solicitudes de acceso y supresión, y decide cuánto tiempo guardar las conversaciones." />
      {s && <Retention s={s} reload={load} />}
      <Subject reload={load} />
      {s && <History rows={s.history} />}
      <Panel className="flex gap-3 text-sm text-slate-400" data-testid="privacy-api-note"><ShieldCheck className="h-5 w-5 shrink-0 text-emerald-400" />También disponible por API con el permiso <span className="font-mono text-slate-200">privacy:manage</span>: POST /v1/privacy/export, POST /v1/privacy/erase y GET/PUT /v1/account/retention.</Panel>
    </div>
  );
}
