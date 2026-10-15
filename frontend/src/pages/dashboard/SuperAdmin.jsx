import { useEffect, useState } from "react";
import { toast } from "sonner";
import { BadgePercent, LogIn, Pencil, Plus, Save, Star, Trash2 } from "lucide-react";
import { formatPrice } from "@/lib/currency";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ProviderAlerts } from "@/components/VoiceBalanceAlert";
import { PageHeader, Panel } from "@/components/Common";
import { CustomVoices, ElevenLabsSettings, GoogleSettings, LandingSettings, ResendSettings, StripeSettings } from "@/components/AdminIntegrations";
import { ZadarmaSettings } from "@/components/AdminTelephony";
import { AdminOnboarding } from "@/components/AdminOnboarding";
import { api, errMsg } from "@/lib/api";

const LIM = { max_agents: 0, max_concurrent: 0, recording_days: 0, outbound: true, api: true, widget: true, agenda_pro: true, premium_voices: true, ambience: true };
const EMPTY = { name: "", minutes: 100, price_eur: 49, price_clp: 49000, overage_eur: 0.45, overage_clp: 450, features: "", public: true,
  recommended: false, promo_active: false, promo_label: "PROMOCIÓN", promo_price_eur: 0, promo_price_clp: 0, promo_months: 3, limits: LIM };
const NUMS = ["minutes", "price_eur", "price_clp", "overage_eur", "overage_clp", "promo_price_eur", "promo_price_clp", "promo_months"];
const FEATS = [["outbound", "Llamadas salientes"], ["api", "API para desarrolladores"], ["widget", "Botón para su web"], ["agenda_pro", "Agenda avanzada (Google + recordatorios)"], ["premium_voices", "Voces ultra naturales HD"], ["ambience", "Ambiente de oficina"]];
const NUM_LIMITS = [["max_agents", "Máx. agentes", "0 = sin límite"], ["max_concurrent", "Llamadas a la vez", "0 = sin límite"], ["recording_days", "Días que se guardan grabaciones", "0 = sin límite"]];

const Field = ({ label, hint, children }) => (
  <div className="space-y-1"><p className="text-xs font-medium text-slate-400">{label}{hint && <span className="ml-1 font-normal text-slate-600">· {hint}</span>}</p>{children}</div>
);

function limitsSummary(l = LIM) {
  const off = FEATS.filter(([k]) => l[k] === false).map(([, n]) => n);
  return [l.max_agents ? `${l.max_agents} agentes` : "agentes ilimitados", l.max_concurrent ? `${l.max_concurrent} a la vez` : null,
    l.recording_days ? `grabaciones ${l.recording_days} días` : null, off.length ? `sin: ${off.join(", ")}` : "todas las funciones"].filter(Boolean).join(" · ");
}

function Plans({ plans, reload }) {
  const [f, setF] = useState(EMPTY);
  const [editId, setEditId] = useState(null);
  const edit = (p) => { setEditId(p.id); setF({ ...EMPTY, ...p, limits: { ...LIM, ...(p.limits || {}) }, features: (p.features || []).join(", ") }); document.getElementById("plan-form")?.scrollIntoView({ behavior: "smooth", block: "start" }); };
  const reset = () => { setEditId(null); setF(EMPTY); };
  const body = (x) => {
    const b = { name: x.name, public: x.public, recommended: x.recommended, promo_active: x.promo_active, promo_label: x.promo_label,
      features: (Array.isArray(x.features) ? x.features : x.features.split(",")).map((t) => t.trim()).filter(Boolean).slice(0, 8),
      limits: Object.fromEntries(Object.entries({ ...LIM, ...(x.limits || {}) }).map(([k, v]) => [k, typeof v === "boolean" ? v : Number(v) || 0])) };
    NUMS.forEach((k) => { b[k] = Number(x[k]) || 0; });
    return b;
  };
  const create = async () => {
    try {
      if (editId) await api.put(`/admin/plans/${editId}`, body(f)); else await api.post("/admin/plans", body(f));
      toast.success(editId ? "Plan actualizado" : "Plan creado"); reset(); reload();
    } catch (e) { toast.error(errMsg(e)); }
  };
  const quick = async (p, patch, msg) => {
    try { await api.put(`/admin/plans/${p.id}`, body({ ...EMPTY, ...p, ...patch })); toast.success(msg); reload(); }
    catch (e) { toast.error(errMsg(e)); }
  };
  const del = async (id) => { try { await api.delete(`/admin/plans/${id}`); reload(); } catch (e) { toast.error(errMsg(e)); } };
  const inp = (k, type = "text") => <Input type={type} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} className="bg-slate-950/60" data-testid={`plan-${k}-input`} />;
  const setLim = (k, v) => setF({ ...f, limits: { ...f.limits, [k]: v } });
  return (
    <Panel className="space-y-4" data-testid="plans-panel">
      <h3 className="text-lg font-semibold text-white">Planes</h3>
      {plans.map((p) => (
        <div key={p.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-800 p-3" data-testid={`plan-row-${p.id}`}>
          <div className="min-w-0">
            <p className="flex flex-wrap items-center gap-2 font-semibold text-white">{p.name}{!p.public && <span className="text-xs text-slate-500">(oculto en la web)</span>}
              {p.recommended && <span className="rounded-full bg-blue-500/20 px-2 py-0.5 text-[10px] font-bold uppercase text-blue-300" data-testid={`plan-tag-recommended-${p.id}`}>Recomendado</span>}
              {p.promo_active && <span className="rounded-full bg-rose-500/20 px-2 py-0.5 text-[10px] font-bold uppercase text-rose-300" data-testid={`plan-tag-promo-${p.id}`}>{p.promo_label} · {formatPrice(p.promo_price_eur, "EUR")} / {formatPrice(p.promo_price_clp, "CLP")} · {p.promo_months} m</span>}</p>
            <p className="text-xs text-slate-400">{p.minutes} min/mes · España {formatPrice(p.price_eur, "EUR")}/mes (extra {formatPrice(p.overage_eur, "EUR", 2)}/min) · Chile {formatPrice(p.price_clp, "CLP")}/mes (extra {formatPrice(p.overage_clp, "CLP")}/min)</p>
            <p className="text-xs text-slate-500" data-testid={`plan-limits-${p.id}`}>{limitsSummary({ ...LIM, ...(p.limits || {}) })}</p>
          </div>
          <div className="flex items-center gap-3">
            <Button size="sm" variant={p.recommended ? "default" : "outline"} onClick={() => quick(p, { recommended: !p.recommended }, p.recommended ? "Ya no es el recomendado" : `${p.name} es ahora el plan recomendado`)} className="h-8 rounded-full text-xs" data-testid={`plan-recommend-${p.id}`}><Star className="mr-1 h-3.5 w-3.5" />{p.recommended ? "Recomendado" : "Recomendar"}</Button>
            <Button size="sm" variant="outline" onClick={() => (p.promo_active ? quick(p, { promo_active: false }, "Promoción desactivada") : edit({ ...p, promo_active: true }))} className={`h-8 rounded-full text-xs ${p.promo_active ? "border-rose-500 text-rose-300" : ""}`} data-testid={`plan-promo-toggle-${p.id}`}><BadgePercent className="mr-1 h-3.5 w-3.5" />{p.promo_active ? "Quitar promoción" : "Promoción"}</Button>
            <button onClick={() => edit(p)} className="text-slate-500 hover:text-emerald-300" data-testid={`plan-edit-${p.id}`}><Pencil className="h-4 w-4" /></button>
            <button onClick={() => del(p.id)} className="text-slate-500 hover:text-rose-300" data-testid={`plan-delete-${p.id}`}><Trash2 className="h-4 w-4" /></button>
          </div>
        </div>
      ))}
      <div id="plan-form" className="scroll-mt-24 space-y-4 border-t border-slate-800 pt-4" data-testid="plan-form">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{editId ? `Editando: ${f.name}` : "Nuevo plan"}</p>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Nombre del plan">{inp("name")}</Field>
          <Field label="Minutos incluidos al mes">{inp("minutes", "number")}</Field>
          <Field label="Precio mensual España (€)">{inp("price_eur", "number")}</Field>
          <Field label="Precio mensual Chile ($ CLP)">{inp("price_clp", "number")}</Field>
          <Field label="Minuto extra España (€)">{inp("overage_eur", "number")}</Field>
          <Field label="Minuto extra Chile ($ CLP)">{inp("overage_clp", "number")}</Field>
          <div className="sm:col-span-2"><Field label="Características que se muestran en la web" hint="separadas por comas">{inp("features")}</Field></div>
        </div>
        <div className="rounded-xl border border-slate-800 p-4" data-testid="plan-limits-box">
          <p className="mb-3 text-sm font-semibold text-slate-200">Qué incluye y límites</p>
          <div className="grid gap-3 sm:grid-cols-3">
            {NUM_LIMITS.map(([k, label, hint]) => <Field key={k} label={label} hint={hint}><Input type="number" min="0" value={f.limits[k]} onChange={(e) => setLim(k, e.target.value)} className="bg-slate-950/60" data-testid={`plan-limit-${k}`} /></Field>)}
          </div>
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            {FEATS.map(([k, label]) => <label key={k} className="flex items-center gap-2 text-sm text-slate-300"><Switch checked={f.limits[k]} onCheckedChange={(v) => setLim(k, v)} data-testid={`plan-feature-${k}`} />{label}</label>)}
          </div>
        </div>
        <div className="grid gap-2 sm:grid-cols-2">
          <label className="flex items-center gap-2 text-sm text-slate-300"><Switch checked={f.public} onCheckedChange={(v) => setF({ ...f, public: v })} data-testid="plan-public-switch" /> Visible en la web</label>
          <label className="flex items-center gap-2 text-sm text-slate-300"><Switch checked={f.recommended} onCheckedChange={(v) => setF({ ...f, recommended: v })} data-testid="plan-recommended-switch" /> Plan recomendado (“Más elegido”)</label>
        </div>
        <div className={`space-y-3 rounded-xl border p-4 ${f.promo_active ? "border-rose-500/50 bg-rose-500/5" : "border-slate-800"}`} data-testid="plan-promo-box">
          <label className="flex items-center gap-2 text-sm font-semibold text-slate-200"><Switch checked={f.promo_active} onCheckedChange={(v) => setF({ ...f, promo_active: v })} data-testid="plan-promo-switch" /> Promoción con precio tachado</label>
          {f.promo_active && <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Texto del cartel">{inp("promo_label")}</Field>
            <Field label="Meses con el precio rebajado">{inp("promo_months", "number")}</Field>
            <Field label="Precio de promoción España (€)" hint="0 = sin promo en España">{inp("promo_price_eur", "number")}</Field>
            <Field label="Precio de promoción Chile ($ CLP)" hint="0 = sin promo en Chile">{inp("promo_price_clp", "number")}</Field>
            <p className="text-xs text-slate-400 sm:col-span-2">Se cobra el precio rebajado durante {f.promo_months || "N"} {Number(f.promo_months) === 1 ? "mes" : "meses"} y después el precio normal. Dura hasta que la quites; quien ya la contrató la conserva.</p>
          </div>}
        </div>
        <div className="flex justify-end gap-2">
          {editId && <Button variant="ghost" onClick={reset} className="rounded-full" data-testid="plan-cancel-edit-button">Cancelar</Button>}
          <Button onClick={create} disabled={!f.name} className="rounded-full" data-testid="plan-create-button">{editId ? <Save className="mr-2 h-4 w-4" /> : <Plus className="mr-2 h-4 w-4" />}{editId ? "Guardar cambios" : "Crear plan"}</Button>
        </div>
      </div>
    </Panel>
  );
}

function UserRow({ u, plans, reload }) {
  const save = async (patch) => {
    try { await api.put(`/admin/users/${u.id}`, { plan_id: u.plan_id, allow_overage: u.allow_overage, suspended: u.suspended, ...patch }); reload(); }
    catch (e) { toast.error(errMsg(e)); }
  };
  const plan = plans.find((p) => p.id === u.plan_id);
  const remove = async () => {
    if (!window.confirm(`¿Eliminar la cuenta ${u.business_name} y todos sus datos? No se puede deshacer.`)) return;
    try { await api.delete(`/admin/users/${u.id}`); toast.success("Cuenta eliminada"); reload(); } catch (e) { toast.error(errMsg(e)); }
  };
  const impersonate = async () => { await api.post(`/admin/users/${u.id}/impersonate`); window.location.href = "/app"; };
  const over = plan && u.minutes_used >= plan.minutes;
  return (
    <tr className="border-t border-slate-800" data-testid={`admin-user-${u.id}`}>
      <td className="p-3"><p className="text-white">{u.business_name}</p><p className="text-xs text-slate-500">{u.email} · {u.country}{u.role === "admin" ? " · admin" : ""}</p></td>
      <td className="p-3">
        <Select value={u.plan_id || "none"} onValueChange={(v) => save({ plan_id: v === "none" ? null : v })}>
          <SelectTrigger className="h-8 w-40 bg-slate-950/60 text-xs" data-testid={`admin-user-plan-${u.id}`}><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="none">Sin límite</SelectItem>{plans.map((p) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}</SelectContent>
        </Select>
      </td>
      <td className={`p-3 font-mono text-xs ${over ? "text-rose-300" : "text-slate-300"}`}>{u.minutes_used}{plan ? ` / ${plan.minutes}` : ""} min</td>
      <td className="p-3 text-xs text-slate-300">{u.calls} llamadas · {u.agents} agentes</td>
      <td className="p-3"><Switch checked={u.allow_overage} onCheckedChange={(v) => save({ allow_overage: v })} data-testid={`admin-user-overage-${u.id}`} /></td>
      <td className="p-3"><Switch checked={u.suspended} onCheckedChange={(v) => save({ suspended: v })} data-testid={`admin-user-suspend-${u.id}`} /></td>
      <td className="p-3">{u.role !== "admin" && <button onClick={impersonate} className="inline-flex items-center gap-1 rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-200 hover:border-emerald-500" data-testid={`admin-user-impersonate-${u.id}`}><LogIn className="h-3.5 w-3.5" /> Entrar</button>}
        {u.role !== "admin" && <button onClick={remove} className="ml-2 text-slate-500 hover:text-rose-300" data-testid={`admin-user-delete-${u.id}`}><Trash2 className="inline h-4 w-4" /></button>}</td>
    </tr>
  );
}

export default function SuperAdmin() {
  const [users, setUsers] = useState([]);
  const [plans, setPlans] = useState([]);
  const load = () => { api.get("/admin/users").then((r) => setUsers(r.data)); api.get("/admin/plans").then((r) => setPlans(r.data)); };
  useEffect(() => { load(); }, []);
  const totals = { accounts: users.length, minutes: users.reduce((s, u) => s + u.minutes_used, 0), calls: users.reduce((s, u) => s + u.calls, 0) };
  return (
    <div className="fade-up">
      <PageHeader eyebrow="Super admin" title="Cuentas y planes" desc="Gestiona clientes, asigna planes con límite de minutos, permite exceso, suspende cuentas o entra en ellas para dar soporte." />
      <ProviderAlerts />
      <div className="mb-6 grid grid-cols-3 gap-4">
        {[["Cuentas", totals.accounts], ["Minutos este mes", totals.minutes.toFixed(1)], ["Llamadas totales", totals.calls]].map(([l, v]) => (
          <Panel key={l} className="p-5"><p className="text-xs uppercase tracking-widest text-slate-500">{l}</p><p className="mt-2 font-display text-3xl font-bold text-white">{v}</p></Panel>
        ))}
      </div>
      <div className="mb-6"><AdminOnboarding /></div>
      <div className="grid gap-6 xl:grid-cols-3">
        <Panel className="overflow-x-auto p-0 xl:col-span-2">
          <table className="w-full min-w-[820px] text-sm" data-testid="admin-users-table">
            <thead className="text-left text-xs uppercase tracking-wider text-slate-500"><tr><th className="p-3">Cuenta</th><th className="p-3">Plan</th><th className="p-3">Uso del mes</th><th className="p-3">Actividad</th><th className="p-3">Exceso</th><th className="p-3">Suspendida</th><th className="p-3"></th></tr></thead>
            <tbody>{users.map((u) => <UserRow key={u.id} u={u} plans={plans} reload={load} />)}</tbody>
          </table>
        </Panel>
        <Plans plans={plans} reload={load} />
      </div>
      <p className="mt-4 text-xs text-slate-500">Con "Exceso" activo la cuenta sigue llamando al agotar el plan. Los clientes contratan su plan desde "Mi plan" y Stripe les cobra la cuota mensual.</p>
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <ZadarmaSettings />
        <LandingSettings />
        <StripeSettings />
        <ElevenLabsSettings />
        <ResendSettings />
        <GoogleSettings />
        <CustomVoices />
      </div>
    </div>
  );
}
