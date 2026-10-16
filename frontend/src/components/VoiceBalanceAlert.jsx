import { useEffect, useState } from "react";
import { AlertTriangle, Bot, ExternalLink, Mic, PhoneOff, Radio, Users } from "lucide-react";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/constants";

const ICON = { voice: Mic, sip: Radio, ai: Bot, concurrency: Users, silent: PhoneOff };

function Issue({ i }) {
  const I = ICON[i.kind] || AlertTriangle;
  const crit = i.level === "critical";
  return (
    <div className="flex flex-wrap items-start gap-3 py-3 first:pt-0 last:pb-0" data-testid={`provider-alert-${i.kind}`}>
      <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg ${crit ? "bg-rose-100 text-rose-600" : "bg-amber-100 text-amber-700"}`}><I className="h-4 w-4" /></span>
      <div className="min-w-0 flex-1">
        <p className="font-semibold">{i.title}</p>
        <p className="text-sm opacity-80">{i.detail}{i.runs_out_at ? ` · al ritmo actual se agota hacia el ${fmtDate(i.runs_out_at)}` : ""}{i.reset_at ? ` · se renueva el ${fmtDate(i.reset_at)}` : ""}</p>
        {i.pct != null && <div className="mt-2 h-1.5 max-w-md overflow-hidden rounded-full bg-white/70"><div className={`h-full ${crit ? "bg-rose-500" : "bg-amber-500"}`} style={{ width: `${Math.max(2, i.pct)}%` }} /></div>}
      </div>
      <a href={i.url} {...(i.url.startsWith("#") ? {} : { target: "_blank", rel: "noreferrer" })} className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-current/20 bg-white px-3.5 py-1.5 text-xs font-semibold hover:bg-white/80" data-testid={`provider-alert-${i.kind}-action`}>{i.action} <ExternalLink className="h-3 w-3" /></a>
    </div>
  );
}

export function ProviderAlerts({ refreshKey = 0 }) {
  const [d, setD] = useState(null);
  useEffect(() => {
    const load = () => api.get("/admin/monitor/provider-alerts").then((r) => setD(r.data)).catch(() => {});
    load();
    const t = setInterval(load, 300000);
    return () => clearInterval(t);
  }, [refreshKey]);
  if (!d?.issues?.length) return null;
  const crit = d.issues.some((i) => i.level === "critical");
  return (
    <div className={`mb-6 rounded-2xl border p-4 ${crit ? "border-rose-300 bg-rose-50 text-rose-900" : "border-amber-300 bg-amber-50 text-amber-900"}`} role="alert" data-testid="provider-alerts">
      <p className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-wider" data-testid="provider-alerts-title">
        <AlertTriangle className="h-4 w-4" />{d.issues.length === 1 ? "1 proveedor necesita atención" : `${d.issues.length} proveedores necesitan atención`}
        <span className="font-normal normal-case tracking-normal opacity-60">· revisado {fmtDate(d.checked_at)}</span>
      </p>
      <div className="divide-y divide-current/10">{d.issues.map((i) => <Issue key={i.kind} i={i} />)}</div>
    </div>
  );
}
