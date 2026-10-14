import { useEffect, useState } from "react";
import { toast } from "sonner";
import { LogIn, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageHeader, Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";

function Plans({ plans, reload }) {
  const [f, setF] = useState({ name: "", minutes: 100, price: 49, currency: "EUR", overage_price: 0.45 });
  const create = async () => {
    try { await api.post("/admin/plans", { ...f, minutes: Number(f.minutes), price: Number(f.price), overage_price: Number(f.overage_price) }); toast.success("Plan creado"); reload(); }
    catch (e) { toast.error(errMsg(e)); }
  };
  const del = async (id) => { try { await api.delete(`/admin/plans/${id}`); reload(); } catch (e) { toast.error(errMsg(e)); } };
  const inp = (k, ph, type = "text") => <Input type={type} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} placeholder={ph} className="bg-slate-950/60" data-testid={`plan-${k}-input`} />;
  return (
    <Panel className="space-y-4" data-testid="plans-panel">
      <h3 className="text-lg font-semibold text-white">Planes</h3>
      {plans.map((p) => (
        <div key={p.id} className="flex items-center justify-between rounded-xl border border-slate-800 p-3" data-testid={`plan-row-${p.id}`}>
          <div><p className="font-semibold text-white">{p.name}</p><p className="text-xs text-slate-400">{p.minutes} min/mes · {p.price} {p.currency}/mes · exceso {p.overage_price} {p.currency}/min</p></div>
          <button onClick={() => del(p.id)} className="text-slate-500 hover:text-rose-300" data-testid={`plan-delete-${p.id}`}><Trash2 className="h-4 w-4" /></button>
        </div>
      ))}
      <div className="grid grid-cols-2 gap-2 border-t border-slate-800 pt-4">
        {inp("name", "Nombre del plan")}{inp("minutes", "Minutos/mes", "number")}{inp("price", "Precio/mes", "number")}{inp("overage_price", "Precio minuto extra", "number")}
        <Select value={f.currency} onValueChange={(v) => setF({ ...f, currency: v })}>
          <SelectTrigger className="bg-slate-950/60" data-testid="plan-currency-select"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="EUR">EUR</SelectItem><SelectItem value="CLP">CLP</SelectItem></SelectContent>
        </Select>
        <Button onClick={create} disabled={!f.name} className="rounded-full" data-testid="plan-create-button"><Plus className="mr-2 h-4 w-4" /> Crear plan</Button>
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
      <td className="p-3">{u.role !== "admin" && <button onClick={impersonate} className="inline-flex items-center gap-1 rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-200 hover:border-emerald-500" data-testid={`admin-user-impersonate-${u.id}`}><LogIn className="h-3.5 w-3.5" /> Entrar</button>}</td>
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
      <div className="mb-6 grid grid-cols-3 gap-4">
        {[["Cuentas", totals.accounts], ["Minutos este mes", totals.minutes.toFixed(1)], ["Llamadas totales", totals.calls]].map(([l, v]) => (
          <Panel key={l} className="p-5"><p className="text-xs uppercase tracking-widest text-slate-500">{l}</p><p className="mt-2 font-display text-3xl font-bold text-white">{v}</p></Panel>
        ))}
      </div>
      <div className="grid gap-6 xl:grid-cols-3">
        <Panel className="overflow-x-auto p-0 xl:col-span-2">
          <table className="w-full min-w-[820px] text-sm" data-testid="admin-users-table">
            <thead className="text-left text-xs uppercase tracking-wider text-slate-500"><tr><th className="p-3">Cuenta</th><th className="p-3">Plan</th><th className="p-3">Uso del mes</th><th className="p-3">Actividad</th><th className="p-3">Exceso</th><th className="p-3">Suspendida</th><th className="p-3"></th></tr></thead>
            <tbody>{users.map((u) => <UserRow key={u.id} u={u} plans={plans} reload={load} />)}</tbody>
          </table>
        </Panel>
        <Plans plans={plans} reload={load} />
      </div>
      <p className="mt-4 text-xs text-slate-500">Con "Exceso" activo la cuenta sigue llamando al agotar el plan y los minutos extra se cobran al precio del plan (el cobro automático con tarjeta llegará con Stripe).</p>
    </div>
  );
}
