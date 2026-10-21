import { useEffect, useRef, useState } from "react";
import { Loader2, Pause, Play } from "lucide-react";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/api";

const SILENT = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=";
const blobCache = new Map();

const fetchAudio = async ({ demo, ambience, volume, voice, text, lang }) => {
  const key = JSON.stringify([demo, ambience, volume, voice, text, lang]);
  if (blobCache.has(key)) return blobCache.get(key);
  try {
    const r = await api.get(demo ? "/voice-preview/demo.wav" : "/voice-preview", {
      params: demo ? undefined : { voice, text, ambience_id: ambience, volume, lang }, responseType: "blob", timeout: 90000 });
    const url = URL.createObjectURL(r.data);
    blobCache.set(key, url);
    return url;
  } catch (e) {
    const b = e?.response?.data;
    if (b instanceof Blob) { try { e.response.data = JSON.parse(await b.text()); } catch { /* not json */ } }
    if (e?.code === "ECONNABORTED") throw new Error("El audio tarda demasiado. Inténtalo de nuevo en unos segundos.");
    throw new Error(e?.response ? errMsg(e, "No se pudo generar el audio de ejemplo.") : "Sin conexión con el servidor. Revisa tu internet.");
  }
};

export const AmbiencePreview = ({ demo = false, ambience = "none", volume = 35, text = "", voice = "", lang = "es", label = "Escuchar ejemplo", testid = "audio-preview-play-button", className = "" }) => {
  const [state, setState] = useState("idle");
  const audioRef = useRef(null);

  const stop = () => {
    const a = audioRef.current;
    if (a) { a.onplaying = a.onended = a.onerror = null; a.pause(); }
    audioRef.current = null;
    setState("idle");
  };

  useEffect(() => stop, []);
  useEffect(() => { if (state !== "idle") stop(); }, [ambience, volume, voice, text]); // eslint-disable-line react-hooks/exhaustive-deps

  const play = async () => {
    if (state !== "idle") return stop();
    const a = new Audio();
    a.play().catch(() => {});
    a.src = SILENT;
    a.play().catch(() => {});
    audioRef.current = a;
    setState("loading");
    try {
      const url = await fetchAudio({ demo, ambience, volume, voice, text, lang });
      if (audioRef.current !== a) return;
      a.onplaying = () => setState("playing");
      a.onended = stop;
      a.onerror = () => { stop(); toast.error("Tu navegador no pudo reproducir el audio. Prueba con otro navegador."); };
      a.src = url;
      await a.play();
    } catch (e) {
      if (audioRef.current !== a) return;
      stop();
      toast.error(e?.name === "NotAllowedError" ? "Pulsa de nuevo para escuchar: el audio ya está listo." : e.message);
    }
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
