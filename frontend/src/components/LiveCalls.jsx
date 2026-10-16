import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Ban, Headphones, Loader2, MessageSquare, PhoneCall, PhoneOff, Square, UserRound } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";

// Vapi listen socket: raw PCM s16le @16 kHz; detect mono vs interleaved stereo from the first chunk.
function looksStereo(s) {
  let d1 = 0, d2 = 0;
  for (let i = 0; i + 2 < s.length; i++) { d1 += Math.abs(s[i] - s[i + 1]); d2 += Math.abs(s[i] - s[i + 2]); }
  return d2 < d1 * 0.8;
}

function useListener() {
  const [id, setId] = useState(null);
  const ref = useRef(null);
  const stop = () => { const r = ref.current; ref.current = null; setId(null); if (r) { try { r.ws.close(); } catch { /* closed */ } r.ctx.close(); } };
  const start = async (cid) => {
    stop();
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    await ctx.resume();
    setId(cid);
    try {
      const { data } = await api.get(`/admin/monitor/calls/${cid}/listen`);
      const ws = new WebSocket(data.url);
      ws.binaryType = "arraybuffer";
      const st = { ws, ctx, t: 0, stereo: null, rate: 16000 };
      ref.current = st;
      ws.onmessage = (ev) => {
        if (typeof ev.data === "string") { try { const m = JSON.parse(ev.data); if (m.sampleRate) st.rate = m.sampleRate; if (m.channels) st.stereo = m.channels === 2; } catch { /* text */ } return; }
        const pcm = new Int16Array(ev.data);
        if (!pcm.length) return;
        if (st.stereo === null) st.stereo = looksStereo(pcm);
        const frames = st.stereo ? pcm.length >> 1 : pcm.length;
        const buf = ctx.createBuffer(1, frames, st.rate);
        const out = buf.getChannelData(0);
        for (let i = 0; i < frames; i++) out[i] = st.stereo ? (pcm[2 * i] + pcm[2 * i + 1]) / 65536 : pcm[i] / 32768;
        const src = ctx.createBufferSource();
        src.buffer = buf; src.connect(ctx.destination);
        st.t = Math.max(st.t, ctx.currentTime + 0.15);
        src.start(st.t); st.t += buf.duration;
      };
      ws.onclose = () => { if (ref.current?.ws === ws) { stop(); toast.info("La escucha ha terminado"); } };
      ws.onerror = () => toast.error("No se pudo conectar al audio de la llamada");
    } catch (e) { toast.error(errMsg(e)); stop(); ctx.close(); }
  };
  useEffect(() => stop, []);
  return { listening: id, start, stop };
}

function CallRow({ c, l, onChange }) {
  const [busy, setBusy] = useState("");
  const hang = async () => {
    if (!window.confirm(`¿Colgar la llamada con ${c.number}?`)) return;
    setBusy("hang");
    try { await api.post(`/admin/monitor/calls/${c.id}/hangup`); toast.success("Llamada colgada"); if (l.listening === c.id) l.stop(); onChange(); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(""); }
  };
  const block = async () => {
    const reason = window.prompt(`Bloquear ${c.number} en toda la plataforma. Motivo (opcional):`, "Fraude");
    if (reason === null) return;
    setBusy("block");
    try {
      await api.post("/admin/blocklist", { kind: "phone", value: c.number, reason });
      if (c.can_hangup) await api.post(`/admin/monitor/calls/${c.id}/hangup`).catch(() => {});
      toast.success("Número bloqueado y llamada colgada"); onChange();
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(""); }
  };
  const on = l.listening === c.id;
  const [msg, setMsg] = useState("");
  const say = async () => {
    setBusy("say");
    try { await api.post(`/admin/monitor/calls/${c.id}/say`, { message: msg }); toast.success("El agente lo está diciendo"); setMsg(""); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(""); }
  };
  const transfer = async () => {
    const num = window.prompt("¿A qué número paso la llamada? (con prefijo, ej. +34 612 345 678)");
    if (!num) return;
    setBusy("transfer");
    try { const r = await api.post(`/admin/monitor/calls/${c.id}/transfer`, { number: num }); toast.success(`Pasando la llamada a ${r.data.number}`); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(""); }
  };
  return (
    <div className={`flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3 text-sm ${on ? "border-emerald-500/60 bg-emerald-500/5" : "border-slate-800"}`} data-testid={`live-call-${c.id}`}>
      <div className="min-w-0">
        <p className="text-white">{c.business} · {c.lead || c.number}</p>
        <p className="text-xs text-slate-500">{c.type === "inboundPhoneCall" ? "Entrante" : "Saliente"} · {c.number} · <Elapsed from={c.started_at} /></p>
      </div>
      <div className="flex items-center gap-2">
        <span className="mr-1 flex items-center gap-1.5 text-xs text-emerald-300"><span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" />{c.status === "in-progress" ? "en curso" : c.status === "ringing" ? "sonando" : "en cola"}</span>
        <Button size="sm" variant="outline" disabled={!c.can_listen || c.status !== "in-progress"} onClick={() => (on ? l.stop() : l.start(c.id))} className={`h-8 rounded-full text-xs ${on ? "border-emerald-500 text-emerald-300" : ""}`} data-testid={`live-call-listen-${c.id}`}>
          {on ? <><Square className="mr-1 h-3.5 w-3.5" />Dejar de escuchar</> : <><Headphones className="mr-1 h-3.5 w-3.5" />Escuchar</>}</Button>
        <Button size="sm" variant="outline" disabled={!c.can_hangup || !!busy} onClick={hang} className="h-8 rounded-full border-rose-500/50 text-xs text-rose-300 hover:bg-rose-500/10" data-testid={`live-call-hangup-${c.id}`}>{busy === "hang" ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <PhoneOff className="mr-1 h-3.5 w-3.5" />}Colgar</Button>
        <Button size="sm" variant="ghost" disabled={!c.number || !!busy} onClick={block} className="h-8 rounded-full text-xs text-slate-400 hover:text-rose-300" title="Bloquear número y colgar" data-testid={`live-call-block-${c.id}`}><Ban className="mr-1 h-3.5 w-3.5" />Bloquear</Button>
      </div>
      {on && <div className="flex w-full flex-wrap items-center gap-2 border-t border-emerald-500/20 pt-3" data-testid={`live-call-controls-${c.id}`}>
          <Input value={msg} onChange={(e) => setMsg(e.target.value)} onKeyDown={(e) => e.key === "Enter" && msg.trim().length > 1 && say()} placeholder="Escribe lo que quieres que diga el agente…" className="h-9 min-w-[240px] flex-1 bg-slate-950/60 text-sm" data-testid={`live-call-say-input-${c.id}`} />
          <Button size="sm" onClick={say} disabled={msg.trim().length < 2 || !!busy} className="h-9 rounded-full text-xs" data-testid={`live-call-say-${c.id}`}>{busy === "say" ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <MessageSquare className="mr-1 h-3.5 w-3.5" />}Que lo diga</Button>
          <Button size="sm" variant="outline" onClick={transfer} disabled={!!busy} className="h-9 rounded-full text-xs" data-testid={`live-call-transfer-${c.id}`}>{busy === "transfer" ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <UserRound className="mr-1 h-3.5 w-3.5" />}Pasar a una persona</Button>
        </div>}
    </div>
  );
}

function Elapsed({ from }) {
  const [, tick] = useState(0);
  useEffect(() => { const t = setInterval(() => tick((x) => x + 1), 1000); return () => clearInterval(t); }, []);
  const s = Math.max(0, Math.floor((Date.now() - new Date(from).getTime()) / 1000));
  return <span className="font-mono">{Math.floor(s / 60)}:{String(s % 60).padStart(2, "0")}</span>;
}

export function LiveCalls() {
  const [d, setD] = useState(null);
  const l = useListener();
  const load = () => api.get("/admin/monitor/live").then((r) => setD(r.data)).catch(() => {});
  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, []);
  const n = d?.active.length || 0;
  return (
    <Panel className="space-y-3" data-testid="live-calls-panel">
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-lg font-semibold text-white"><PhoneCall className="h-5 w-5 text-emerald-300" />Llamadas en curso <span className="rounded-full bg-rose-500/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-rose-300">En directo</span></h3>
        <span className={`rounded-full px-3 py-1 font-mono text-xs ${d && n >= d.limit ? "bg-rose-500/15 text-rose-300" : "bg-emerald-500/10 text-emerald-300"}`} data-testid="live-calls-count">{n} / {d?.limit ?? "…"} líneas</span>
      </div>
      {d && !n && <p className="text-sm text-slate-500" data-testid="live-calls-empty">Ninguna llamada activa ahora mismo. Se actualiza cada 5 s.</p>}
      {d?.active.map((c) => <CallRow key={c.id} c={c} l={l} onChange={load} />)}
      {n > 0 && <p className="text-xs text-slate-500">Al escuchar, el cliente y el interlocutor no notan nada. Bloquear impide que ese número vuelva a llamar o a recibir llamadas desde cualquier cuenta.</p>}
    </Panel>
  );
}
