import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, PhoneOff, Play } from "lucide-react";
import { Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";
import { fmtDate } from "@/lib/constants";

function PlayRec({ cid }) {
  const [state, setState] = useState("");
  const play = async () => {
    setState("loading");
    try {
      const r = await api.get(`/admin/monitor/calls/${cid}/recording`, { responseType: "blob" });
      const a = new Audio(URL.createObjectURL(r.data));
      a.onended = () => setState("");
      await a.play(); setState("playing");
    } catch (e) { toast.error(errMsg(e, "La grabación no está disponible")); setState(""); }
  };
  return <button onClick={play} disabled={!!state} className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-300 hover:underline disabled:opacity-60" data-testid={`silent-play-${cid}`}>
    {state === "loading" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}{state === "playing" ? "Sonando…" : "Escuchar"}</button>;
}

export function SilentCalls() {
  const [d, setD] = useState(null);
  useEffect(() => { const load = () => api.get("/admin/monitor/silent").then((r) => setD(r.data)).catch(() => {}); load(); const t = setInterval(load, 60000); return () => clearInterval(t); }, []);
  if (!d) return null;
  return (
    <Panel id="silent-calls" className="scroll-mt-24 space-y-3" data-testid="silent-calls-panel">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-lg font-semibold text-white"><PhoneOff className="h-5 w-5 text-amber-300" />Llamadas mudas</h3>
        <span className="font-mono text-xs text-slate-400" data-testid="silent-calls-count">{d.last_hour} en la última hora · {d.last_24h} en 24 h</span>
      </div>
      <p className="text-xs text-slate-500">Llamadas que se conectaron pero el cliente no dijo nada. Si salen varias seguidas, suele ser un fallo de la línea o de la voz. Te avisamos por email (máximo uno por hora).</p>
      {!d.rows.length && <p className="text-sm text-slate-500" data-testid="silent-calls-empty">Ninguna en las últimas 24 h.</p>}
      <div className="divide-y divide-slate-800">
        {d.rows.map((r) => (
          <div key={r.call_id + r.created_at} className="flex flex-wrap items-center justify-between gap-3 py-2 text-sm" data-testid={`silent-row-${r.call_id}`}>
            <div className="min-w-0">
              <p className="text-white">{r.business} · <span className="font-mono">{r.phone}</span></p>
              <p className="text-xs text-slate-500">{fmtDate(r.created_at)} · {r.direction === "entrante" ? "Entrante" : "Saliente"} · {r.seconds} s{r.bot_spoke ? "" : " · el agente tampoco habló"}</p>
            </div>
            {r.call_id && <PlayRec cid={r.call_id} />}
          </div>
        ))}
      </div>
    </Panel>
  );
}
