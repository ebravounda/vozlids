import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Ban, Bot, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";
import { fmtDate } from "@/lib/constants";

const KINDS = [["phone", "Teléfono", "+34 612 345 678"], ["email", "Email", "fraude@ejemplo.com"], ["domain", "Dominio de email", "ejemplo.com"]];

export function Blocklist() {
  const [rows, setRows] = useState(null);
  const [f, setF] = useState({ kind: "phone", value: "", reason: "" });
  const load = () => api.get("/admin/blocklist").then((r) => setRows(r.data));
  useEffect(() => { load(); }, []);
  const add = async () => {
    try { await api.post("/admin/blocklist", f); toast.success("Bloqueado en toda la plataforma"); setF({ ...f, value: "", reason: "" }); load(); }
    catch (e) { toast.error(errMsg(e)); }
  };
  const del = async (r) => { if (!window.confirm(`¿Desbloquear ${r.value}?`)) return; await api.delete(`/admin/blocklist/${r.id}`); toast.success("Desbloqueado"); load(); };
  const ph = KINDS.find((k) => k[0] === f.kind)[2];
  return (
    <Panel className="space-y-4" data-testid="blocklist-panel">
      <div>
        <h3 className="flex items-center gap-2 text-lg font-semibold text-white"><Ban className="h-5 w-5 text-rose-300" />Números y emails bloqueados</h3>
        <p className="text-xs text-slate-500">Un número bloqueado no puede pedir demos ni dejar datos en formularios o en el botón web, sus llamadas entrantes se cuelgan sin gastar minutos y nadie puede llamarle desde la plataforma. Un email o dominio bloqueado no puede registrarse ni usar formularios. Los emails temporales (mailinator, yopmail…) se rechazan solos y un número que pide más de 5 demos o formularios en una hora se bloquea 24 h automáticamente.</p>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        <select value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })} className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900" data-testid="block-kind-select">
          {KINDS.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
        </select>
        <Input value={f.value} onChange={(e) => setF({ ...f, value: e.target.value })} placeholder={ph} className="bg-slate-950/60" data-testid="block-value-input" />
        <Input value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} placeholder="Motivo (opcional)" className="bg-slate-950/60" data-testid="block-reason-input" />
        <Button onClick={add} disabled={f.value.trim().length < 3} className="rounded-full sm:w-fit sm:justify-self-end" data-testid="block-add-button"><Ban className="mr-2 h-4 w-4" />Bloquear</Button>
      </div>
      {rows && !rows.length && <p className="text-sm text-slate-500" data-testid="blocklist-empty">No hay nada bloqueado.</p>}
      <div className="divide-y divide-slate-800">
        {rows?.map((r) => (
          <div key={r.id} className="flex flex-wrap items-center justify-between gap-3 py-2.5 text-sm" data-testid={`block-row-${r.id}`}>
            <div className="min-w-0">
              <p className="font-mono text-white">{r.value} <span className="ml-1 font-sans text-xs text-slate-500">{KINDS.find((k) => k[0] === r.kind)?.[1]}</span></p>
              <p className="text-xs text-slate-500">{r.source === "auto" && <Bot className="mr-1 inline h-3 w-3" />}{r.reason || "Sin motivo"} · {fmtDate(r.created_at)}{r.expires_at ? ` · hasta ${fmtDate(r.expires_at)}` : ""}</p>
            </div>
            <button onClick={() => del(r)} className="text-slate-500 hover:text-emerald-300" title="Desbloquear" data-testid={`block-delete-${r.id}`}><Trash2 className="h-4 w-4" /></button>
          </div>
        ))}
      </div>
    </Panel>
  );
}
