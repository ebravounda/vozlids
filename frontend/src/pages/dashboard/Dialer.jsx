import { useEffect, useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, Headphones, Loader2, Phone, PhoneCall, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Panel } from "@/components/Common";
import { Keypad, PhoneLog, usePhone } from "@/components/dialer/Keypad";
import * as P from "@/lib/zadarmaPhone";
import { api, errMsg } from "@/lib/api";

const mmss = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
const STATUS = { answered: "Contestada", busy: "Ocupado", "no answer": "Sin respuesta", cancel: "Cancelada", failed: "Fallida" };

function Connect({ numbers }) {
  const s = usePhone();
  const [number, setNumber] = useState(numbers[0] || "");
  return (
    <div className="mx-auto max-w-xs space-y-4 py-6 text-center" data-testid="dialer-connect">
      <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-300"><Phone className="h-7 w-7" /></div>
      {numbers.length > 1 && (
        <Select value={number} onValueChange={setNumber}>
          <SelectTrigger className="bg-slate-950/60 font-mono" data-testid="dialer-number-select"><SelectValue /></SelectTrigger>
          <SelectContent>{numbers.map((n) => <SelectItem key={n} value={n} className="font-mono">{n}</SelectItem>)}</SelectContent>
        </Select>
      )}
      <p className="text-sm text-slate-400">Llamarás con <span className="font-mono text-white">{number}</span></p>
      {s.status === "error" && <p className="flex items-start gap-2 rounded-xl bg-rose-500/10 p-3 text-left text-xs text-rose-300" data-testid="dialer-error"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />{s.error}</p>}
      <Button onClick={() => P.connect(number)} disabled={s.status === "loading"} className="w-full rounded-full bg-emerald-500 text-slate-950 hover:bg-emerald-400" data-testid="dialer-start-button">
        {s.status === "loading" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Phone className="mr-2 h-4 w-4" />} Activar teléfono
      </Button>
      <p className="flex items-start gap-2 text-left text-xs text-slate-500"><Headphones className="mt-0.5 h-4 w-4 shrink-0" /> El navegador te pedirá el micrófono. Usa auriculares para evitar eco.</p>
    </div>
  );
}

function Recents({ calls, onPick }) {
  const seen = new Set();
  const list = calls.filter((c) => c.to && !seen.has(c.to) && seen.add(c.to)).slice(0, 8);
  return (
    <div data-testid="dialer-recents">
      <h3 className="mb-3 text-sm font-semibold text-white">Recientes</h3>
      {list.length ? list.map((c) => (
        <button key={c.to} type="button" onClick={() => onPick(c.to)} className="flex w-full items-center justify-between rounded-xl px-3 py-2 text-left transition-colors hover:bg-slate-800/60" data-testid={`dialer-recent-${c.to}`}>
          <span><span className="block font-mono text-sm text-white">+{c.to}</span><span className="text-[11px] text-slate-500">{c.start} · {mmss(c.seconds)}</span></span>
          <PhoneCall className="h-4 w-4 text-emerald-300" />
        </button>
      )) : <p className="text-xs text-slate-500" data-testid="dialer-recents-empty">Aquí verás los últimos números a los que llamaste.</p>}
    </div>
  );
}

function History({ d, onRefresh }) {
  const admin = d?.calls?.some((c) => c.cost !== undefined);
  return (
    <Panel className="overflow-x-auto p-0" data-testid="dialer-history">
      <div className="flex items-center justify-between p-5 pb-2">
        <div>
          <h3 className="text-lg font-semibold text-white">Tus llamadas de este mes</h3>
          <p className="text-xs text-slate-500" data-testid="dialer-history-minutes">{d ? `${d.minutes} min en ${d.calls.length} llamadas · se descuentan de tu plan` : "Cargando…"}</p>
        </div>
        <Button size="sm" variant="ghost" onClick={onRefresh} data-testid="dialer-history-refresh"><RefreshCw className="h-4 w-4" /></Button>
      </div>
      {d && (d.calls.length ? (
        <table className="w-full min-w-[560px] text-sm">
          <thead className="text-left text-xs uppercase tracking-wider text-slate-500"><tr>{["Fecha", "Número", "Estado", "Duración", ...(admin ? ["Coste Zadarma"] : [])].map((h) => <th key={h} className="p-3 font-medium">{h}</th>)}</tr></thead>
          <tbody>{d.calls.map((c) => (
            <tr key={c.id} className="border-t border-slate-800" data-testid={`dialer-call-${c.id}`}>
              <td className="p-3 text-xs text-slate-400">{c.start}</td>
              <td className="p-3"><p className="font-mono text-white">+{c.to}</p><p className="text-[11px] text-slate-500">{c.destination}</p></td>
              <td className="p-3 text-xs">{STATUS[c.status] || c.status}</td>
              <td className="p-3 font-mono text-xs">{mmss(c.seconds)}</td>
              {admin && <td className="p-3 font-mono text-xs">{c.cost} {c.currency}</td>}
            </tr>))}</tbody>
        </table>
      ) : <p className="p-5 pt-2 text-sm text-slate-500" data-testid="dialer-history-empty">Aún no has hecho llamadas desde el panel este mes. Pueden tardar unos minutos en aparecer.</p>)}
    </Panel>
  );
}

export default function Dialer() {
  const s = usePhone();
  const [info, setInfo] = useState(null);
  const [hist, setHist] = useState(null);
  const [number, setNumber] = useState("");
  const load = () => api.get("/dialer/history").then((r) => { setHist(r.data); if (r.data.error) toast.error(r.data.error); }).catch((e) => toast.error(errMsg(e)));
  useEffect(() => {
    api.get("/dialer").then((r) => setInfo(r.data)).catch(() => setInfo({ numbers: [] }));
    load();
    const f = () => setTimeout(load, 4000);
    window.addEventListener("voz-dialer-ended", f);
    return () => window.removeEventListener("voz-dialer-ended", f);
  }, []);
  const on = ["ready", "calling", "talking"].includes(s.status);
  const pick = (to) => { setNumber(`+${to}`); if (s.status === "ready") P.dial(`+${to}`); };
  return (
    <div className="space-y-6" data-testid="dialer-page">
      <div>
        <h1 className="font-display text-3xl font-semibold text-white">Teléfono</h1>
        <p className="mt-1 text-sm text-slate-400">Llama tú mismo a tus clientes desde el navegador, con tu número de empresa. Los minutos se descuentan de tu plan.</p>
      </div>
      {info && !info.numbers.length ? (
        <Panel data-testid="dialer-no-number"><p className="text-sm text-slate-400">Aún no tienes un número activo. Pídelo en «Mi número» para poder llamar desde aquí.</p></Panel>
      ) : info && (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
          <Panel data-testid="dialer-phone-card">{on ? <Keypad number={number} setNumber={setNumber} /> : <Connect numbers={info.numbers} />}</Panel>
          <Panel><Recents calls={hist?.calls || []} onPick={pick} /></Panel>
        </div>
      )}
      <PhoneLog />
      <History d={hist} onRefresh={load} />
    </div>
  );
}
