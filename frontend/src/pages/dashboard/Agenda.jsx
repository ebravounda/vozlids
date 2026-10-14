import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Save, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageHeader, Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";
import { DAYS, fmtSlot } from "@/lib/constants";

const timeCls = "rounded-lg border border-slate-700 bg-slate-950/60 px-2 py-1.5 font-mono text-sm text-white disabled:opacity-40 [color-scheme:dark]";

function Hours({ av, setAv, onSave, saving }) {
  const setDay = (i, patch) => setAv({ ...av, days: av.days.map((d, j) => (j === i ? { ...d, ...patch } : d)) });
  return (
    <Panel className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-xl font-semibold text-white">Horario de citas</h3>
        <Select value={String(av.slot_minutes)} onValueChange={(v) => setAv({ ...av, slot_minutes: Number(v) })}>
          <SelectTrigger className="w-40 bg-slate-950/60" data-testid="agenda-slot-select"><SelectValue /></SelectTrigger>
          <SelectContent>{[15, 20, 30, 45, 60, 90].map((m) => <SelectItem key={m} value={String(m)}>Citas de {m} min</SelectItem>)}</SelectContent>
        </Select>
      </div>
      {av.days.map((d, i) => (
        <div key={i} className="flex items-center gap-3 border-b border-slate-800/70 pb-3" data-testid={`agenda-day-${i}`}>
          <Switch checked={d.enabled} onCheckedChange={(v) => setDay(i, { enabled: v })} data-testid={`agenda-day-switch-${i}`} />
          <span className={`w-24 text-sm ${d.enabled ? "text-white" : "text-slate-500"}`}>{DAYS[i]}</span>
          <input type="time" value={d.start} disabled={!d.enabled} onChange={(e) => setDay(i, { start: e.target.value })} className={timeCls} data-testid={`agenda-day-start-${i}`} />
          <span className="text-slate-500">–</span>
          <input type="time" value={d.end} disabled={!d.enabled} onChange={(e) => setDay(i, { end: e.target.value })} className={timeCls} data-testid={`agenda-day-end-${i}`} />
        </div>
      ))}
      <Button onClick={onSave} disabled={saving} className="rounded-full font-semibold" data-testid="agenda-save-hours-button">
        {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />} Guardar horario
      </Button>
    </Panel>
  );
}

export default function Agenda() {
  const [av, setAv] = useState(null);
  const [appts, setAppts] = useState([]);
  const [saving, setSaving] = useState(false);

  const loadAppts = () => api.get("/appointments").then((r) => setAppts(r.data)).catch(() => {});
  useEffect(() => { api.get("/availability").then((r) => setAv(r.data)); loadAppts(); }, []);

  const save = async () => {
    setSaving(true);
    try { await api.put("/availability", av); toast.success("Horario guardado"); }
    catch (e) { toast.error(errMsg(e)); }
    finally { setSaving(false); }
  };

  const cancel = async (id) => {
    if (!window.confirm("¿Cancelar esta cita? El hueco quedará libre.")) return;
    await api.delete(`/appointments/${id}`);
    toast.success("Cita cancelada");
    loadAppts();
  };

  return (
    <div className="fade-up">
      <PageHeader eyebrow="Agenda" title="Agenda y citas" desc="El agente solo ofrece huecos dentro de este horario (hora de Madrid) y nunca reserva dos citas a la misma hora." />
      <div className="grid gap-6 lg:grid-cols-2">
        {av && <Hours av={av} setAv={setAv} onSave={save} saving={saving} />}
        <Panel>
          <h3 className="mb-4 text-xl font-semibold text-white">Próximas citas</h3>
          <div className="space-y-3" data-testid="appointments-list">
            {appts.map((a) => (
              <div key={a.id} className="flex items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-950/40 p-4" data-testid={`appointment-${a.id}`}>
                <div>
                  <p className="text-sm font-semibold capitalize text-teal-200">{fmtSlot(a.start)}</p>
                  <p className="text-sm text-white">{a.lead_name} <span className="font-mono text-xs text-slate-400">{a.lead_phone}</span></p>
                  {a.notes && <p className="text-xs text-slate-500">{a.notes}{a.is_sample ? " · ejemplo" : ""}</p>}
                </div>
                <button onClick={() => cancel(a.id)} className="rounded-lg p-2 text-slate-500 hover:bg-rose-500/10 hover:text-rose-300" title="Cancelar" data-testid={`appointment-cancel-${a.id}`}><X className="h-4 w-4" /></button>
              </div>
            ))}
            {!appts.length && <p className="text-sm text-slate-500" data-testid="appointments-empty">No hay citas próximas.</p>}
          </div>
        </Panel>
      </div>
    </div>
  );
}
