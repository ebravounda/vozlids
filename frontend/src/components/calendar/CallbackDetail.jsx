import { useState } from "react";
import { toast } from "sonner";
import { CalendarClock, ExternalLink, Loader2, Phone, PhoneCall, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, errMsg } from "@/lib/api";
import { cap } from "@/lib/cal";
import { fmtSlot } from "@/lib/constants";

export function CallbackDetail({ a, onDone, onLead }) {
  const [start, setStart] = useState(a.start);
  const [busy, setBusy] = useState("");
  const [ask, setAsk] = useState(false);
  const run = async (k, fn, msg) => { setBusy(k); try { await fn(); toast.success(msg); onDone(); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(""); } };
  return (
    <div className="space-y-4" data-testid="callback-detail">
      <div className="space-y-2 rounded-xl bg-amber-50 p-4 text-sm text-amber-900">
        <p className="flex items-center gap-2 font-semibold"><CalendarClock className="h-4 w-4 text-amber-600" />{cap(fmtSlot(a.start))}</p>
        <p className="flex items-center gap-2"><Phone className="h-4 w-4 text-amber-500" /><span className="font-mono" data-testid="callback-phone">{a.lead_phone}</span></p>
        <p className="flex items-center gap-2 text-amber-800" data-testid="callback-info"><PhoneCall className="h-4 w-4" />El cliente pidió que le llamaran más tarde · rellamada {a.callback_count} de 2{a.agent_name ? ` · ${a.agent_name}` : ""}</p>
        {a.lead_id && <button onClick={() => onLead(a.lead_id)} className="inline-flex items-center gap-1 text-xs font-semibold text-amber-700 hover:underline" data-testid="callback-open-lead">Ver la llamada anterior <ExternalLink className="h-3 w-3" /></button>}
      </div>
      <div className="space-y-1.5">
        <Label className="text-xs text-slate-600">Nueva fecha y hora (lunes a viernes, 9:00–21:00)</Label>
        <Input type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} className="border-slate-200 bg-white text-slate-900" data-testid="callback-edit-start" />
      </div>
      <div className="flex justify-between gap-2">
        <Button variant="ghost" disabled={!!busy} onClick={() => (ask ? run("del", () => api.delete(`/callbacks/${a.id}`), "Rellamada cancelada") : setAsk(true))} className="text-rose-600 hover:bg-rose-50 hover:text-rose-700" data-testid="callback-cancel-button">
          {busy === "del" ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Trash2 className="mr-1 h-4 w-4" />}{ask ? "¿Seguro? Pulsa para cancelar" : "Cancelar rellamada"}</Button>
        <Button disabled={!!busy || start === a.start} onClick={() => run("save", () => api.patch(`/callbacks/${a.id}`, { start }), `Rellamada movida a las ${start.slice(11)}`)} className="rounded-full bg-amber-500 text-white hover:bg-amber-600" data-testid="callback-save-button">
          {busy === "save" && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}Cambiar hora</Button>
      </div>
    </div>
  );
}
