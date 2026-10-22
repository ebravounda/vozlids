import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Headphones, Loader2, Mic, Phone, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";

const BASE = "https://my.zadarma.com/webphoneWebRTCWidget/v9/js/";
const loadScript = (src) => new Promise((ok, fail) => {
  if (document.querySelector(`script[src="${src}"]`)) return ok();
  const s = document.createElement("script");
  s.src = src; s.onload = ok; s.onerror = () => fail(new Error("No se pudo cargar el teléfono"));
  document.body.appendChild(s);
});
const mmss = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
const STATUS = { answered: "Contestada", busy: "Ocupado", "no answer": "Sin respuesta", cancel: "Cancelada", failed: "Fallida" };

function PhoneCard({ numbers }) {
  const [number, setNumber] = useState(numbers[0] || "");
  const [state, setState] = useState(window.__vozDialer ? "ready" : "idle");
  const start = async () => {
    setState("loading");
    try {
      await navigator.mediaDevices?.getUserMedia?.({ audio: true }).then((st) => st.getTracks().forEach((t) => t.stop()));
      const { data } = await api.post("/dialer/session", { number });
      await loadScript(`${BASE}loader-phone-lib.js?sub_v=1`);
      await loadScript(`${BASE}loader-phone-fn.js?sub_v=1`);
      window.zadarmaWidgetFn(data.key, data.sip, "rounded", "es", true, "{right:'24px',bottom:'24px'}");
      window.__vozDialer = data.number;
      setState("ready");
      toast.success("Teléfono listo: usa el teclado de abajo a la derecha");
    } catch (e) {
      setState("idle");
      toast.error(e?.name === "NotAllowedError" ? "Permite el micrófono en el navegador para poder llamar" : errMsg(e));
    }
  };
  if (!numbers.length) return <Panel data-testid="dialer-no-number"><p className="text-sm text-slate-400">Aún no tienes un número activo. Pídelo en «Mi número» para poder llamar desde aquí.</p></Panel>;
  return (
    <Panel data-testid="dialer-phone-card">
      <div className="flex flex-wrap items-end gap-4">
        <div className="min-w-[220px] flex-1">
          <p className="mb-2 text-xs uppercase tracking-widest text-slate-500">Llamar desde</p>
          <Select value={number} onValueChange={setNumber} disabled={state === "ready"}>
            <SelectTrigger className="bg-slate-950/60 font-mono" data-testid="dialer-number-select"><SelectValue /></SelectTrigger>
            <SelectContent>{numbers.map((n) => <SelectItem key={n} value={n} className="font-mono">{n}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        {state === "ready"
          ? <p className="flex items-center gap-2 text-sm text-emerald-300" data-testid="dialer-ready"><Phone className="h-4 w-4" /> Teléfono activo con {window.__vozDialer}</p>
          : <Button onClick={start} disabled={state === "loading"} className="rounded-full bg-emerald-500 text-slate-950 hover:bg-emerald-400" data-testid="dialer-start-button">
              {state === "loading" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Phone className="mr-2 h-4 w-4" />} Activar teléfono
            </Button>}
      </div>
      <div className="mt-5 grid gap-3 text-xs text-slate-400 sm:grid-cols-2">
        <p className="flex items-start gap-2"><Mic className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" /> El navegador te pedirá permiso para usar el micrófono.</p>
        <p className="flex items-start gap-2"><Headphones className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" /> Usa auriculares para que no haya eco. Tus clientes verán tu número.</p>
      </div>
    </Panel>
  );
}

function History() {
  const [d, setD] = useState(null);
  const load = () => api.get("/dialer/history").then((r) => { setD(r.data); if (r.data.error) toast.error(r.data.error); }).catch((e) => toast.error(errMsg(e)));
  useEffect(() => { load(); }, []);
  const admin = d?.calls?.some((c) => c.cost !== undefined);
  return (
    <Panel className="overflow-x-auto p-0" data-testid="dialer-history">
      <div className="flex items-center justify-between p-5 pb-2">
        <div>
          <h3 className="text-lg font-semibold text-white">Tus llamadas de este mes</h3>
          <p className="text-xs text-slate-500" data-testid="dialer-history-minutes">{d ? `${d.minutes} min en ${d.calls.length} llamadas` : "Cargando…"}</p>
        </div>
        <Button size="sm" variant="ghost" onClick={load} data-testid="dialer-history-refresh"><RefreshCw className="h-4 w-4" /></Button>
      </div>
      {d && (d.calls.length ? (
        <table className="w-full min-w-[560px] text-sm">
          <thead className="text-left text-xs uppercase tracking-wider text-slate-500"><tr>{["Fecha", "Número", "Estado", "Duración", ...(admin ? ["Coste Zadarma"] : [])].map((h) => <th key={h} className="p-3 font-medium">{h}</th>)}</tr></thead>
          <tbody>{d.calls.map((c) => (
            <tr key={c.id} className="border-t border-slate-800" data-testid={`dialer-call-${c.id}`}>
              <td className="p-3 text-xs text-slate-400">{c.start}</td>
              <td className="p-3"><p className="font-mono text-white">{c.to}</p><p className="text-[11px] text-slate-500">{c.destination}</p></td>
              <td className="p-3 text-xs">{STATUS[c.status] || c.status}</td>
              <td className="p-3 font-mono text-xs">{mmss(c.seconds)}</td>
              {admin && <td className="p-3 font-mono text-xs">{c.cost} {c.currency}</td>}
            </tr>))}</tbody>
        </table>
      ) : <p className="p-5 pt-2 text-sm text-slate-500" data-testid="dialer-history-empty">Aún no has hecho llamadas desde el panel este mes.</p>)}
    </Panel>
  );
}

export default function Dialer() {
  const [info, setInfo] = useState(null);
  useEffect(() => { api.get("/dialer").then((r) => setInfo(r.data)).catch(() => setInfo({ numbers: [] })); }, []);
  return (
    <div className="space-y-6" data-testid="dialer-page">
      <div>
        <h1 className="font-display text-3xl font-semibold text-white">Teléfono</h1>
        <p className="mt-1 text-sm text-slate-400">Llama tú mismo a tus clientes desde el navegador, con tu número de empresa. Los minutos se descuentan de tu plan.</p>
      </div>
      {info && <PhoneCard numbers={info.numbers} />}
      <History />
    </div>
  );
}
