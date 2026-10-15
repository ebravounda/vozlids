import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Bot, CalendarClock, Clock, ExternalLink, Loader2, Phone, Trash2, UserRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, errMsg } from "@/lib/api";
import { endHm } from "@/lib/cal";
import { fmtSlot } from "@/lib/constants";

const field = "border-slate-200 bg-white text-slate-900";

function Detail({ a, slot, onSaved, onCancelled, onLead }) {
  const [f, setF] = useState({ start: a.start, notes: a.notes || "", duration_minutes: a.duration_minutes || slot });
  const [busy, setBusy] = useState("");
  const [ask, setAsk] = useState(false);
  const run = async (k, fn) => { setBusy(k); try { await fn(); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(""); } };
  const save = () => run("save", async () => { await api.patch(`/appointments/${a.id}`, { ...f, duration_minutes: Number(f.duration_minutes) }); toast.success("Cita actualizada"); onSaved(); });
  const cancel = () => run("cancel", async () => { await api.delete(`/appointments/${a.id}`); toast.success("Cita cancelada · el hueco queda libre"); onCancelled(); });
  const Src = a.source === "manual" ? UserRound : Bot;
  return (
    <div className="space-y-4">
      <div className="space-y-2 rounded-xl bg-slate-50 p-4 text-sm text-slate-700">
        <p className="flex items-center gap-2 font-semibold capitalize text-slate-900"><CalendarClock className="h-4 w-4 text-blue-600" />{fmtSlot(a.start)} – {endHm(a, slot)}</p>
        {a.lead_phone && <p className="flex items-center gap-2"><Phone className="h-4 w-4 text-slate-400" /><a href={`tel:${a.lead_phone}`} className="font-mono hover:text-blue-600" data-testid="appt-phone">{a.lead_phone}</a></p>}
        <p className="flex items-center gap-2 text-slate-500"><Src className="h-4 w-4" />{a.source === "manual" ? "Creada a mano" : "Reservada por el agente IA"}{a.is_sample ? " · ejemplo" : ""}</p>
        {a.lead_id && <button onClick={() => onLead(a.lead_id)} className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:underline" data-testid="appt-open-lead">Ver llamada y transcripción <ExternalLink className="h-3 w-3" /></button>}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5"><Label className="text-xs text-slate-600">Fecha y hora</Label><Input type="datetime-local" value={f.start} onChange={(e) => setF({ ...f, start: e.target.value })} className={field} data-testid="appt-edit-start" /></div>
        <div className="space-y-1.5"><Label className="text-xs text-slate-600">Duración (min)</Label><Input type="number" min={5} max={480} step={5} value={f.duration_minutes} onChange={(e) => setF({ ...f, duration_minutes: e.target.value })} className={field} data-testid="appt-edit-duration" /></div>
      </div>
      <div className="space-y-1.5"><Label className="text-xs text-slate-600">Notas</Label><Textarea value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} rows={3} className={field} data-testid="appt-edit-notes" /></div>
      {ask ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800" data-testid="appt-cancel-confirm-box">
          ¿Cancelar la cita? El hueco quedará libre.
          <div className="flex gap-2"><Button size="sm" variant="ghost" onClick={() => setAsk(false)} className="text-slate-700" data-testid="appt-cancel-no">No</Button>
            <Button size="sm" onClick={cancel} disabled={!!busy} className="bg-rose-600 text-white hover:bg-rose-500" data-testid="appt-cancel-yes">{busy === "cancel" && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}Sí, cancelar</Button></div>
        </div>
      ) : (
        <div className="flex justify-between gap-2">
          <Button variant="ghost" onClick={() => setAsk(true)} className="text-rose-600 hover:bg-rose-50 hover:text-rose-700" data-testid="appt-cancel-button"><Trash2 className="mr-1 h-4 w-4" />Cancelar cita</Button>
          <Button onClick={save} disabled={!!busy} className="rounded-full bg-blue-600 text-white hover:bg-blue-700" data-testid="appt-save-button">{busy === "save" && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}Guardar cambios</Button>
        </div>
      )}
    </div>
  );
}

function Create({ start, slot, onSaved }) {
  const [f, setF] = useState({ start, lead_name: "", lead_phone: "", notes: "", duration_minutes: slot });
  const [busy, setBusy] = useState(false);
  useEffect(() => setF((x) => ({ ...x, start })), [start]);
  const save = async () => {
    setBusy(true);
    try { await api.post("/appointments", { ...f, duration_minutes: Number(f.duration_minutes) }); toast.success("Cita creada"); onSaved(); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-3">
      <div className="space-y-1.5"><Label className="text-xs text-slate-600">Nombre del cliente</Label><Input autoFocus value={f.lead_name} onChange={(e) => setF({ ...f, lead_name: e.target.value })} placeholder="Ana López" className={field} data-testid="appt-new-name" /></div>
      <div className="space-y-1.5"><Label className="text-xs text-slate-600">Teléfono (opcional)</Label><Input value={f.lead_phone} onChange={(e) => setF({ ...f, lead_phone: e.target.value })} placeholder="+34 612 345 678" className={`${field} font-mono`} data-testid="appt-new-phone" /></div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5"><Label className="text-xs text-slate-600">Fecha y hora</Label><Input type="datetime-local" value={f.start} onChange={(e) => setF({ ...f, start: e.target.value })} className={field} data-testid="appt-new-start" /></div>
        <div className="space-y-1.5"><Label className="text-xs text-slate-600"><Clock className="mr-1 inline h-3 w-3" />Duración (min)</Label><Input type="number" min={5} max={480} step={5} value={f.duration_minutes} onChange={(e) => setF({ ...f, duration_minutes: e.target.value })} className={field} data-testid="appt-new-duration" /></div>
      </div>
      <div className="space-y-1.5"><Label className="text-xs text-slate-600">Notas</Label><Textarea value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} rows={2} className={field} data-testid="appt-new-notes" /></div>
      <Button onClick={save} disabled={busy || !f.lead_name.trim() || !f.start} className="w-full rounded-full bg-blue-600 text-white hover:bg-blue-700" data-testid="appt-new-save">{busy && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}Crear cita</Button>
    </div>
  );
}

export function ApptDialog({ state, slot, onClose, onChanged, onLead }) {
  const done = () => { onClose(); onChanged(); };
  return (
    <Dialog open={!!state} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg border-slate-200 bg-white text-slate-900" data-testid="appt-dialog">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold text-slate-900">{state?.appt ? state.appt.lead_name : "Nueva cita"}</DialogTitle>
          <DialogDescription className="text-slate-500">{state?.appt ? "Edita, mueve o cancela la cita." : "Se guarda en tu agenda y el agente ya no ofrecerá ese hueco."}</DialogDescription>
        </DialogHeader>
        {state?.appt && <Detail key={state.appt.id} a={state.appt} slot={slot} onSaved={done} onCancelled={done} onLead={(id) => { onClose(); onLead(id); }} />}
        {state?.create && <Create start={state.create} slot={slot} onSaved={done} />}
      </DialogContent>
    </Dialog>
  );
}
