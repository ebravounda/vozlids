import { useEffect, useRef, useState } from "react";
import { Download, Loader2, Pause, Play } from "lucide-react";
import { api } from "@/lib/api";

const mmss = (s) => (Number.isFinite(s) ? `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}` : "0:00");

export function RecordingPlayer({ leadId, seconds }) {
  const ref = useRef(null);
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const [dur, setDur] = useState(seconds || 0);

  useEffect(() => {
    setUrl(""); setError(""); setPlaying(false); setTime(0);
    api.get(`/leads/${leadId}/recording-url`).then((r) => setUrl(r.data.url)).catch(() => setError("La grabación aún no está disponible."));
  }, [leadId]);

  const toggle = () => {
    const a = ref.current;
    if (!a) return;
    if (a.paused) a.play().catch(() => setError("No se pudo reproducir la grabación."));
    else a.pause();
  };
  const seek = (e) => { if (ref.current && dur) ref.current.currentTime = (Number(e.target.value) / 100) * dur; };

  if (error) return <p className="text-xs text-slate-500" data-testid="lead-audio-error">{error}</p>;
  return (
    <div className="flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-900/60 p-3" data-testid="lead-details-audio-player">
      {url && <audio ref={ref} src={url} preload="metadata" onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)}
        onTimeUpdate={(e) => setTime(e.target.currentTime)} onLoadedMetadata={(e) => Number.isFinite(e.target.duration) && setDur(e.target.duration)} />}
      <button type="button" onClick={toggle} disabled={!url} className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-emerald-500 text-slate-950 transition-colors hover:bg-emerald-400 disabled:opacity-50" data-testid="lead-details-audio-play">
        {!url ? <Loader2 className="h-4 w-4 animate-spin" /> : playing ? <Pause className="h-4 w-4" /> : <Play className="ml-0.5 h-4 w-4" />}
      </button>
      <input type="range" min="0" max="100" step="0.1" value={dur ? (time / dur) * 100 : 0} onChange={seek} className="h-1.5 flex-1 cursor-pointer accent-emerald-400" data-testid="lead-details-audio-seek" />
      <span className="shrink-0 font-mono text-xs text-slate-400" data-testid="lead-details-audio-time">{mmss(time)} / {mmss(dur)}</span>
      {url && <a href={url} target="_blank" rel="noreferrer" download className="shrink-0 text-slate-400 hover:text-emerald-300" title="Descargar" data-testid="lead-details-audio-download"><Download className="h-4 w-4" /></a>}
    </div>
  );
}
