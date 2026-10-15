import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { CheckCircle2, Loader2, PhoneCall } from "lucide-react";
import { api, errMsg } from "@/lib/api";

export default function PublicForm() {
  const { agentId } = useParams();
  const q = new URLSearchParams(window.location.search);
  const embed = q.get("embed") === "1";
  const color = /^#[0-9a-fA-F]{6}$/.test(q.get("color") || "") ? q.get("color") : "";
  const [agent, setAgent] = useState(null);
  const [missing, setMissing] = useState(false);
  const [form, setForm] = useState({ name: "", phone: "", email: "", consent: false });
  const [state, setState] = useState("idle");
  const [error, setError] = useState("");

  useEffect(() => {
    api.get(`/public/agents/${agentId}`).then((r) => setAgent(r.data)).catch(() => setMissing(true));
  }, [agentId]);

  const set = (k) => (e) => setForm({ ...form, [k]: k === "consent" ? e.target.checked : e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setState("sending");
    try {
      await api.post(`/public/agents/${agentId}/leads`, form);
      setState("done");
    } catch (err) {
      setError(errMsg(err));
      setState("idle");
    }
  };

  const input = "w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-slate-900 outline-none transition-colors focus:border-emerald-600 focus:ring-2 focus:ring-emerald-600/20";

  if (missing || (agent && !agent.active))
    return <div className="grid min-h-screen place-items-center bg-white p-6 text-slate-600" data-testid="public-form-unavailable">Este formulario no está disponible.</div>;

  return (
    <div className={embed ? "bg-white p-5" : "flex min-h-screen items-center justify-center bg-slate-50 p-4"} style={{ fontFamily: "'Plus Jakarta Sans', sans-serif" }}>
      <div className={embed ? "w-full" : "w-full max-w-md rounded-3xl border border-slate-200 bg-white p-7 shadow-sm"} data-testid="public-form-card">
        {state === "done" ? (
          <div className="py-8 text-center" data-testid="public-form-success">
            <CheckCircle2 className="mx-auto h-12 w-12 text-emerald-600" />
            <h2 className="mt-4 text-2xl font-bold text-slate-900" style={{ fontFamily: "Outfit" }}>¡Gracias, {form.name.split(" ")[0]}!</h2>
            <p className="mt-2 text-slate-600">Te llamamos en unos segundos al {form.phone}. Ten el móvil a mano.</p>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4">
            <div className="flex items-center gap-3">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-emerald-600 text-white" style={color ? { background: color } : undefined}><PhoneCall className="h-5 w-5" /></span>
              <div>
                <h2 className="text-xl font-bold text-slate-900" style={{ fontFamily: "Outfit" }}>Te llamamos ahora</h2>
                <p className="text-sm text-slate-500" data-testid="public-form-business">{agent?.business_name || "…"}</p>
              </div>
            </div>
            <input required className={input} placeholder="Nombre y apellidos" value={form.name} onChange={set("name")} data-testid="public-form-name-input" />
            <input required className={input} type="tel" placeholder={`Teléfono (${agent?.phone_example || "+34 600 000 000"})`} value={form.phone} onChange={set("phone")} data-testid="public-form-phone-input" />
            <input className={input} type="email" placeholder="Email (opcional)" value={form.email} onChange={set("email")} data-testid="public-form-email-input" />
            <label className="flex gap-3 text-xs leading-relaxed text-slate-600">
              <input type="checkbox" required checked={form.consent} onChange={set("consent")} className="mt-0.5 h-4 w-4 accent-emerald-600" data-testid="public-form-consent-checkbox" />
              <span>Acepto que {agent?.business_name || "la empresa"} me llame ahora a este número. La llamada la realiza un asistente virtual con IA y se graba para mejorar el servicio. Puedo pedir que no me vuelvan a llamar en cualquier momento.</span>
            </label>
            {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" data-testid="public-form-error">{error}</p>}
            <button type="submit" disabled={state === "sending"} data-testid="public-form-submit-button"
              style={color ? { background: color } : undefined}
              className="flex w-full items-center justify-center gap-2 rounded-full bg-emerald-600 py-3.5 font-semibold text-white transition-colors hover:bg-emerald-700 disabled:opacity-60">
              {state === "sending" && <Loader2 className="h-4 w-4 animate-spin" />} Quiero que me llamen
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
