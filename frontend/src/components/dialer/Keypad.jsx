import { useEffect, useState } from "react";
import { Delete, Mic, MicOff, Pause, Phone, PhoneOff, Play } from "lucide-react";
import * as P from "@/lib/zadarmaPhone";

const KEYS = [["1", ""], ["2", "ABC"], ["3", "DEF"], ["4", "GHI"], ["5", "JKL"], ["6", "MNO"], ["7", "PQRS"], ["8", "TUV"], ["9", "WXYZ"], ["*", ""], ["0", "+"], ["#", ""]];
const clock = (ms) => { const s = Math.max(0, Math.floor(ms / 1000)); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };

export function usePhone() {
  const [s, setS] = useState(P.getState());
  useEffect(() => P.subscribe(setS), []);
  return s;
}

function useNow(on) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { if (!on) return undefined; const t = setInterval(() => setNow(Date.now()), 500); return () => clearInterval(t); }, [on]);
  return now;
}

function CallInfo({ s }) {
  const now = useNow(s.status === "talking");
  if (s.status === "calling") return <p className="text-sm text-amber-300" data-testid="keypad-status">Llamando…</p>;
  if (s.status !== "talking") return <p className="text-xs text-slate-500" data-testid="keypad-status">Desde {s.line}</p>;
  return (
    <div className="flex items-center justify-center gap-4 text-sm" data-testid="keypad-status">
      <span className="font-mono text-emerald-300" data-testid="keypad-timer">{clock(now - s.startedAt)}</span>
      {s.deadline != null && <span className={`text-xs ${s.deadline - now < 60000 ? "text-rose-300" : "text-slate-400"}`} data-testid="keypad-remaining">Te quedan {clock(s.deadline - now)} min</span>}
    </div>
  );
}

const Round = ({ on, onClick, children, label, testid }) => (
  <button type="button" onClick={onClick} title={label} data-testid={testid}
    className={`flex h-12 w-12 items-center justify-center rounded-full border transition-colors ${on ? "border-amber-400 bg-amber-400/15 text-amber-300" : "border-slate-700 text-slate-300 hover:bg-slate-800"}`}>{children}</button>
);

export function Keypad({ number, setNumber }) {
  const s = usePhone();
  const live = s.status === "calling" || s.status === "talking";
  const [tones, setTones] = useState("");
  useEffect(() => { if (!live) setTones(""); }, [live]);
  const press = (k) => {
    if (s.status === "talking") { P.dtmf(k); setTones((t) => (t + k).slice(-20)); }
    else if (!live) setNumber((n) => (n + k).slice(0, 20));
  };
  return (
    <div className="mx-auto w-full max-w-xs space-y-4" data-testid="keypad">
      <div className="text-center">
        <input value={s.status === "talking" && tones ? tones : number} readOnly={live} onChange={(e) => setNumber(e.target.value.replace(/[^\d+*#\s]/g, "").slice(0, 20))}
          onKeyDown={(e) => e.key === "Enter" && !live && P.dial(number)} placeholder="Número"
          className="w-full bg-transparent text-center font-mono text-2xl tracking-wider text-white outline-none placeholder:text-slate-600" data-testid="keypad-input" />
        <div className="mt-1 h-6"><CallInfo s={s} /></div>
      </div>
      <div className="grid grid-cols-3 gap-3">
        {KEYS.map(([k, sub]) => (
          <button key={k} type="button" onClick={() => press(k)} data-testid={`keypad-key-${k === "*" ? "star" : k === "#" ? "hash" : k}`}
            className="flex h-14 flex-col items-center justify-center rounded-2xl bg-slate-800/60 text-xl font-semibold text-white transition-colors hover:bg-slate-700 active:scale-95">
            {k}<span className="text-[9px] font-normal tracking-widest text-slate-500">{sub}</span>
          </button>
        ))}
      </div>
      <div className="flex items-center justify-center gap-4">
        {s.status === "talking" && <Round on={s.muted} onClick={P.toggleMute} label="Silenciar" testid="keypad-mute">{s.muted ? <MicOff className="h-5 w-5" /> : <Mic className="h-5 w-5" />}</Round>}
        {live ? (
          <button type="button" onClick={P.hangup} className="flex h-16 w-16 items-center justify-center rounded-full bg-rose-500 text-white transition-colors hover:bg-rose-400" data-testid="keypad-hangup"><PhoneOff className="h-6 w-6" /></button>
        ) : (
          <button type="button" onClick={() => P.dial(number)} disabled={s.status !== "ready" || !number} className="flex h-16 w-16 items-center justify-center rounded-full bg-emerald-500 text-slate-950 transition-colors hover:bg-emerald-400 disabled:opacity-40" data-testid="keypad-call"><Phone className="h-6 w-6" /></button>
        )}
        {s.status === "talking" && <Round on={s.held} onClick={P.toggleHold} label="En espera" testid="keypad-hold">{s.held ? <Play className="h-5 w-5" /> : <Pause className="h-5 w-5" />}</Round>}
        {!live && number && <Round onClick={() => setNumber((n) => n.slice(0, -1))} label="Borrar" testid="keypad-backspace"><Delete className="h-5 w-5" /></Round>}
      </div>
    </div>
  );
}
