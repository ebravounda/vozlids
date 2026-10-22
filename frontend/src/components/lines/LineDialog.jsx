import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, errMsg } from "@/lib/api";

export const Pick = ({ label, value, onChange, opts, testid, placeholder }) => (
  <div className="space-y-1.5">
    <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">{label}</p>
    <Select value={value || undefined} onValueChange={onChange}>
      <SelectTrigger className="bg-slate-950/60" data-testid={testid}><SelectValue placeholder={placeholder} /></SelectTrigger>
      <SelectContent>{opts.map(([v, l, dis]) => <SelectItem key={v} value={v} disabled={dis}>{l}</SelectItem>)}</SelectContent>
    </Select>
  </div>
);

export function sipOptions(data, current = "") {
  const free = data.sips.filter((s) => !s.used_by || s.id === current);
  return [
    ...free.map((s) => [s.id, `Línea SIP ${s.id}${s.name ? ` · ${s.name}` : ""}${s.id === current ? " (la actual)" : ""}`]),
    ["new", data.sips_left > 0 ? `Crear una línea SIP nueva (puedes crear ${data.sips_left})` : "Crear una línea SIP nueva (Zadarma no deja crear más)", data.sips_left <= 0],
  ];
}

const ROLES = { main: "Número principal del cliente", agent: "Número propio de un agente", platform: "Número de la plataforma (centrales y demos)" };

function useForm(opts) {
  const [owner, setOwner] = useState("");
  const [role, setRole] = useState("");
  const [agent, setAgent] = useState("");
  const o = opts.owners.find((x) => x.id === (owner === "platform" ? opts.platform_tenant : owner));
  const roles = owner === "platform" ? ["platform"] : o ? [...(o.main_number ? [] : ["main"]), "agent"] : [];
  useEffect(() => { setRole(roles[0] || ""); setAgent(""); }, [owner]); // eslint-disable-line react-hooks/exhaustive-deps
  const agents = (o?.agents || []).filter((a) => role !== "agent" || !a.has_own);
  return { owner, setOwner, role, setRole, agent, setAgent, o, roles, agents };
}

export function LineDialog({ mode, line, data, opts, onClose, onDone }) {
  const f = useForm(opts);
  const [sip, setSip] = useState(mode === "reconfigure" ? line.sip_id || "" : "");
  const [charge, setCharge] = useState(false);
  const [busy, setBusy] = useState(false);
  const owners = useMemo(() => [["platform", "Plataforma VozLeads (centrales y demos)"], ...opts.owners.map((x) => [x.id, `${x.name} · ${x.country}${x.kyc_ok ? "" : " · sin documentos"}`])], [opts]);
  const needAgent = f.role === "agent";
  const ready = sip && (mode === "reconfigure" || (f.owner && f.role && (!needAgent || f.agent) && (f.role === "platform" || f.o?.kyc_ok)));
  const go = async () => {
    setBusy(true);
    try {
      if (mode === "reconfigure") await api.post(`/admin/lines/${encodeURIComponent(line.number)}/reconfigure`, { sip_id: sip });
      else {
        const body = { tenant_id: f.owner === "platform" ? opts.platform_tenant : f.owner, role: f.role, agent_id: f.agent, sip_id: sip, charge: needAgent && charge && f.o?.can_charge };
        await api.post(mode === "move" ? `/admin/lines/${encodeURIComponent(line.number)}/move` : "/admin/lines/connect", mode === "move" ? body : { ...body, number: line.number });
      }
      toast.success(`${line.number} configurado y funcionando`); onDone();
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const title = { connect: "Conectar", move: "Mover", reconfigure: "Reconfigurar" }[mode];
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-lg" data-testid="line-dialog">
        <DialogHeader><DialogTitle>{title} {line.number}</DialogTitle></DialogHeader>
        <div className="space-y-4 text-sm">
          {mode !== "reconfigure" && <>
            <Pick label="¿De quién es?" value={f.owner} onChange={f.setOwner} opts={owners} testid="line-owner-select" placeholder="Elige el cliente o la plataforma" />
            {f.o && !f.o.kyc_ok && f.owner !== "platform" && <p className="flex gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200" data-testid="line-kyc-warning"><AlertTriangle className="h-4 w-4 shrink-0" />Este cliente aún no tiene sus documentos aprobados. Revísalos en «Documentos de los titulares».</p>}
            {f.roles.length > 0 && <Pick label="¿Para qué?" value={f.role} onChange={f.setRole} opts={f.roles.map((r) => [r, ROLES[r]])} testid="line-role-select" />}
            {f.o?.main_number && f.owner !== "platform" && <p className="text-xs text-slate-400">Ya tiene número principal: {f.o.main_number}.</p>}
            {(needAgent || f.role === "main" || f.role === "platform") && (f.agents.length
              ? <Pick label={needAgent ? "Agente" : "Agente que contesta"} value={f.agent} onChange={f.setAgent} opts={f.agents.map((a) => [a.id, a.name])} testid="line-agent-select" placeholder={needAgent ? "Elige el agente" : "El principal de la cuenta"} />
              : <p className="text-xs text-rose-300" data-testid="line-no-agent">{needAgent ? "Todos los agentes ya tienen número. Crea otro agente para asignarle este." : "Esta cuenta aún no tiene agentes."}</p>)}
            {needAgent && f.o && (
              <label className="flex items-start gap-2 rounded-xl border border-slate-700 p-3 text-xs text-slate-300">
                <input type="checkbox" className="mt-0.5" checked={charge} disabled={!f.o.can_charge} onChange={(e) => setCharge(e.target.checked)} data-testid="line-charge-checkbox" />
                <span>{f.o.can_charge ? <>Cobrar el número adicional por Stripe: <b>{f.o.price}</b> ahora y cada mes.</> : "Esta cuenta no paga por Stripe: no se cobrará automáticamente."}</span>
              </label>)}
          </>}
          <Pick label="Línea SIP" value={sip} onChange={setSip} opts={sipOptions(data, line.sip_id)} testid="line-sip-select" placeholder="Elige la línea SIP" />
          {sip && sip !== "new" && <p className="text-xs text-amber-300" data-testid="line-sip-warning">Se le pone una contraseña nueva a la línea {sip}: si la usas en un teléfono o una app, dejará de funcionar ahí.</p>}
          <p className="text-xs text-slate-500">VozLeads configura la línea en Zadarma, la conecta a la IA y desvía el número: queda listo para recibir y hacer llamadas.</p>
          <Button onClick={go} disabled={busy || !ready} className="w-full rounded-full" data-testid="line-confirm-button">{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}{title} y configurar todo</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function AgentDialog({ line, opts, onClose, onDone }) {
  const o = opts.owners.find((x) => x.id === line.tenant_id);
  const [agent, setAgent] = useState(line.agent_id);
  const save = async () => {
    try { await api.post(`/admin/lines/${encodeURIComponent(line.number)}/agent`, { agent_id: agent }); toast.success("Agente cambiado"); onDone(); }
    catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-md" data-testid="line-agent-dialog">
        <DialogHeader><DialogTitle>¿Qué agente contesta en {line.number}?</DialogTitle></DialogHeader>
        <Pick label="Agente" value={agent} onChange={setAgent} opts={(o?.agents || []).map((a) => [a.id, a.name])} testid="line-agent-change-select" placeholder="Elige el agente" />
        <Button onClick={save} disabled={!agent} className="mt-2 w-full rounded-full" data-testid="line-agent-save-button">Guardar</Button>
      </DialogContent>
    </Dialog>
  );
}
