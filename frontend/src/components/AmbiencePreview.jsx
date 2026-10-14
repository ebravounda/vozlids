import { useEffect, useRef, useState } from "react";
import { Pause, Play } from "lucide-react";
import { API } from "@/lib/api";

const MALE = ["alvaro", "dario", "arnau", "p_marcos", "p_gonzalo", "p_luis", "p_hector"];

function pickVoice(voiceId) {
  const voices = window.speechSynthesis?.getVoices() || [];
  const es = voices.filter((v) => v.lang?.toLowerCase().startsWith("es-es"));
  const pool = es.length ? es : voices.filter((v) => v.lang?.startsWith("es"));
  const male = MALE.includes(voiceId);
  const re = male ? /(jorge|pablo|alvaro|álvaro|dario|male|hombre|diego|enrique)/i : /(monica|mónica|elvira|lucia|laura|helena|female|mujer|marisol)/i;
  return pool.find((v) => re.test(v.name)) || pool[0] || null;
}

export const AmbiencePreview = ({ ambience, volume, text, voice, label = "Escuchar ejemplo", testid = "audio-preview-play-button", className = "" }) => {
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef(null);
  const timers = useRef([]);

  const stop = () => {
    audioRef.current?.pause();
    audioRef.current = null;
    window.speechSynthesis?.cancel();
    timers.current.forEach(clearTimeout);
    timers.current = [];
    setPlaying(false);
  };

  useEffect(() => stop, []);
  useEffect(() => { if (playing) stop(); }, [ambience, volume, voice]); // eslint-disable-line react-hooks/exhaustive-deps

  const play = () => {
    if (playing) return stop();
    setPlaying(true);
    if (!["none", "vapi_office"].includes(ambience) && volume > 0) {
      const a = new Audio(`${API}/ambience/${ambience}/${volume}.wav?v=2`);
      a.loop = true;
      a.play().catch(() => {});
      audioRef.current = a;
    }
    const synth = window.speechSynthesis;
    if (text && synth) {
      const u = new SpeechSynthesisUtterance(text);
      u.lang = "es-ES";
      u.rate = 1.03;
      const v = pickVoice(voice);
      if (v) u.voice = v;
      u.onend = () => timers.current.push(setTimeout(stop, 2200));
      timers.current.push(setTimeout(() => synth.speak(u), 1100));
    } else {
      timers.current.push(setTimeout(stop, 10000));
    }
  };

  return (
    <button type="button" onClick={play} data-testid={testid}
      className={`group inline-flex items-center gap-3 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-5 py-2.5 text-sm font-semibold text-emerald-200 transition-colors hover:bg-emerald-500/20 ${className}`}>
      <span className="grid h-7 w-7 place-items-center rounded-full bg-emerald-500 text-slate-950">
        {playing ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5 translate-x-px" />}
      </span>
      {playing ? "Parar" : label}
      {playing && (
        <span className="flex h-4 items-center gap-0.5" aria-hidden>
          {[0, 1, 2, 3, 4].map((i) => (
            <span key={i} className="wave-bar h-4 w-0.5 rounded bg-emerald-300" style={{ animationDelay: `${i * 0.12}s` }} />
          ))}
        </span>
      )}
    </button>
  );
};
