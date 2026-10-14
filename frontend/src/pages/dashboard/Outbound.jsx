import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, PhoneOutgoing, Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageHeader, Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";
import { COUNTRIES } from "@/lib/constants";

const TYPES = { seguimiento: "Seguimiento", cobro: "Cobro", info: "Información", recordatorio: "Recordatorio", encuesta: "Encuesta" };
const STATUS_CLS = { pendiente: "text-cyan-300", realizada: "text-emerald-300", cancelada: "text-slate-500", fallida: "text-red-300", no_llamar: "text-rose-300", en_proceso: "text-amber-300" };

function TemplateEditor({ onSaved }) {
  const [f, setF] = useState({ name: "", call_type: "seguimiento", purpose: "", greeting: "Hola {nombre}, te llamo de parte de nuestro equipo. Soy un asistente virtual y la llamada se graba. ¿Tienes un minuto?" });
  const save = async () => {
    try { await api.post("/templates", f); toast.success("Plantilla creada"); setF({ ...f, name: "", purpose: "" }); onSaved(); }
    catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div className="space-y-3 border-t border-slate-800 pt-4" data-testid="template-editor">
      <p className="text-sm font-semibold text-white">Nueva plantilla</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Input placeholder="Nombre" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className="bg-slate-950/60" data-testid="template-name-input" />
        <Select value={f.call_type} onValueChange={(v) => setF({ ...f, call_type: v })}>
          <SelectTrigger className="bg-slate-950/60" data-testid="template-type-select"><SelectValue /></SelectTrigger>
          <SelectContent>{Object.entries(TYPES).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent>
        </Select>
      </div>
      <Textarea rows={3} placeholder="Qué debe conseguir el agente en esta llamada" value={f.purpose} onChange={(e) => setF({ ...f, purpose: e.target.value })} className="bg-slate-950/60" data-testid="template-purpose-input" />
      <Textarea rows={2} value={f.greeting} onChange={(e) => setF({ ...f, greeting: e.target.value })} className="bg-slate-950/60" data-testid="template-greeting-input" />
      <Button onClick={save} disabled={!f.name || !f.purpose} className="rounded-full" data-testid="template-save-button"><Plus className="mr-2 h-4 w-4" /> Guardar plantilla</Button>
    </div>
  );
}

function Scheduler({ agents, templates, onDone }) {
  const [f, setF] = useState({ agent_id: "", template_id: "", contacts: "", when: "now", run_at: "" });
  const [busy, setBusy] = useState(false);
  const agent = agents.find((a) => a.id === f.agent_id);
  const submit = async () => {
    const contacts = f.contacts.split("\n").map((l) => l.split(/[,;\t]/).map((x) => x.trim())).filter((p) => p[0] && p[1]).map(([name, phone, email]) => ({ name, phone, email: email || "" }));
    if (!contacts.length) return toast.error("Añade al menos un contacto: Nombre, teléfono");
    setBusy(true);
    try {
      const { data } = await api.post("/scheduled-calls", { agent_id: f.agent_id, template_id: f.template_id, contacts, run_at: f.when === "later" ? f.run_at : null });
      toast.success(f.when === "later" ? `${data.count} llamadas programadas` : `${data.count} llamadas en marcha`);
      setF({ ...f, contacts: "" }); onDone();
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <Panel className="space-y-4" data-testid="scheduler-panel">
      <h3 className="text-lg font-semibold text-white">Lanzar o programar llamadas</h3>
      <div className="grid gap-3 sm:grid-cols-2">
        <Select value={f.agent_id} onValueChange={(v) => setF({ ...f, agent_id: v })}>
          <SelectTrigger className="bg-slate-950/60" data-testid="schedule-agent-select"><SelectValue placeholder="Agente" /></SelectTrigger>
          <SelectContent>{agents.map((a) => <SelectItem key={a.id} value={a.id}>{a.name} · {COUNTRIES[a.country || "ES"].name}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={f.template_id} onValueChange={(v) => setF({ ...f, template_id: v })}>
          <SelectTrigger className="bg-slate-950/60" data-testid="schedule-template-select"><SelectValue placeholder="Plantilla" /></SelectTrigger>
          <SelectContent>{templates.map((t) => <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>)}</SelectContent>
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label>Clientes (uno por línea: Nombre, teléfono, email opcional)</Label>
        <Textarea rows={5} value={f.contacts} onChange={(e) => setF({ ...f, contacts: e.target.value })} placeholder={`Laura Pérez, ${agent ? COUNTRIES[agent.country || "ES"].example : "+34 600 000 000"}`} className="bg-slate-950/60 font-mono text-sm" data-testid="schedule-contacts-input" />
      </div>
      <div className="flex flex-wrap items-center gap-3">
        {[["now", "Llamar ahora"], ["later", "Programar"]].map(([k, l]) => (
          <button key={k} onClick={() => setF({ ...f, when: k })} data-testid={`schedule-when-${k}`} className={`rounded-full border px-4 py-1.5 text-sm ${f.when === k ? "border-emerald-500 bg-emerald-500/10 text-emerald-200" : "border-slate-700 text-slate-300"}`}>{l}</button>
        ))}
        {f.when === "later" && <input type="datetime-local" value={f.run_at} onChange={(e) => setF({ ...f, run_at: e.target.value })} className="rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-1.5 text-sm text-white [color-scheme:dark]" data-testid="schedule-datetime-input" />}
        {f.when === "later" && agent && <span className="text-xs text-slate-500">Hora de {COUNTRIES[agent.country || "ES"].city} · salen en tandas cada 15 min</span>}
      </div>
      <Button onClick={submit} disabled={busy || !f.agent_id || !f.template_id || (f.when === "later" && !f.run_at)} className="rounded-full font-semibold" data-testid="schedule-submit-button">
        {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <PhoneOutgoing className="mr-2 h-4 w-4" />} {f.when === "later" ? "Programar llamadas" : "Llamar ahora"}
      </Button>
      <p className="text-xs text-slate-500">Llama solo a clientes que te han autorizado a contactarles. Se respeta tu lista de no llamar.</p>
    </Panel>
  );
}

export default function Outbound() {
  const [agents, setAgents] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [jobs, setJobs] = useState([]);
  const loadT = () => api.get("/templates").then((r) => setTemplates(r.data));
  const loadJ = () => api.get("/scheduled-calls").then((r) => setJobs(r.data));
  useEffect(() => { api.get("/agents").then((r) => setAgents(r.data)); loadT(); loadJ(); }, []);
  const cancel = async (id) => { await api.delete(`/scheduled-calls/${id}`); loadJ(); };
  const delTpl = async (id) => { await api.delete(`/templates/${id}`); loadT(); };

  return (
    <div className="fade-up">
      <PageHeader eyebrow="Llamadas salientes" title="Seguimiento, cobros y recordatorios" desc="Elige una plantilla, añade el nombre y teléfono de tus clientes y llama ahora o a la fecha y hora que quieras." />
      <div className="mb-6 grid gap-6 lg:grid-cols-2">
        <Scheduler agents={agents} templates={templates} onDone={loadJ} />
        <Panel className="space-y-3" data-testid="templates-panel">
          <h3 className="text-lg font-semibold text-white">Plantillas</h3>
          {templates.map((t) => (
            <div key={t.id} className="flex items-start justify-between gap-3 rounded-xl border border-slate-800 p-3" data-testid={`template-${t.id}`}>
              <div><p className="text-sm font-semibold text-white">{t.name} <span className="text-xs font-normal text-emerald-400">{TYPES[t.call_type]}</span></p><p className="line-clamp-2 text-xs text-slate-400">{t.purpose}</p></div>
              <button onClick={() => delTpl(t.id)} className="text-slate-500 hover:text-rose-300" data-testid={`template-delete-${t.id}`}><X className="h-4 w-4" /></button>
            </div>
          ))}
          <TemplateEditor onSaved={loadT} />
        </Panel>
      </div>
      <Panel className="overflow-x-auto p-0">
        <table className="w-full min-w-[700px] text-sm" data-testid="scheduled-table">
          <thead className="text-left text-xs uppercase tracking-wider text-slate-500"><tr><th className="p-4">Cliente</th><th className="p-4">Plantilla</th><th className="p-4">Cuándo</th><th className="p-4">Estado</th><th className="p-4"></th></tr></thead>
          <tbody>
            {jobs.map((j) => (
              <tr key={j.id} className="border-t border-slate-800">
                <td className="p-4"><p className="text-white">{j.name}</p><p className="font-mono text-xs text-slate-500">{j.phone}</p></td>
                <td className="p-4 text-slate-300">{j.template_name}</td>
                <td className="p-4 text-xs text-slate-400">{j.run_at_local ? `${j.run_at_local.replace("T", " ")} (${COUNTRIES[j.country].city})` : "Inmediata"}</td>
                <td className={`p-4 text-xs font-semibold ${STATUS_CLS[j.status] || ""}`}>{j.status}{j.error ? ` · ${j.error}` : ""}</td>
                <td className="p-4">{j.status === "pendiente" && <button onClick={() => cancel(j.id)} className="text-xs text-rose-300" data-testid={`scheduled-cancel-${j.id}`}>Cancelar</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!jobs.length && <p className="p-8 text-center text-sm text-slate-500">Aún no hay llamadas salientes.</p>}
      </Panel>
    </div>
  );
}
