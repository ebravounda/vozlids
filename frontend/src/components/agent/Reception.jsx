import { useEffect, useState } from "react";
import { PhoneIncoming } from "lucide-react";
import { api } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

const Toggle = ({ checked, onChange, title, desc, testid }) => (
  <label className="flex items-start justify-between gap-4 rounded-xl border border-slate-800 bg-slate-950/40 p-4">
    <span><span className="block text-sm font-semibold text-white">{title}</span><span className="mt-1 block text-xs text-slate-400">{desc}</span></span>
    <Switch checked={checked} onCheckedChange={onChange} data-testid={testid} />
  </label>
);

const useOwnNumber = (agentId) => {
  const [num, setNum] = useState(undefined);
  useEffect(() => {
    if (!agentId) { setNum(null); return; }
    api.get("/numbers").then((r) => setNum((r.data.numbers || []).find((n) => n.agent_id === agentId && n.number) || null)).catch(() => setNum(null));
  }, [agentId]);
  return num;
};

export const ReceptionPanel = ({ agent, update }) => {
  const own = useOwnNumber(agent.id);
  if (own === undefined) return null;
  if (!own) return (
    <p className="flex items-center gap-3 rounded-xl border border-dashed border-slate-700 p-4 text-xs text-slate-400" data-testid="reception-needs-number">
      <PhoneIncoming className="h-4 w-4 shrink-0" />Cuando este agente tenga su propio número, podrás hacer que también atienda como recepcionista las llamadas que reciba.
    </p>
  );
  const on = !own.extra || (agent.receptionist ?? true);
  return (
    <div className="space-y-3" data-testid="reception-panel">
      {own.extra ? (
        <Toggle checked={on} onChange={(v) => update({ receptionist: v })} testid="reception-toggle"
          title={`También hace de recepcionista en ${own.number}`}
          desc="Cuando alguien llame a este número, atiende como recepcionista de este negocio o departamento. En las llamadas que hace sigue con su objetivo." />
      ) : (
        <p className="flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-950/40 p-4 text-sm font-semibold text-white" data-testid="reception-main-number">
          <PhoneIncoming className="h-4 w-4 shrink-0 text-emerald-400" />Atiende como recepcionista las llamadas a {own.number}
        </p>
      )}
      {on && (
        <div className="space-y-3 border-l-2 border-emerald-500/40 pl-4" data-testid="reception-options">
          <Toggle checked={agent.reception_book ?? true} onChange={(v) => update({ reception_book: v })} testid="reception-book-toggle"
            title="Agendar citas" desc="Reserva en los huecos libres de tu agenda." />
          <Toggle checked={agent.reception_message ?? true} onChange={(v) => update({ reception_message: v })} testid="reception-message-toggle"
            title="Tomar recado y avisar" desc="Apunta quién llama y qué necesita, y te avisa por email." />
          <div className="space-y-2">
            <Label>Pasar la llamada a este número (opcional)</Label>
            <Input value={agent.transfer_number || ""} onChange={(e) => update({ transfer_number: e.target.value })} placeholder="+34 600 000 000"
              className="bg-slate-950/60" data-testid="reception-transfer-input" />
            <p className="text-xs text-slate-500">Si quien llama pide hablar con una persona, el agente le pasa a este teléfono. Déjalo vacío para no pasar llamadas.</p>
          </div>
        </div>
      )}
    </div>
  );
};

export const BusinessFacts = ({ agent, update }) => (
  <div className="grid gap-5 md:grid-cols-3">
    <div className="space-y-2"><Label>Dirección</Label><Input value={agent.address || ""} maxLength={300} onChange={(e) => update({ address: e.target.value })} placeholder="Calle, número, ciudad" data-testid="agent-address-input" className="bg-slate-950/60" /></div>
    <div className="space-y-2"><Label>Horario</Label><Input value={agent.hours || ""} maxLength={500} onChange={(e) => update({ hours: e.target.value })} placeholder="L-V 9:00-18:00" data-testid="agent-hours-input" className="bg-slate-950/60" /></div>
    <div className="space-y-2"><Label>Email de avisos (opcional)</Label><Input type="email" value={agent.notify_email || ""} maxLength={200} onChange={(e) => update({ notify_email: e.target.value.trim() })} placeholder="Si está vacío, a tu email" data-testid="agent-notify-email-input" className="bg-slate-950/60" /></div>
  </div>
);
