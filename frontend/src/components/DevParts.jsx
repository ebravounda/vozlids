import { useState } from "react";
import { toast } from "sonner";
import { Copy, Loader2, Plus, RotateCw, Send, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";
import { fmtDate } from "@/lib/constants";

export const Code = ({ children, testid }) => <pre className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950 p-4 font-mono text-xs leading-relaxed text-emerald-200" data-testid={testid}>{children}</pre>;
const copy = (t, msg = "Copiado") => navigator.clipboard.writeText(t).then(() => toast.success(msg));
const Env = ({ env }) => <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${env === "test" ? "bg-amber-500/20 text-amber-300" : "bg-emerald-500/15 text-emerald-300"}`}>{env === "test" ? "Sandbox" : "Producción"}</span>;

export function Secret({ value, label, onClose }) {
  return (
    <div className="space-y-2 rounded-xl border border-amber-500/40 bg-amber-500/10 p-4" data-testid="secret-once">
      <p className="text-sm font-semibold text-amber-200">{label} · cópialo ahora, no se volverá a mostrar</p>
      <div className="flex gap-2"><code className="flex-1 break-all rounded-lg bg-slate-950 p-2 font-mono text-xs text-emerald-200" data-testid="secret-once-value">{value}</code>
        <Button size="sm" variant="outline" onClick={() => copy(value)} data-testid="secret-once-copy"><Copy className="h-4 w-4" /></Button></div>
      <Button size="sm" variant="ghost" onClick={onClose} data-testid="secret-once-close">Ya lo he guardado</Button>
    </div>
  );
}

export function Keys({ d, reload }) {
  const [f, setF] = useState({ name: "", env: "live", scopes: Object.keys(d.scopes), expires_days: "", allowed_ips: "" });
  const [secret, setSecret] = useState("");
  const [busy, setBusy] = useState(false);
  const run = async (fn) => { setBusy(true); try { await fn(); reload(); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); } };
  const create = () => run(async () => {
    const r = await api.post("/developer/keys", { ...f, expires_days: f.expires_days ? Number(f.expires_days) : null, allowed_ips: f.allowed_ips.split(/[\s,]+/).filter(Boolean) });
    setSecret(r.data.key); setF({ ...f, name: "" });
  });
  const rotate = (k) => run(async () => { const r = await api.post(`/developer/keys/${k.id}/rotate`); setSecret(r.data.key); toast.success("La clave anterior funcionará 24 h más"); });
  const toggleScope = (s) => setF({ ...f, scopes: f.scopes.includes(s) ? f.scopes.filter((x) => x !== s) : [...f.scopes, s] });
  return (
    <Panel className="space-y-4" data-testid="dev-keys-panel">
      <h3 className="text-lg font-semibold text-white">Claves API</h3>
      {secret && <Secret value={secret} label="Tu nueva clave" onClose={() => setSecret("")} />}
      <div className="grid gap-3 rounded-xl border border-slate-800 p-4 sm:grid-cols-2">
        <div className="space-y-1.5"><Label className="text-xs">Nombre</Label><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="CRM, ERP…" className="bg-slate-950/60" data-testid="dev-key-name-input" /></div>
        <div className="space-y-1.5"><Label className="text-xs">Entorno</Label>
          <div className="flex gap-2">{[["live", "Producción"], ["test", "Sandbox (sin llamadas reales)"]].map(([v, l]) => <Button key={v} type="button" size="sm" variant={f.env === v ? "default" : "outline"} onClick={() => setF({ ...f, env: v })} className="rounded-full" data-testid={`dev-key-env-${v}`}>{l}</Button>)}</div></div>
        <div className="space-y-1.5 sm:col-span-2"><Label className="text-xs">Permisos</Label>
          <div className="flex flex-wrap gap-2">{Object.entries(d.scopes).map(([s, l]) => (
            <button key={s} type="button" onClick={() => toggleScope(s)} className={`rounded-full border px-3 py-1 text-xs ${f.scopes.includes(s) ? "border-blue-500 bg-blue-500/15 text-blue-200" : "border-slate-700 text-slate-400"}`} data-testid={`dev-key-scope-${s.replace(":", "-")}`}><span className="font-mono">{s}</span> · {l}</button>
          ))}</div></div>
        <div className="space-y-1.5"><Label className="text-xs">Caduca en (días, opcional)</Label><Input type="number" min={1} max={730} value={f.expires_days} onChange={(e) => setF({ ...f, expires_days: e.target.value })} className="bg-slate-950/60" data-testid="dev-key-expires-input" /></div>
        <div className="space-y-1.5"><Label className="text-xs">IPs permitidas (opcional)</Label><Input value={f.allowed_ips} onChange={(e) => setF({ ...f, allowed_ips: e.target.value })} placeholder="203.0.113.10, 198.51.100.0/24" className="bg-slate-950/60 font-mono" data-testid="dev-key-ips-input" /></div>
        <Button onClick={create} disabled={busy || !f.name || !f.scopes.length} className="w-fit rounded-full" data-testid="dev-key-create-button">{busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}Generar clave</Button>
      </div>
      {d.keys.map((k) => (
        <div key={k.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-800 p-3 text-sm" data-testid={`dev-key-row-${k.id}`}>
          <div className="min-w-0">
            <p className="flex items-center gap-2 text-white">{k.name} <Env env={k.env} />{k.disabled && <span className="text-xs text-rose-300">desactivada</span>}</p>
            <p className="font-mono text-xs text-slate-400">{k.prefix}… · {k.scopes.length} permisos{k.allowed_ips.length ? ` · ${k.allowed_ips.length} IP` : ""}{k.expires_at ? ` · caduca ${fmtDate(k.expires_at)}` : ""}</p>
            <p className="text-xs text-slate-500">{k.last_used_at ? `Último uso ${fmtDate(k.last_used_at)} desde ${k.last_used_ip}` : "Sin usar todavía"}</p>
          </div>
          <div className="flex items-center gap-2">
            <Switch checked={!k.disabled} onCheckedChange={(v) => run(() => api.post(`/developer/keys/${k.id}/disable`, null, { params: { disabled: !v } }))} data-testid={`dev-key-toggle-${k.id}`} />
            <Button size="sm" variant="outline" onClick={() => rotate(k)} className="rounded-full" data-testid={`dev-key-rotate-${k.id}`}><RotateCw className="mr-1 h-4 w-4" />Rotar</Button>
            <Button size="sm" variant="ghost" onClick={() => window.confirm("¿Revocar esta clave? Las integraciones que la usen dejarán de funcionar.") && run(() => api.delete(`/developer/keys/${k.id}`))} data-testid={`dev-key-revoke-${k.id}`}><Trash2 className="h-4 w-4 text-rose-300" /></Button>
          </div>
        </div>
      ))}
    </Panel>
  );
}

export function Webhooks({ d, reload }) {
  const [f, setF] = useState({ url: "", events: d.events.filter((e) => e !== "call.started"), sandbox: false });
  const [secret, setSecret] = useState("");
  const [busy, setBusy] = useState("");
  const run = async (id, fn) => { setBusy(id); try { await fn(); reload(); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(""); } };
  const add = () => run("add", async () => { const r = await api.post("/developer/webhooks", f); setSecret(r.data.secret); setF({ ...f, url: "" }); });
  const test = (h) => run(h.id, async () => {
    const r = await api.post(`/developer/webhooks/${h.id}/test`);
    r.data.delivered ? toast.success(`Entregado (HTTP ${r.data.status_code})`) : toast.error(`No entregado: ${r.data.error || `HTTP ${r.data.status_code}`}`);
  });
  const ev = (e) => setF({ ...f, events: f.events.includes(e) ? f.events.filter((x) => x !== e) : [...f.events, e] });
  return (
    <Panel className="space-y-4" data-testid="dev-webhooks-panel">
      <h3 className="text-lg font-semibold text-white">Webhooks</h3>
      <p className="text-xs text-slate-400">Te enviamos un POST firmado cada vez que una llamada cambia de estado. Reintentamos hasta 8 veces (30 s, 1 min, 2 min…) si tu servidor no responde 2xx.</p>
      {secret && <Secret value={secret} label="Secreto de firma del webhook" onClose={() => setSecret("")} />}
      <div className="space-y-3 rounded-xl border border-slate-800 p-4">
        <Input value={f.url} onChange={(e) => setF({ ...f, url: e.target.value })} placeholder="https://tu-servidor.com/webhooks/vozleads" className="bg-slate-950/60 font-mono" data-testid="dev-webhook-url-input" />
        <div className="flex flex-wrap gap-2">{d.events.map((e) => <button key={e} type="button" onClick={() => ev(e)} className={`rounded-full border px-3 py-1 font-mono text-xs ${f.events.includes(e) ? "border-blue-500 bg-blue-500/15 text-blue-200" : "border-slate-700 text-slate-400"}`} data-testid={`dev-webhook-event-${e.replace(".", "-")}`}>{e}</button>)}</div>
        <label className="flex items-center gap-2 text-xs text-slate-300"><Switch checked={f.sandbox} onCheckedChange={(v) => setF({ ...f, sandbox: v })} data-testid="dev-webhook-sandbox-switch" />Recibir solo eventos de sandbox</label>
        <Button onClick={add} disabled={busy === "add" || !f.url.startsWith("https://") || !f.events.length} className="rounded-full" data-testid="dev-webhook-add-button">Añadir webhook</Button>
      </div>
      {d.webhooks.map((h) => (
        <div key={h.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-800 p-3 text-sm" data-testid={`dev-webhook-row-${h.id}`}>
          <div className="min-w-0"><p className="flex items-center gap-2 break-all font-mono text-xs text-white">{h.url} <Env env={h.sandbox ? "test" : "live"} /></p>
            <p className="text-xs text-slate-500">{h.events.join(", ")}{h.last_delivery_at ? ` · última entrega ${fmtDate(h.last_delivery_at)} (${h.last_status || h.last_error})` : ""}</p></div>
          <div className="flex items-center gap-2">
            <Switch checked={h.active} onCheckedChange={(v) => run(h.id, () => api.post(`/developer/webhooks/${h.id}/toggle`, null, { params: { active: v } }))} data-testid={`dev-webhook-toggle-${h.id}`} />
            <Button size="sm" variant="outline" onClick={() => test(h)} disabled={busy === h.id} className="rounded-full" data-testid={`dev-webhook-test-${h.id}`}><Send className="mr-1 h-4 w-4" />Probar</Button>
            <Button size="sm" variant="ghost" onClick={() => run(h.id, () => api.delete(`/developer/webhooks/${h.id}`))} data-testid={`dev-webhook-delete-${h.id}`}><Trash2 className="h-4 w-4 text-rose-300" /></Button>
          </div>
        </div>
      ))}
      {d.deliveries.length > 0 && (
        <div className="space-y-1 border-t border-slate-800 pt-3" data-testid="dev-deliveries-list">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Últimas entregas</p>
          {d.deliveries.map((x) => <p key={x.event_id} className="font-mono text-xs text-slate-400">{fmtDate(x.created_at)} · {x.event} · <span className={x.status === "delivered" ? "text-emerald-300" : x.status === "failed" ? "text-rose-300" : "text-amber-300"}>{x.status}</span> · {x.attempts} intento(s){x.last_status ? ` · HTTP ${x.last_status}` : ""}</p>)}
        </div>
      )}
    </Panel>
  );
}
