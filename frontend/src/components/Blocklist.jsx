import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Ban, Bot, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";
import { fmtDate } from "@/lib/constants";

const KINDS = [["phone", "Teléfono", "+34 612 345 678"], ["email", "Email", "fraude@ejemplo.com"], ["domain", "Dominio de email", "ejemplo.com"], ["ip", "IP", "203.0.113.7"]];

export function Blocklist() {
  const [rows, setRows] = useState(null);
  const q = new URLSearchParams(window.location.search);
  const [f, setF] = useState(q.get("block_ip") ? { kind: "ip", value: q.get("block_ip"), reason: q.get("reason") || "" } : { kind: "phone", value: "", reason: "" });
  const [fromEmail, setFromEmail] = useState(!!q.get("block_ip"));
  const load = () => api.get("/admin/blocklist").then((r) => setRows(r.data));
  useEffect(() => {
    load();
    if (fromEmail) setTimeout(() => document.querySelector('[data-testid="blocklist-panel"]')?.scrollIntoView({ behavior: "smooth", block: "center" }), 600);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const block = async (b, msg = "Bloqueado en toda la plataforma") => {
    try { await api.post("/admin/blocklist", b); toast.success(msg); setF({ kind: f.kind, value: "", reason: "" }); setFromEmail(false); window.history.replaceState(null, "", "/app/monitor"); load(); }
    catch (e) { toast.error(errMsg(e)); }
  };
  const add = () => block(f);
  const blockedIps = new Set((rows || []).filter((r) => r.kind === "ip").map((r) => r.value));
  const del = async (r) => { if (!window.confirm(`¿Desbloquear ${r.value}?`)) return; await api.delete(`/admin/blocklist/${r.id}`); toast.success("Desbloqueado"); load(); };
  const ph = KINDS.find((k) => k[0] === f.kind)[2];
  return (
    <Panel className={`space-y-4 ${fromEmail ? "ring-2 ring-rose-400" : ""}`} data-testid="blocklist-panel">
      {fromEmail && <p className="rounded-xl bg-rose-50 p-3 text-sm text-rose-800" data-testid="block-ip-confirm">Vienes del email de alerta: revisa la IP y pulsa <b>Bloquear</b> para confirmarlo.</p>}
      <div>
        <h3 className="flex items-center gap-2 text-lg font-semibold text-white"><Ban className="h-5 w-5 text-rose-300" />Números y emails bloqueados</h3>
        <p className="text-xs text-slate-500">Un número bloqueado no puede pedir demos ni dejar datos en formularios o en el botón web, sus llamadas entrantes se cuelgan sin gastar minutos y nadie puede llamarle desde la plataforma. Un email o dominio bloqueado no puede registrarse ni usar formularios. Los emails temporales (mailinator, yopmail…) se rechazan solos y un número que pide 5 o más demos o formularios en una hora se bloquea 24 h automáticamente y te avisamos por email.</p>
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
              {r.ips?.length > 0 && <div className="mt-1.5 flex flex-wrap gap-1.5">{r.ips.map((ip) => blockedIps.has(ip)
                ? <span key={ip} className="rounded-full bg-slate-100 px-2 py-0.5 font-mono text-[11px] text-slate-500">IP {ip} bloqueada</span>
                : <button key={ip} onClick={() => block({ kind: "ip", value: ip, reason: `Abuso desde ${r.value}` }, `IP ${ip} bloqueada`)} className="rounded-full border border-rose-300 px-2 py-0.5 font-mono text-[11px] text-rose-700 hover:bg-rose-50" data-testid={`block-ip-${ip}`}>Bloquear IP {ip}</button>)}</div>}
            </div>
            <button onClick={() => del(r)} className="text-slate-500 hover:text-emerald-300" title="Desbloquear" data-testid={`block-delete-${r.id}`}><Trash2 className="h-4 w-4" /></button>
          </div>
        ))}
      </div>
    </Panel>
  );
}
