import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, LogIn, UserPlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";
import { fmtDate } from "@/lib/constants";

const ST = { pendiente: ["Pendiente de línea", "bg-amber-100 text-amber-800"], comprando: ["Comprando", "bg-amber-100 text-amber-800"],
  activo: ["Conectado", "bg-emerald-100 text-emerald-800"], error: ["Error", "bg-rose-100 text-rose-800"],
  pausado: ["Bloqueada", "bg-slate-200 text-slate-700"], liberado: ["Liberada", "bg-slate-200 text-slate-700"] };

function AssignForm({ c, done }) {
  const [f, setF] = useState({ number: c.number || "", sip_login: "", sip_password: "" });
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await api.post(`/admin/onboarding/${c.id}/assign`, f);
      setRes(r.data);
      toast.success("Línea asignada y email enviado al cliente");
      if (!r.data.route_error) done();
    } catch (err) { toast.error(errMsg(err)); } finally { setBusy(false); }
  };
  const inp = (k, ph, type = "text") => <Input required type={type} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} placeholder={ph} className="bg-slate-950/60 font-mono text-xs" data-testid={`assign-${k}-${c.id}`} />;
  return (
    <form onSubmit={submit} className="mt-3 space-y-2 rounded-xl border border-slate-800 p-3" data-testid={`assign-form-${c.id}`}>
      <div className="grid gap-2 sm:grid-cols-3">{inp("number", c.country === "CL" ? "+56 2 ..." : "+34 9...")}{inp("sip_login", "Login SIP (ej. 123456-100)")}{inp("sip_password", "Contraseña SIP", "password")}</div>
      <Button type="submit" size="sm" disabled={busy} className="rounded-full" data-testid={`assign-submit-${c.id}`}>{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Conectar y avisar al cliente</Button>
      {res?.route_error && <p className="text-xs text-amber-300" data-testid={`assign-route-error-${c.id}`}>No se pudo dirigir el número automáticamente ({res.route_error}). En Zadarma, desvía las llamadas entrantes del número a: <b className="select-all font-mono">{res.inbound_uri}</b></p>}
    </form>
  );
}

function Row({ c, reload }) {
  const [open, setOpen] = useState(false);
  const [label, cls] = ST[c.status] || ST.pendiente;
  const enter = async () => { await api.post(`/admin/users/${c.id}/impersonate`); window.location.href = "/app/numero"; };
  const block = async (b) => { try { await api.post(`/admin/onboarding/${c.id}/block`, null, { params: { blocked: b } }); reload(); } catch (e) { toast.error(errMsg(e)); } };
  const addr = [c.billing.line, c.billing.postal_code, c.billing.city, c.billing.region].filter(Boolean).join(", ");
  return (
    <div className="border-t border-slate-800 py-4 first:border-0" data-testid={`onboarding-row-${c.id}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-semibold text-white">{c.business_name} <span className="text-xs font-normal text-slate-500">· {c.country} · alta {fmtDate(c.created_at)}</span></p>
          <p className="text-xs text-slate-400">{c.name} · {c.email}{c.doc ? ` · ${c.doc}` : ""}{c.website ? ` · ${c.website}` : ""}</p>
          {addr && <p className="text-xs text-slate-500">{addr}</p>}
          {c.number && <p className="mt-1 font-mono text-xs text-slate-300">{c.number}</p>}
          {c.error && <p className="mt-1 text-xs text-rose-300">{c.error}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${cls}`} data-testid={`onboarding-status-${c.id}`}>{label}</span>
          <Button size="sm" variant="outline" onClick={() => setOpen(!open)} className="rounded-full" data-testid={`onboarding-assign-${c.id}`}>{c.status === "activo" ? "Cambiar línea" : "Asignar número"}</Button>
          {c.status === "activo" && <Button size="sm" variant="ghost" onClick={() => block(true)} className="rounded-full" data-testid={`onboarding-block-${c.id}`}>Bloquear</Button>}
          {c.status === "pausado" && <Button size="sm" variant="ghost" onClick={() => block(false)} className="rounded-full" data-testid={`onboarding-unblock-${c.id}`}>Desbloquear</Button>}
          <Button size="sm" variant="ghost" onClick={enter} className="rounded-full" data-testid={`onboarding-enter-${c.id}`}><LogIn className="mr-1 h-4 w-4" />Entrar</Button>
        </div>
      </div>
      {open && <AssignForm c={c} done={() => { setOpen(false); reload(); }} />}
    </div>
  );
}

export function AdminOnboarding() {
  const [list, setList] = useState(null);
  const load = () => api.get("/admin/onboarding").then((r) => setList(r.data));
  useEffect(() => { load(); }, []);
  if (!list) return null;
  const pending = list.filter((c) => ["pendiente", "error", "comprando"].includes(c.status)).length;
  return (
    <Panel className="space-y-2" data-testid="admin-onboarding-panel">
      <div className="flex items-center gap-2">
        <UserPlus className="h-5 w-5 text-emerald-300" /><h3 className="text-lg font-semibold text-white">Altas de clientes</h3>
        {pending > 0 && <span className="rounded-full bg-amber-500 px-2 py-0.5 text-xs font-bold text-slate-950" data-testid="onboarding-pending-count">{pending} pendientes</span>}
      </div>
      <p className="text-xs text-slate-500">Al pagar, cada cliente aparece aquí. Compra su número en Zadarma, crea su SIP y asígnalo: el cliente recibe un email con su número y su línea queda conectada.</p>
      {list.length ? list.map((c) => <Row key={c.id} c={c} reload={load} />) : <p className="text-sm text-slate-500">Aún no hay altas.</p>}
    </Panel>
  );
}
