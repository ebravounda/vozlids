import { useEffect, useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, CalendarCheck, Copy, Download, PhoneCall } from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { StatusBadge } from "@/components/Common";
import { SubjectActions } from "@/components/PrivacyParts";
import { api } from "@/lib/api";
import { fmtDate, fmtSlot } from "@/lib/constants";
import { cap } from "@/lib/cal";
import { LangFlag } from "@/components/LangFlag";
import { RecordingPlayer } from "@/components/RecordingPlayer";

const Score = ({ value }) => (
  <div data-testid="lead-interest-score">
    <div className="flex justify-between text-xs text-slate-400"><span>Puntuación de interés</span><span className="font-mono text-white">{value ?? "—"}{value != null && "%"}</span></div>
    <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-800">
      <div className="h-full rounded-full bg-gradient-to-r from-amber-400 to-emerald-400 transition-all" style={{ width: `${value || 0}%` }} />
    </div>
  </div>
);

const mmss = (t) => (t == null ? "" : `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(Math.floor(t % 60)).padStart(2, "0")}`);

const asText = (lead) =>
  [`Llamada con ${lead.name} (${lead.phone}) · Agente ${lead.agent_name} · ${fmtDate(lead.created_at)}`, "",
    ...lead.messages.map((m) => `[${mmss(m.t)}] ${m.role === "lead" ? "Cliente" : "Agente"}: ${m.text}`)].join("\n");

const TranscriptActions = ({ lead }) => {
  const copy = () => { navigator.clipboard?.writeText(asText(lead)); toast.success("Transcripción copiada"); };
  const download = () => {
    const url = URL.createObjectURL(new Blob([asText(lead)], { type: "text/plain;charset=utf-8" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: `transcripcion-${lead.name.replace(/\s+/g, "-")}.txt` });
    a.click();
    URL.revokeObjectURL(url);
  };
  const cls = "inline-flex items-center gap-1.5 rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300 hover:text-white";
  return (
    <div className="flex gap-2">
      <button onClick={copy} className={cls} data-testid="transcript-copy-button"><Copy className="h-3.5 w-3.5" /> Copiar</button>
      <button onClick={download} className={cls} data-testid="transcript-download-button"><Download className="h-3.5 w-3.5" /> Descargar .txt</button>
    </div>
  );
};

const Transcript = ({ messages }) => (
  <div className="space-y-3" data-testid="lead-transcript">
    {messages.map((m, i) => (
      <div key={i} className={`flex ${m.role === "lead" ? "justify-end" : ""}`}>
        <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${m.role === "lead" ? "rounded-tr-sm bg-emerald-500/15 text-emerald-50" : "rounded-tl-sm bg-slate-800 text-slate-200"}`}>
          <p className="mb-0.5 text-[10px] font-semibold uppercase tracking-wider opacity-60">{m.role === "lead" ? "Cliente" : "Agente"} {m.t != null && <span className="font-mono">· {mmss(m.t)}</span>}</p>
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
      <SheetContent aria-describedby={undefined} className="w-full overflow-y-auto border-slate-800 bg-slate-950 sm:max-w-xl" data-testid="lead-detail-sheet">
        {!lead && <SheetTitle className="sr-only">Detalle del lead</SheetTitle>}
        {lead && (
          <div className="space-y-6">
            <SheetHeader>
              <SheetTitle className="text-left font-display text-2xl text-white">{lead.name}</SheetTitle>
              <div className="flex flex-wrap items-center gap-3 text-sm text-slate-400">
                <span className="font-mono">{lead.phone}</span>
                {lead.email && <span>{lead.email}</span>}
                <StatusBadge status={lead.status} testid="lead-detail-status" />
                <LangFlag lang={lead.language} phone={lead.phone} withName testid="lead-detail-language" />
              </div>
              <p className="text-left text-xs text-slate-500">Agente {lead.agent_name}{lead.executive && lead.executive !== lead.agent_name ? ` (habló ${lead.executive})` : ""} · {fmtDate(lead.created_at)}{lead.duration_seconds ? ` · ${Math.round(lead.duration_seconds)} s` : ""}{lead.is_sample ? " · Ejemplo" : ""}</p>
              {lead.memory_calls > 0 && <p className="text-left text-xs text-blue-500" data-testid="lead-memory-note">El agente recordó {lead.memory_calls === 1 ? "1 llamada anterior" : `${lead.memory_calls} llamadas anteriores`} con este número</p>}
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
            {lead.callback_at && (
              <div className="flex items-center gap-3 rounded-xl border border-amber-400/30 bg-amber-400/10 p-4 text-sm text-amber-100" data-testid="lead-callback">
                <PhoneCall className="h-5 w-5" /> {lead.callback_of ? "Rellamada programada para" : "El agente volverá a llamar el"} <span className="font-semibold">{cap(fmtSlot(lead.callback_at))}</span>
              </div>
            )}
            {lead.recording_url ? (
              <RecordingPlayer leadId={lead.id} seconds={lead.duration_seconds} />
            ) : lead.transcript_purged_at ? <p className="text-xs text-slate-500" data-testid="lead-purged-note">Transcripción y grabación eliminadas el {fmtDate(lead.transcript_purged_at)} por tu plazo de conservación.</p>
              : lead.call_phase === "ended" && <p className="text-xs text-slate-500">Sin grabación disponible.</p>}
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
                <div className="mb-3 flex items-center justify-between gap-3">
                  <p className="text-xs font-semibold uppercase tracking-widest text-emerald-400">Transcripción completa</p>
                  <TranscriptActions lead={lead} />
                </div>
                <Transcript messages={lead.messages} />
              </div>
            )}
            {!lead.is_sample && (
              <div className="space-y-2 border-t border-slate-800 pt-4" data-testid="lead-rgpd-actions">
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Privacidad (RGPD) · todos los datos de este contacto</p>
                <SubjectActions subject={{ phone: lead.phone, email: lead.email || "" }} onErased={onClose} compact />
              </div>
            )}
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
};
