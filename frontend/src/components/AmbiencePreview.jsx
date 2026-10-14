import { useEffect, useRef, useState } from "react";
import { Loader2, Pause, Play } from "lucide-react";
import { toast } from "sonner";
import { API } from "@/lib/api";

const previewUrl = ({ demo, ambience, volume, voice, text }) =>
  demo ? `${API}/voice-preview/demo.wav`
    : `${API}/voice-preview?${new URLSearchParams({ voice, text, ambience_id: ambience, volume: String(volume) })}`;

export const AmbiencePreview = ({ demo = false, ambience = "none", volume = 35, text = "", voice = "", label = "Escuchar ejemplo", testid = "audio-preview-play-button", className = "" }) => {
  const [state, setState] = useState("idle");
  const audioRef = useRef(null);

  const stop = () => {
    const a = audioRef.current;
    if (a) { a.onplaying = a.onended = a.onerror = null; a.pause(); a.removeAttribute("src"); a.load(); }
    audioRef.current = null;
    setState("idle");
  };

  useEffect(() => stop, []);
  useEffect(() => { if (state !== "idle") stop(); }, [ambience, volume, voice, text]); // eslint-disable-line react-hooks/exhaustive-deps

  const play = () => {
    if (state !== "idle") return stop();
    const a = new Audio();
    a.preload = "auto";
    a.onplaying = () => setState("playing");
    a.onended = stop;
    a.onerror = () => { stop(); toast.error("No se pudo generar el audio de ejemplo. Inténtalo de nuevo."); };
    a.src = previewUrl({ demo, ambience, volume, voice, text });
    audioRef.current = a;
    setState("loading");
    a.play().catch((e) => { if (e?.name !== "AbortError" && audioRef.current === a) { stop(); toast.error("Toca de nuevo para escuchar el ejemplo."); } });
  };

  return (
    <button type="button" onClick={play} data-testid={testid} data-state={state}
      className={`group inline-flex items-center gap-3 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-5 py-2.5 text-sm font-semibold text-emerald-200 transition-colors hover:bg-emerald-500/20 ${className}`}>
      <span className="grid h-7 w-7 place-items-center rounded-full bg-emerald-500 text-slate-950">
        {state === "loading" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : state === "playing" ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5 translate-x-px" />}
      </span>
      {state === "loading" ? "Preparando audio…" : state === "playing" ? "Parar" : label}
      {state === "playing" && (
        <span className="flex h-4 items-center gap-0.5" aria-hidden>
          {[0, 1, 2, 3, 4].map((i) => (
            <span key={i} className="wave-bar h-4 w-0.5 rounded bg-emerald-300" style={{ animationDelay: `${i * 0.12}s` }} />
          ))}
        </span>
      )}
    </button>
  );
};
