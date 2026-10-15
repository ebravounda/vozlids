import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { CalendarCheck, CalendarX, CheckCircle2, Loader2 } from "lucide-react";
import { Logo } from "@/components/Common";
import { api, errMsg } from "@/lib/api";

export default function PublicAppointment() {
  const { token } = useParams();
  const [a, setA] = useState(null);
  const [state, setState] = useState("");
  const [busy, setBusy] = useState("");
  useEffect(() => { api.get(`/public/appointment/${token}`).then((r) => setA(r.data)).catch((e) => setState(errMsg(e, "Cita no encontrada o ya anulada"))); }, [token]);
  const act = async (k) => {
    if (k === "cancel" && !window.confirm("¿Seguro que quieres anular la cita?")) return;
    setBusy(k);
    try { await api.post(`/public/appointment/${token}/${k}`); setState(k); } catch (e) { setState(errMsg(e)); } finally { setBusy(""); }
  };
  const msg = { confirm: "¡Gracias! Tu asistencia está confirmada.", cancel: "Tu cita se ha anulado. Gracias por avisar." }[state];
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#F8FAFC] p-6" data-testid="public-appointment-page">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-[0_30px_80px_-40px_rgba(15,23,42,0.4)]">
        <Logo className="mx-auto" />
        {!a && !state && <Loader2 className="mx-auto mt-8 h-6 w-6 animate-spin text-slate-400" />}
        {state && !msg && <p className="mt-8 text-slate-600" data-testid="public-appt-error">{state}</p>}
        {msg && <div className="mt-8" data-testid="public-appt-done"><CheckCircle2 className="mx-auto h-12 w-12 text-blue-600" /><p className="mt-3 font-semibold text-slate-900">{msg}</p></div>}
        {a && !state && (
          <div className="mt-8">
            <p className="text-sm text-slate-500">Hola {a.name}, tienes una cita con</p>
            <p className="mt-1 text-xl font-bold text-slate-900">{a.business}</p>
            <p className="mt-3 rounded-xl bg-blue-50 px-4 py-3 font-semibold text-blue-800" data-testid="public-appt-when">{a.when}</p>
            {a.confirmed && <p className="mt-3 text-sm text-emerald-700">Ya la habías confirmado.</p>}
            <div className="mt-6 grid gap-3">
              <button onClick={() => act("confirm")} disabled={!!busy} className="flex h-12 items-center justify-center gap-2 rounded-lg bg-blue-600 font-semibold text-white hover:bg-blue-700" data-testid="public-appt-confirm">{busy === "confirm" ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarCheck className="h-4 w-4" />}Confirmo que asistiré</button>
              <button onClick={() => act("cancel")} disabled={!!busy} className="flex h-12 items-center justify-center gap-2 rounded-lg border border-slate-300 font-semibold text-slate-700 hover:bg-slate-50" data-testid="public-appt-cancel">{busy === "cancel" ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarX className="h-4 w-4" />}No puedo ir, anular cita</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
