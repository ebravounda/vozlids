import { useEffect, useState } from "react";
import { AlertTriangle, ExternalLink } from "lucide-react";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/constants";

const n = (v) => Number(v || 0).toLocaleString("es-ES");

export function VoiceBalanceAlert() {
  const [v, setV] = useState(null);
  useEffect(() => {
    const load = () => api.get("/admin/monitor/voice-alert").then((r) => setV(r.data)).catch(() => {});
    load();
    const t = setInterval(load, 300000);
    return () => clearInterval(t);
  }, []);
  if (!v?.low) return null;
  const tone = v.empty ? "border-rose-300 bg-rose-50 text-rose-900" : "border-amber-300 bg-amber-50 text-amber-900";
  return (
    <div className={`mb-6 flex flex-wrap items-start gap-4 rounded-2xl border p-4 ${tone}`} role="alert" data-testid="voice-balance-alert">
      <AlertTriangle className={`mt-0.5 h-5 w-5 shrink-0 ${v.empty ? "text-rose-600" : "text-amber-600"}`} />
      <div className="min-w-0 flex-1 space-y-1">
        <p className="font-semibold" data-testid="voice-balance-alert-title">
          {v.empty ? "Saldo de voz agotado en ElevenLabs: se está usando la voz de respaldo" : `Queda un ${v.pct_left}% de saldo de voz en ElevenLabs`}
        </p>
        <p className="text-sm opacity-80">
          {n(v.used)} de {n(v.limit)} caracteres usados · plan {v.tier}
          {v.runs_out_at ? ` · al ritmo actual se agota hacia el ${fmtDate(v.runs_out_at)}` : ""}
          {v.reset_at ? ` · se renueva el ${fmtDate(v.reset_at)}` : ""}
        </p>
        <div className="mt-2 h-1.5 max-w-md overflow-hidden rounded-full bg-white/70">
          <div className={`h-full ${v.empty ? "bg-rose-500" : "bg-amber-500"}`} style={{ width: `${Math.max(2, v.pct_left)}%` }} />
        </div>
      </div>
      <a href="https://elevenlabs.io/app/subscription" target="_blank" rel="noreferrer" className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800" data-testid="voice-balance-alert-topup">
        Recargar en ElevenLabs <ExternalLink className="h-3.5 w-3.5" />
      </a>
    </div>
  );
}
