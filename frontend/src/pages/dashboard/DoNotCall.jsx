import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader, Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";
import { fmtDate } from "@/lib/constants";

export default function DoNotCall() {
  const [items, setItems] = useState([]);
  const [phone, setPhone] = useState("");
  const [reason, setReason] = useState("");

  const load = () => api.get("/dnc").then((r) => setItems(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const add = async (e) => {
    e.preventDefault();
    try {
      await api.post("/dnc", { phone, reason });
      setPhone(""); setReason("");
      toast.success("Número bloqueado");
      load();
    } catch (err) { toast.error(errMsg(err)); }
  };

  const remove = async (id) => {
    await api.delete(`/dnc/${id}`);
    load();
  };

  return (
    <div className="fade-up">
      <PageHeader eyebrow="Privacidad" title="Lista de no llamar" desc="Estos números nunca reciben llamadas. Quien lo pide durante una llamada se añade solo." />
      <Panel className="mb-6">
        <form onSubmit={add} className="flex flex-col gap-3 sm:flex-row">
          <Input value={phone} onChange={(e) => setPhone(e.target.value)} required placeholder="+34 600 000 000" className="h-11 bg-slate-950/60 font-mono sm:w-60" data-testid="dnc-add-phone-input" />
          <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Motivo (opcional)" className="h-11 bg-slate-950/60" data-testid="dnc-add-reason-input" />
          <Button type="submit" className="h-11 rounded-full px-6 font-semibold" data-testid="dnc-add-phone-button"><Plus className="mr-2 h-4 w-4" /> Bloquear</Button>
        </form>
      </Panel>
      <Panel className="p-0">
        {items.map((d) => (
          <div key={d.id} className="flex items-center justify-between gap-3 border-b border-slate-800/70 px-6 py-4" data-testid={`dnc-row-${d.id}`}>
            <div>
              <p className="font-mono text-sm text-white">{d.phone}</p>
              <p className="text-xs text-slate-500">{d.reason} · {fmtDate(d.created_at)}</p>
            </div>
            <button onClick={() => remove(d.id)} className="rounded-lg p-2 text-slate-500 hover:bg-rose-500/10 hover:text-rose-300" data-testid={`dnc-delete-${d.id}`} title="Quitar"><Trash2 className="h-4 w-4" /></button>
          </div>
        ))}
        {!items.length && <p className="p-8 text-center text-sm text-slate-500" data-testid="dnc-empty">La lista está vacía.</p>}
      </Panel>
    </div>
  );
}
