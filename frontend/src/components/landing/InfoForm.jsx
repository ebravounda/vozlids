import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, Loader2, PhoneCall } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { DEMO, byCode } from "@/lib/geo";

const Done = ({ name, calling, reset }) => (
  <div className="py-6 text-center" data-testid="info-form-success">
    <CheckCircle2 className="mx-auto h-12 w-12 text-blue-600" />
    <p className="mt-4 text-xl font-bold text-slate-900" style={{ fontFamily: "Plus Jakarta Sans" }}>¡Gracias, {name.split(" ")[0]}!</p>
    <p className="mt-2 text-sm text-slate-600">{calling ? "Nuestro agente de voz te está llamando ahora mismo. Contesta y escucha cómo atenderíamos a tus clientes." : "Hemos recibido tus datos. Te contactaremos muy pronto."}</p>
    <button onClick={reset} className="mt-5 text-sm font-semibold text-blue-700 hover:underline" data-testid="info-form-again">Enviar otra solicitud</button>
  </div>
);

export function InfoForm({ m, page = "/", id = "solicitar", title = "Recibe una llamada demo gratis", dark = false }) {
  const list = m.market !== "INT" ? DEMO.filter((d) => d.code === m.market) : DEMO;
  const initial = m.visitor && list.includes(m.visitor) ? m.visitor.code : list[0].code;
  const [f, setF] = useState({ name: "", phone: "", country: initial, consent: false });
  useEffect(() => { if (!f.phone) setF((x) => ({ ...x, country: initial })); }, [initial]); // eslint-disable-line react-hooks/exhaustive-deps
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [repeat, setRepeat] = useState(false);
  const [done, setDone] = useState(null);
  const c = byCode(f.country);
  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setRepeat(false);
    if (!f.consent) return setErr("Marca la casilla para que podamos llamarte.");
    setBusy(true);
    try {
      const phone = f.phone.trim().startsWith("+") ? f.phone : `${c.dial}${f.phone}`;
      const r = await api.post("/public/info-request", { ...f, phone, page });
      if (r.data.repeated) setRepeat(true);
      else setDone({ name: f.name, calling: r.data.calling });
    } catch (e2) { setErr(errMsg(e2)); } finally { setBusy(false); }
  };
  const tid = (s) => `${id}-${s}`;
  return (
    <div id={id} className={`scroll-mt-24 rounded-2xl border p-6 sm:p-7 ${dark ? "border-slate-700 bg-white" : "border-slate-200 bg-white shadow-[0_24px_70px_-24px_rgba(15,23,42,0.35)]"}`} data-testid={tid("form")}>
      {done ? <Done {...done} reset={() => { setDone(null); setF({ ...f, name: "", phone: "", consent: false }); }} /> : (
        <form onSubmit={submit} className="space-y-4">
          <div>
            <p className="text-xl font-bold text-slate-900" style={{ fontFamily: "Plus Jakarta Sans" }}>{title}</p>
            <p className="mt-1 text-sm text-slate-600">Déjanos tu nombre y teléfono: <b>nuestro agente con IA te llama en segundos</b> con una muestra breve.</p>
          </div>
          <label className="block text-sm font-medium text-slate-700">Nombre
            <input required minLength={2} maxLength={80} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Tu nombre" autoComplete="name"
              className="mt-1 h-12 w-full rounded-lg border border-slate-300 px-3 text-base text-slate-900 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-600/20" data-testid={tid("name")} />
          </label>
          <div>
            <span className="text-sm font-medium text-slate-700">País y teléfono</span>
            <div className="mt-1 flex gap-2">
              <label className="relative flex items-center rounded-lg border border-slate-300 focus-within:border-blue-600" data-testid={tid("country-flag")}>
                <select value={f.country} onChange={(e) => setF({ ...f, country: e.target.value })} disabled={list.length === 1} aria-label="País"
                  className="h-12 appearance-none bg-transparent py-0 pl-3 pr-6 text-sm font-semibold text-slate-800 outline-none disabled:opacity-100" data-testid={tid("country-select")}>
                  {list.map((d) => <option key={d.code} value={d.code}>{d.flag} {d.name}</option>)}
                </select>
                {list.length > 1 && <span className="pointer-events-none absolute right-2 text-xs text-slate-400">▾</span>}
              </label>
              <div className="flex flex-1 items-center rounded-lg border border-slate-300 focus-within:border-blue-600 focus-within:ring-2 focus-within:ring-blue-600/20">
                <span className="pl-3 font-mono text-sm text-slate-500" data-testid={tid("prefix")}>{c.dial}</span>
                <input required type="tel" inputMode="tel" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} placeholder={c.ph} autoComplete="tel-national"
                  className="h-12 w-full min-w-0 rounded-lg px-2 text-base text-slate-900 outline-none" data-testid={tid("phone")} />
              </div>
            </div>
          </div>
          <label className="flex items-start gap-2 text-xs leading-relaxed text-slate-600">
            <input type="checkbox" checked={f.consent} onChange={(e) => setF({ ...f, consent: e.target.checked })} className="mt-0.5 h-4 w-4 accent-blue-600" data-testid={tid("consent")} />
            <span>Acepto que VozLeads me llame a este número para informarme. La llamada puede grabarse. <Link to="/privacidad" className="underline">Privacidad</Link></span>
          </label>
          {err && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" data-testid={tid("error")}>{err}</p>}
          <button disabled={busy} className="flex h-12 w-full items-center justify-center gap-2 rounded-lg bg-blue-600 font-semibold text-white transition-colors hover:bg-blue-700 disabled:opacity-60" data-testid={tid("submit")}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <PhoneCall className="h-4 w-4" />} Quiero que me llamen ahora
          </button>
          {repeat
            ? <p className="text-center text-xs font-medium text-amber-700" data-testid={tid("repeat-note")}>Ya hemos llamado a este número hoy. Puedes volver a solicitar otra prueba en 24 horas.</p>
            : <p className="text-center text-xs text-slate-500">Muestra gratuita de 10-15 segundos · Sin compromiso</p>}
        </form>
      )}
    </div>
  );
}
