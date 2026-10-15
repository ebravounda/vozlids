import { useEffect, useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, BellRing, Bot, CreditCard, Loader2, Mic, PhoneCall, Radio, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";
import { fmtDate } from "@/lib/constants";

const num = (v, d = 2) => Number(v || 0).toLocaleString("es-ES", { minimumFractionDigits: d, maximumFractionDigits: d });
export const cur = (v, c = "EUR", d = 2) => (v == null ? "—" : c === "CLP" ? `$${Math.round(v).toLocaleString("es-CL")} CLP` : c === "USD" ? `${num(v, d)} $` : `${num(v, d)} ${c === "EUR" ? "€" : c}`);

function Card({ icon: Icon, title, testid, children, warn }) {
  return (
    <Panel className={`space-y-2 p-5 ${warn ? "ring-1 ring-rose-400/60" : ""}`} data-testid={testid}>
      <div className="flex items-center gap-2 text-xs uppercase tracking-widest text-slate-500"><Icon className="h-4 w-4 text-emerald-300" />{title}</div>
      {children}
    </Panel>
  );
}

const Big = ({ children, testid }) => <p className="font-display text-2xl font-bold text-white" data-testid={testid}>{children}</p>;
const Hint = ({ children }) => <p className="text-xs text-slate-500">{children}</p>;
const Err = ({ s }) => (s?.error ? <p className="text-xs text-rose-300">{s.error}</p> : !s?.connected ? <p className="text-sm text-amber-300">Sin conectar</p> : null);

export function Balances({ b, alerts }) {
  if (!b) return <Panel className="p-5 text-sm text-slate-400"><Loader2 className="mr-2 inline h-4 w-4 animate-spin" />Consultando saldos…</Panel>;
  const { sip, voice, ai, stripe } = b;
  const lim = alerts?.settings || {};
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <Card icon={Radio} title="Línea SIP · Zadarma" testid="balance-sip" warn={sip.balance != null && sip.balance < lim.sip_min}>
        <Err s={sip} />{sip.balance != null && <><Big testid="balance-sip-value">{cur(sip.balance, sip.currency)}</Big><Hint>Saldo disponible para minutos y números</Hint></>}
      </Card>
      <Card icon={Mic} title="Voces · ElevenLabs" testid="balance-voice" warn={voice.pct_left != null && voice.pct_left < lim.voice_min_pct}>
        <Err s={voice} />
        {voice.limit != null && !voice.error && <>
          <Big testid="balance-voice-value">{voice.pct_left}% libre</Big>
          <div className="h-2 overflow-hidden rounded-full bg-slate-800"><div className="h-full bg-emerald-400" style={{ width: `${Math.min(100, (100 * voice.used) / (voice.limit || 1))}%` }} /></div>
          <Hint>{voice.used.toLocaleString("es-ES")} / {voice.limit.toLocaleString("es-ES")} caracteres · plan {voice.tier}{voice.reset_at ? ` · renueva ${fmtDate(voice.reset_at)}` : ""}</Hint>
        </>}
      </Card>
      <Card icon={Bot} title="Motor IA · Vapi" testid="balance-ai" warn={ai.active >= ai.concurrency_limit}>
        <Err s={ai} />
        {ai.month_spend != null && <>
          <Big testid="balance-ai-value">{cur(ai.month_spend, "USD")} <span className="text-sm font-normal text-slate-500">este mes</span></Big>
          <Hint>{ai.month_calls} llamadas · {ai.active}/{ai.concurrency_limit} líneas ocupadas ahora</Hint>
          <a href="https://dashboard.vapi.ai/org/billing/credits" target="_blank" rel="noreferrer" className="text-xs text-emerald-300 underline" data-testid="vapi-billing-link">Ver créditos restantes en Vapi</a>
        </>}
      </Card>
      <Card icon={CreditCard} title="Cobros · Stripe" testid="balance-stripe">
        {!stripe.connected ? <p className="text-sm text-amber-300">Modo pruebas (sin cuenta propia)</p> : stripe.error ? <Err s={stripe} /> : <>
          <Big testid="balance-stripe-value">{stripe.available.map((a) => cur(a.amount, a.currency)).join(" · ") || "0"}</Big>
          <Hint>Disponible · pendiente {stripe.pending.map((a) => cur(a.amount, a.currency)).join(" · ") || "0"} · {stripe.mode === "live" ? "modo real" : "modo pruebas"}</Hint>
        </>}
      </Card>
    </div>
  );
}

export function LiveCalls() {
  const [d, setD] = useState(null);
  useEffect(() => {
    const load = () => api.get("/admin/monitor/live").then((r) => setD(r.data)).catch(() => {});
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);
  const n = d?.active.length || 0;
  return (
    <Panel className="space-y-3" data-testid="live-calls-panel">
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-lg font-semibold text-white"><PhoneCall className="h-5 w-5 text-emerald-300" />Llamadas en curso</h3>
        <span className={`rounded-full px-3 py-1 font-mono text-xs ${d && n >= d.limit ? "bg-rose-500/15 text-rose-300" : "bg-emerald-500/10 text-emerald-300"}`} data-testid="live-calls-count">{n} / {d?.limit ?? "…"} líneas</span>
      </div>
      {d && !n && <p className="text-sm text-slate-500" data-testid="live-calls-empty">Ninguna llamada activa ahora mismo. Se actualiza cada 10 s.</p>}
      {d?.active.map((c) => (
        <div key={c.id} className="flex items-center justify-between rounded-xl border border-slate-800 p-3 text-sm" data-testid={`live-call-${c.id}`}>
          <div><p className="text-white">{c.business} · {c.lead || c.number}</p><p className="text-xs text-slate-500">{c.type === "inboundPhoneCall" ? "Entrante" : "Saliente"} · {c.number} · desde {fmtDate(c.started_at)}</p></div>
          <span className="flex items-center gap-1.5 text-xs text-emerald-300"><span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" />{c.status}</span>
        </div>
      ))}
    </Panel>
  );
}

export function Margins() {
  const [d, setD] = useState(null);
  useEffect(() => { api.get("/admin/monitor/margins").then((r) => setD(r.data)); }, []);
  return (
    <Panel className="overflow-x-auto p-0" data-testid="margins-panel">
      <div className="p-5 pb-2"><h3 className="text-lg font-semibold text-white">Consumo y margen por cliente (este mes)</h3><Hint>Ingreso = cuota del plan pagado por Stripe + minutos extra. Coste = IA + voz + línea de todas sus llamadas.</Hint></div>
      <table className="w-full min-w-[760px] text-sm">
        <thead className="text-left text-xs uppercase tracking-wider text-slate-500"><tr>{["Cliente", "Plan", "Llamadas", "Minutos", "Coste", "Ingreso", "Margen"].map((h) => <th key={h} className="p-3">{h}</th>)}</tr></thead>
        <tbody>{d?.rows.map((r) => (
          <tr key={r.tenant_id} className="border-t border-slate-800" data-testid={`margin-row-${r.tenant_id}`}>
            <td className="p-3"><p className="text-white">{r.business}</p><p className="text-xs text-slate-500">{r.email}</p></td>
            <td className="p-3 text-xs text-slate-300">{r.plan ? `${r.plan}${r.paying ? "" : " (sin pago)"}` : "Sin plan"}</td>
            <td className="p-3 font-mono text-xs">{r.calls}</td><td className="p-3 font-mono text-xs">{r.minutes}</td>
            <td className="p-3 font-mono text-xs">{cur(r.cost, r.currency)}</td><td className="p-3 font-mono text-xs">{cur(r.revenue, r.currency)}</td>
            <td className={`p-3 font-mono text-xs font-semibold ${r.margin < 0 ? "text-rose-300" : "text-emerald-300"}`}>{cur(r.margin, r.currency)}{r.margin_pct != null ? ` (${r.margin_pct}%)` : ""}</td>
          </tr>
        ))}</tbody>
      </table>
      {d && !d.rows.length && <p className="p-5 text-sm text-slate-500">Sin actividad este mes.</p>}
    </Panel>
  );
}

export function AlertSettings({ data, reload }) {
  const [f, setF] = useState(data.settings);
  const [busy, setBusy] = useState(false);
  const save = async () => { try { await api.put("/admin/monitor/alerts", { ...f, sip_min: Number(f.sip_min), voice_min_pct: Number(f.voice_min_pct) }); toast.success("Alertas guardadas"); reload(); } catch (e) { toast.error(errMsg(e)); } };
  const check = async () => { setBusy(true); try { await api.post("/admin/monitor/check"); toast.success("Revisión hecha"); reload(); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); } };
  return (
    <Panel className="space-y-4" data-testid="alerts-panel">
      <h3 className="flex items-center gap-2 text-lg font-semibold text-white"><BellRing className="h-5 w-5 text-emerald-300" />Alertas por email</h3>
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="space-y-1.5 sm:col-span-3"><Label className="text-xs">Enviar avisos a</Label><Input value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} className="bg-slate-950/60" data-testid="alerts-email-input" /></div>
        <div className="space-y-1.5"><Label className="text-xs">Saldo SIP mínimo (€)</Label><Input type="number" step="0.5" value={f.sip_min} onChange={(e) => setF({ ...f, sip_min: e.target.value })} className="bg-slate-950/60 font-mono" data-testid="alerts-sip-min-input" /></div>
        <div className="space-y-1.5"><Label className="text-xs">Voces: % mínimo libre</Label><Input type="number" step="1" value={f.voice_min_pct} onChange={(e) => setF({ ...f, voice_min_pct: e.target.value })} className="bg-slate-950/60 font-mono" data-testid="alerts-voice-min-input" /></div>
        <label className="flex items-end gap-2 pb-2 text-sm text-slate-300"><Switch checked={f.enabled} onCheckedChange={(v) => setF({ ...f, enabled: v })} data-testid="alerts-enabled-switch" />Activas</label>
      </div>
      <Hint>Se revisa cada 10 minutos. También avisa al instante si se llena el límite de llamadas simultáneas o el motor IA se queda sin créditos.</Hint>
      <div className="flex gap-2">
        <Button onClick={save} className="rounded-full" data-testid="alerts-save-button">Guardar</Button>
        <Button variant="outline" onClick={check} disabled={busy} className="rounded-full" data-testid="alerts-check-button">{busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}Revisar ahora</Button>
      </div>
      <div className="space-y-2 border-t border-slate-800 pt-3" data-testid="alerts-recent-list">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Últimas alertas</p>
        {!data.recent.length && <p className="text-sm text-slate-500">Todo en orden, sin alertas.</p>}
        {data.recent.map((a) => (
          <div key={a.created_at + a.kind} className="flex items-start gap-2 text-sm"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />
            <div><p className="text-white">{a.title}</p><p className="text-xs text-slate-500">{fmtDate(a.created_at)} · {a.emailed ? "email enviado" : "solo en el panel"}</p></div></div>
        ))}
      </div>
    </Panel>
  );
}
