import { useEffect, useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, Link2, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, errMsg } from "@/lib/api";

const Pick = ({ value, onChange, opts, testid, placeholder }) => (
  <Select value={value || undefined} onValueChange={onChange}>
    <SelectTrigger className="bg-slate-950/60" data-testid={testid}><SelectValue placeholder={placeholder} /></SelectTrigger>
    <SelectContent>{opts.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
  </Select>
);

function ConnectDialog({ number, users, onClose, onDone }) {
  const [tid, setTid] = useState("");
  const [o, setO] = useState(null);
  const [target, setTarget] = useState("main");
  const [busy, setBusy] = useState(false);
  const [charge, setCharge] = useState(true);
  useEffect(() => {
    setO(null); setTarget("main");
    if (tid) api.get(`/admin/zadarma/connect-options/${tid}`).then((r) => { setO(r.data); if (r.data.has_main) setTarget(r.data.agents[0]?.id || ""); setCharge(r.data.can_charge); }).catch((e) => toast.error(errMsg(e)));
  }, [tid]);
  const targets = [...(o && !o.has_main ? [["main", "Número principal (recepcionista y llamadas)"]] : []), ...(o?.agents || []).map((a) => [a.id, `Número propio del agente ${a.name}`])];
  const go = async () => {
    setBusy(true);
    try {
      await api.post("/admin/zadarma/connect", { number: number.number, tenant_id: tid, agent_id: target === "main" ? "" : target, charge: target !== "main" && charge && o.can_charge });
      toast.success(`${number.number} conectado y funcionando`); onDone();
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-lg" data-testid="connect-number-dialog">
        <DialogHeader><DialogTitle>Conectar {number.number}</DialogTitle></DialogHeader>
        <div className="space-y-4 text-sm">
          <Pick value={tid} onChange={setTid} opts={users.map((u) => [u.id, `${u.business_name || u.email} · ${u.country}`])} testid="connect-number-client-select" placeholder="Elige el cliente" />
          {o && !o.kyc_ok && <p className="flex gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-amber-200" data-testid="connect-number-kyc-warning"><AlertTriangle className="h-4 w-4 shrink-0" />Este cliente aún no tiene sus documentos aprobados. Revísalos en «Documentos de los titulares» antes de conectar.</p>}
          {o?.kyc_ok && <>
            {o.has_main && <p className="text-xs text-slate-400">Ya tiene número principal ({o.main_number}); este número se conectará a uno de sus agentes.</p>}
            {targets.length ? <Pick value={target} onChange={setTarget} opts={targets} testid="connect-number-target-select" placeholder="¿Para qué será?" />
              : <p className="text-xs text-rose-300" data-testid="connect-number-no-target">Todos los agentes de esta cuenta ya tienen número. Crea otro agente (por ejemplo «Chile») para asignarle este número.</p>}
            {o.numbers.length > 0 && <p className="text-xs text-slate-400" data-testid="connect-number-current">Números activos de esta cuenta: {o.numbers.map((n) => n.number).join(" · ")}</p>}
            {target && target !== "main" && (
              <label className="flex items-start gap-2 rounded-xl border border-slate-700 p-3 text-xs text-slate-300" data-testid="connect-number-price-note">
                <input type="checkbox" className="mt-0.5" checked={charge} disabled={!o.can_charge} onChange={(e) => setCharge(e.target.checked)} data-testid="connect-number-charge-checkbox" />
                <span>{o.can_charge ? <>Cobrar al cliente el número adicional por Stripe: <b>{o.price}</b> ahora (mes completo) y luego cada mes.</>
                  : <>Esta cuenta no paga por Stripe (plan asignado por ti), así que <b>no se cobrará automáticamente</b>; gestiona tú el cobro.</>}</span>
              </label>)}
            <p className="text-xs text-slate-500">Se crea la línea SIP en Zadarma, se conecta a la IA y el número queda listo para recibir llamadas (recepcionista) y para llamar.</p>
          </>}
          <Button onClick={go} disabled={busy || !o?.kyc_ok || !target} className="w-full rounded-full" data-testid="connect-number-confirm-button">{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Conectar y configurar todo</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function ConnectExisting({ users, onChanged }) {
  const [rows, setRows] = useState(null);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(null);
  const load = async () => {
    setBusy(true);
    try { setRows((await api.get("/admin/zadarma/my-numbers")).data); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const free = rows?.numbers || [];
  return (
    <div className="space-y-3 border-t border-slate-800 pt-4" data-testid="zadarma-existing-numbers">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold text-white">Conectar números de mi Zadarma</p>
        <Button size="sm" variant="outline" onClick={load} disabled={busy} className="rounded-full" data-testid="zadarma-existing-load-button">
          {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}{rows ? "Actualizar" : "Ver mis números"}</Button>
      </div>
      <p className="text-xs text-slate-400">Usa números que ya tienes comprados en Zadarma: elige uno libre, el cliente y si es su número principal o el de un agente. Todo se configura solo.</p>
      {rows && !free.length && <p className="text-xs text-slate-500" data-testid="zadarma-existing-empty">No tienes números disponibles en Zadarma.</p>}
      {rows && <p className="text-xs text-slate-500" data-testid="zadarma-existing-summary">{free.length} disponibles{rows.hidden ? ` · ${rows.hidden} ocultos (en uso en VozLeads, vencidos o inactivos)` : ""}</p>}
      {rows && rows.sips !== undefined && (
        <p className={`text-xs ${rows.sips_left + rows.sips_reusable > 0 ? "text-slate-500" : "text-amber-400"}`} data-testid="zadarma-sip-room">
          Líneas SIP en Zadarma: {rows.sips} creadas · puedes crear {rows.sips_left} más{rows.sips_reusable ? ` · ${rows.sips_reusable} de VozLeads libres para reutilizar` : ""}
          {rows.sips_left + rows.sips_reusable === 0 && " — llegaste al límite: recarga saldo en Zadarma o pide a su soporte que lo amplíe antes de conectar."}
        </p>)}
      {free.map((r) => (
        <div key={r.number} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-800 p-3 text-sm" data-testid={`zadarma-existing-${r.number.slice(1)}`}>
          <span className="text-white"><span className="font-mono">{r.number}</span>
            <span className="ml-2 text-xs text-slate-400">{[r.country === "CL" ? "Chile" : r.country === "ES" ? "España" : "", r.description, r.stop_date && `pagado hasta ${r.stop_date}`].filter(Boolean).join(" · ")}</span></span>
          <Button size="sm" onClick={() => setOpen(r)} className="rounded-full" data-testid={`zadarma-existing-connect-${r.number.slice(1)}`}><Link2 className="mr-1.5 h-4 w-4" />Conectar</Button>
        </div>
      ))}
      {open && <ConnectDialog number={open} users={users} onClose={() => setOpen(null)} onDone={() => { setOpen(null); load(); onChanged(); }} />}
    </div>
  );
}
