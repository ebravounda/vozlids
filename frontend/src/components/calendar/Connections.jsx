import { useEffect, useState } from "react";
import { toast } from "sonner";
import { BellRing, CalendarCheck2, Loader2, Mail, PhoneCall, Unplug } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";
import { fmtDate } from "@/lib/constants";

export function GoogleCard() {
  const [s, setS] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = () => api.get("/google/status").then((r) => setS(r.data));
  useEffect(() => { load(); }, []);
  const connect = async () => { setBusy(true); try { const r = await api.post("/google/connect"); window.location.href = r.data.url; } catch (e) { toast.error(errMsg(e)); setBusy(false); } };
  const disconnect = async () => { if (!window.confirm("¿Desconectar Google Calendar? Las citas dejarán de copiarse.")) return; await api.post("/google/disconnect"); toast.success("Google Calendar desconectado"); load(); };
  if (!s) return null;
  return (
    <Panel className="space-y-4" data-testid="google-calendar-card">
      <div className="flex items-center gap-2"><CalendarCheck2 className="h-5 w-5 text-blue-600" /><h3 className="text-lg font-semibold text-slate-900">Google Calendar</h3></div>
      <p className="text-sm text-slate-500">Cada cita de VozLeads aparece en tu Google Calendar, y las horas que ya tengas ocupadas en Google dejan de ofrecerse a tus clientes.</p>
      {s.connected ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800" data-testid="google-connected">
          <span>Conectado con <b>{s.email}</b>{s.connected_at ? ` · desde ${fmtDate(s.connected_at)}` : ""}</span>
          <Button size="sm" variant="ghost" onClick={disconnect} className="text-slate-600" data-testid="google-disconnect-button"><Unplug className="mr-1 h-4 w-4" />Desconectar</Button>
        </div>
      ) : (
        <Button onClick={connect} disabled={busy || !s.available} className="rounded-full bg-blue-600 text-white hover:bg-blue-700" data-testid="google-connect-button">{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Conectar Google Calendar</Button>
      )}
      {!s.available && <p className="text-xs text-amber-700" data-testid="google-unavailable">Disponible muy pronto: estamos activando la conexión con Google.</p>}
      {s.error && <p className="text-xs text-rose-700" data-testid="google-error">{s.error}</p>}
    </Panel>
  );
}

const HOURS = [[24, "24 h antes"], [3, "3 h antes"], [1, "1 h antes"]];

export function RemindersCard() {
  const [f, setF] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.get("/reminders").then((r) => setF(r.data)); }, []);
  const save = async () => {
    setBusy(true);
    try { const { sent_total, ...body } = f; await api.put("/reminders", body); toast.success("Recordatorios guardados"); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  if (!f) return null;
  const t = "rounded-lg border border-slate-200 bg-white px-2 py-1.5 font-mono text-sm text-slate-900";
  return (
    <Panel className="space-y-5" data-testid="reminders-card">
      <div className="flex items-center gap-2"><BellRing className="h-5 w-5 text-blue-600" /><h3 className="text-lg font-semibold text-slate-900">Recordatorios de citas</h3></div>
      <p className="text-sm text-slate-500">Reduce las ausencias: avisamos a tu cliente antes de cada cita.</p>
      <label className="flex items-start gap-3 rounded-xl border border-slate-200 p-4"><Switch checked={f.email} onCheckedChange={(v) => setF({ ...f, email: v })} data-testid="reminder-email-switch" />
        <span><span className="flex items-center gap-1.5 font-semibold text-slate-900"><Mail className="h-4 w-4" />Email</span><span className="text-sm text-slate-500">Sin coste. Con botón para confirmar o anular; si anula, el hueco queda libre y te avisamos.</span></span></label>
      <label className="flex items-start gap-3 rounded-xl border border-slate-200 p-4"><Switch checked={f.call} onCheckedChange={(v) => setF({ ...f, call: v })} data-testid="reminder-call-switch" />
        <span><span className="flex items-center gap-1.5 font-semibold text-slate-900"><PhoneCall className="h-4 w-4" />Llamada del agente IA</span><span className="text-sm text-slate-500">Tu agente llama y pide confirmación. <b>Consume minutos de tu plan</b> (normalmente menos de 1 minuto por cita).</span></span></label>
      <div className="space-y-2"><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cuándo</p>
        <div className="flex flex-wrap gap-2">{HOURS.map(([h, l]) => <button key={h} onClick={() => setF({ ...f, hours_before: h })} className={`rounded-full border px-4 py-1.5 text-sm ${f.hours_before === h ? "border-blue-600 bg-blue-600 font-semibold text-white" : "border-slate-200 text-slate-600"}`} data-testid={`reminder-hours-${h}`}>{l}</button>)}</div></div>
      {f.call && <div className="flex flex-wrap items-center gap-2 text-sm text-slate-600" data-testid="reminder-call-window">Llamar solo entre
        <input type="time" value={f.call_from} onChange={(e) => setF({ ...f, call_from: e.target.value })} className={t} data-testid="reminder-call-from" /> y
        <input type="time" value={f.call_to} onChange={(e) => setF({ ...f, call_to: e.target.value })} className={t} data-testid="reminder-call-to" /></div>}
      <div className="flex items-center justify-between gap-3"><span className="text-xs text-slate-500" data-testid="reminder-sent-total">{f.sent_total} recordatorios enviados</span>
        <Button onClick={save} disabled={busy} className="rounded-full bg-blue-600 text-white hover:bg-blue-700" data-testid="reminder-save-button">{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Guardar</Button></div>
    </Panel>
  );
}
