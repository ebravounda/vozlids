import { useEffect, useState } from "react";
import { toast } from "sonner";
import { BellRing, CalendarDays, Loader2, Save, SlidersHorizontal } from "lucide-react";
import { GoogleCard, RemindersCard } from "@/components/calendar/Connections";
import { Gate } from "@/components/PlanGate";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageHeader, Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";
import { DAYS } from "@/lib/constants";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AgendaCalendar } from "@/components/calendar/AgendaCalendar";

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
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    api.get("/availability").then((r) => setAv(r.data));
    const g = new URLSearchParams(window.location.search).get("google");
    if (g === "ok") api.get("/google/status").then((r) => r.data.connected && toast.success(`Google Calendar conectado con ${r.data.email}`));
    if (g === "error") toast.error("No se pudo conectar Google Calendar. Inténtalo de nuevo.");
    if (g) window.history.replaceState(null, "", "/app/agenda");
  }, []);

  const save = async () => {
    setSaving(true);
    try { await api.put("/availability", av); toast.success("Horario guardado"); }
    catch (e) { toast.error(errMsg(e)); }
    finally { setSaving(false); }
  };

  return (
    <div className="fade-up" data-testid="agenda-page">
      <PageHeader eyebrow="Agenda" title="Agenda y citas" desc="Todas las citas que reserva tu agente IA y las que creas tú. El agente solo ofrece huecos libres dentro de tu horario y nunca reserva dos citas a la misma hora." />
      <Tabs defaultValue={new URLSearchParams(window.location.search).get("google") ? "connect" : "calendar"}>
        <TabsList className="mb-4 max-w-full justify-start overflow-x-auto bg-slate-100">
          <TabsTrigger value="calendar" data-testid="agenda-tab-calendar"><CalendarDays className="mr-1.5 h-4 w-4" />Calendario</TabsTrigger>
          <TabsTrigger value="hours" data-testid="agenda-tab-hours"><SlidersHorizontal className="mr-1.5 h-4 w-4" />Horario de citas</TabsTrigger>
          <TabsTrigger value="connect" data-testid="agenda-tab-connect"><BellRing className="mr-1.5 h-4 w-4" />Recordatorios y Google</TabsTrigger>
        </TabsList>
        <TabsContent value="calendar">{av && <AgendaCalendar av={av} />}</TabsContent>
        <TabsContent value="connect"><Gate f="agenda_pro"><div className="grid gap-6 lg:grid-cols-2"><RemindersCard /><GoogleCard /></div></Gate></TabsContent>
        <TabsContent value="hours"><div className="max-w-2xl">{av && <Hours av={av} setAv={setAv} onSave={save} saving={saving} />}</div></TabsContent>
      </Tabs>
    </div>
  );
}
