import { useEffect, useState } from "react";
import { AlertTriangle, CalendarCheck } from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { StatusBadge } from "@/components/Common";
import { api } from "@/lib/api";
import { fmtDate, fmtSlot } from "@/lib/constants";

const Score = ({ value }) => (
  <div data-testid="lead-interest-score">
    <div className="flex justify-between text-xs text-slate-400"><span>Puntuación de interés</span><span className="font-mono text-white">{value ?? "—"}{value != null && "%"}</span></div>
    <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-800">
      <div className="h-full rounded-full bg-gradient-to-r from-amber-400 to-emerald-400 transition-all" style={{ width: `${value || 0}%` }} />
    </div>
  </div>
);

const Transcript = ({ messages }) => (
  <div className="space-y-3" data-testid="lead-transcript">
    {messages.map((m, i) => (
      <div key={i} className={`flex ${m.role === "lead" ? "justify-end" : ""}`}>
        <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${m.role === "lead" ? "rounded-tr-sm bg-emerald-500/15 text-emerald-50" : "rounded-tl-sm bg-slate-800 text-slate-200"}`}>
          <p className="mb-0.5 text-[10px] font-semibold uppercase tracking-wider opacity-60">{m.role === "lead" ? "Lead" : "Agente"}</p>
          {m.text}
        </div>
      </div>
    ))}
  </div>
);

export const LeadDetail = ({ id, onClose }) => {
  const [lead, setLead] = useState(null);

  useEffect(() => {
    if (!id) return setLead(null);
    const load = () => api.get(`/leads/${id}`).then((r) => setLead(r.data)).catch(() => {});
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [id]);

  return (
    <Sheet open={!!id} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full overflow-y-auto border-slate-800 bg-slate-950 sm:max-w-xl" data-testid="lead-detail-sheet">
        {lead && (
          <div className="space-y-6">
            <SheetHeader>
              <SheetTitle className="text-left font-display text-2xl text-white">{lead.name}</SheetTitle>
              <div className="flex flex-wrap items-center gap-3 text-sm text-slate-400">
                <span className="font-mono">{lead.phone}</span>
                {lead.email && <span>{lead.email}</span>}
                <StatusBadge status={lead.status} testid="lead-detail-status" />
              </div>
              <p className="text-left text-xs text-slate-500">Agente {lead.agent_name} · {fmtDate(lead.created_at)}{lead.duration_seconds ? ` · ${Math.round(lead.duration_seconds)} s` : ""}{lead.is_sample ? " · Ejemplo" : ""}</p>
            </SheetHeader>
            {lead.error && (
              <div className="flex gap-3 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200" data-testid="lead-error">
                <AlertTriangle className="h-4 w-4 shrink-0" /> {lead.error}
              </div>
            )}
            {lead.status === "llamando" && <p className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-4 text-sm text-cyan-200">Llamada en curso{lead.call_phase ? ` (${lead.call_phase})` : ""}. Al colgar verás aquí la grabación y el resumen.</p>}
            {lead.appointment && (
              <div className="flex items-center gap-3 rounded-xl border border-teal-400/30 bg-teal-400/10 p-4 text-sm text-teal-100" data-testid="lead-appointment">
                <CalendarCheck className="h-5 w-5" /> Cita: <span className="font-semibold capitalize">{fmtSlot(lead.appointment.start)}</span>
              </div>
            )}
            {lead.recording_url ? (
              <audio controls src={lead.recording_url} className="w-full" data-testid="lead-details-audio-play" />
            ) : lead.call_phase === "ended" && <p className="text-xs text-slate-500">Sin grabación disponible.</p>}
            <Score value={lead.interest_score} />
            {lead.summary && (
              <div data-testid="lead-summary">
                <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-emerald-400">Resumen IA</p>
                <p className="text-sm leading-relaxed text-slate-300">{lead.summary}</p>
              </div>
            )}
            {lead.answers && (
              <div><p className="mb-2 text-xs font-semibold uppercase tracking-widest text-emerald-400">Respuestas</p><p className="text-sm text-slate-300">{lead.answers}</p></div>
            )}
            {lead.messages?.length > 0 && (
              <div>
                <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-emerald-400">Transcripción</p>
                <Transcript messages={lead.messages} />
              </div>
            )}
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
};
