import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Check, Loader2, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/context/AuthContext";
import { api, errMsg } from "@/lib/api";
import { formatPrice, planPrice } from "@/lib/currency";

const DOCS = { ES: ["DNI", "NIE", "Pasaporte"], CL: ["RUT", "Pasaporte"] };
const REGION = { ES: "Provincia", CL: "Región" };
const inputCls = "h-11 rounded-lg border-slate-200 bg-white shadow-sm focus-visible:ring-blue-600/30";

const F = ({ id, label, className = "", ...p }) => (
  <div className={`space-y-1.5 ${className}`}>
    <Label htmlFor={id} className="text-sm text-slate-700">{label}</Label>
    <Input id={id} data-testid={`signup-${id}-input`} className={inputCls} {...p} />
  </div>
);

function PlanPicker({ plans, value, onChange, currency }) {
  return (
    <div className="grid gap-2 sm:grid-cols-3" data-testid="signup-plan-picker">
      {plans.map((p) => (
        <button key={p.id} type="button" onClick={() => onChange(p.id)} data-testid={`signup-plan-${p.id}`}
          className={`rounded-xl border p-3 text-left transition-colors ${value === p.id ? "border-blue-600 bg-blue-50 ring-1 ring-blue-600" : "border-slate-200 hover:border-slate-300"}`}>
          <p className="flex items-center justify-between text-sm font-semibold text-slate-900">{p.name}{value === p.id && <Check className="h-4 w-4 text-blue-600" />}</p>
          <p className="mt-1 text-lg font-bold text-slate-900">{formatPrice(planPrice(p, currency), currency)}<span className="text-xs font-normal text-slate-500">/mes</span></p>
          <p className="text-xs text-slate-500">{p.minutes.toLocaleString("es-ES")} min</p>
        </button>
      ))}
    </div>
  );
}

export function SignupForm() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [plans, setPlans] = useState([]);
  const [f, setF] = useState({ first_name: "", last_name: "", email: "", password: "", country: "ES", business_name: "", website: "",
    doc_type: "DNI", doc_number: "", line: "", city: "", postal_code: "", region: "", plan_id: params.get("plan") || "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  useEffect(() => { api.get("/public/plans").then((r) => { setPlans(r.data); setF((x) => ({ ...x, plan_id: x.plan_id || r.data[1]?.id || r.data[0]?.id || "" })); }); }, []);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const currency = f.country === "CL" ? "CLP" : "EUR";
  const setCountry = (c) => setF({ ...f, country: c, doc_type: DOCS[c][0] });

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (!f.plan_id) return setError("Elige un plan");
    setLoading(true);
    try {
      const { line, city, postal_code, region, plan_id, ...rest } = f;
      await register({ ...rest, billing_address: { line, city, postal_code, region } });
    } catch (err) { setError(errMsg(err)); setLoading(false); return; }
    try {
      const r = await api.post("/billing/checkout", { plan_id: f.plan_id, origin_url: window.location.origin, signup: true });
      window.location.href = r.data.checkout_url || r.data.url;
    } catch (err) {
      toast.error(errMsg(err));
      navigate("/app/plan");
    }
  };

  return (
    <form onSubmit={submit} className="mt-8 space-y-5" data-testid="signup-form">
      <div className="space-y-2">
        <Label className="text-sm text-slate-700">País del negocio</Label>
        <div className="grid grid-cols-2 gap-2">
          {[["ES", "🇪🇸 España"], ["CL", "🇨🇱 Chile"]].map(([c, n]) => (
            <button key={c} type="button" onClick={() => setCountry(c)} data-testid={`auth-country-${c}`}
              className={`h-11 rounded-lg border text-sm font-semibold transition-colors ${f.country === c ? "border-blue-600 bg-blue-50 text-blue-700" : "border-slate-200 text-slate-600 hover:border-slate-300"}`}>{n}</button>
          ))}
        </div>
      </div>
      <div className="space-y-2"><Label className="text-sm text-slate-700">Plan</Label><PlanPicker plans={plans} value={f.plan_id} onChange={(v) => setF({ ...f, plan_id: v })} currency={currency} /></div>
      <fieldset className="grid gap-3 sm:grid-cols-2">
        <F id="first-name" label="Nombre" required value={f.first_name} onChange={set("first_name")} autoComplete="given-name" />
        <F id="last-name" label="Apellidos" required value={f.last_name} onChange={set("last_name")} autoComplete="family-name" />
        <F id="email" label="Email" type="email" required value={f.email} onChange={set("email")} autoComplete="email" />
        <F id="password" label="Contraseña" type="password" required minLength={8} value={f.password} onChange={set("password")} placeholder="Mínimo 8 caracteres" autoComplete="new-password" />
      </fieldset>
      <fieldset className="grid gap-3 sm:grid-cols-[150px_1fr]">
        <div className="space-y-1.5">
          <Label className="text-sm text-slate-700">Documento</Label>
          <select value={f.doc_type} onChange={set("doc_type")} className={`${inputCls} w-full border px-3 text-sm`} data-testid="signup-doc-type-select">
            {DOCS[f.country].map((d) => <option key={d}>{d}</option>)}
          </select>
        </div>
        <F id="doc-number" label="Número de documento" required value={f.doc_number} onChange={set("doc_number")} placeholder={f.doc_type === "RUT" ? "12.345.678-5" : f.doc_type === "NIE" ? "X1234567L" : f.doc_type === "DNI" ? "12345678Z" : ""} />
      </fieldset>
      <fieldset className="grid gap-3 sm:grid-cols-2">
        <F id="business" label="Nombre del negocio" required value={f.business_name} onChange={set("business_name")} />
        <F id="website" label="Página web (opcional)" value={f.website} onChange={set("website")} placeholder="www.tunegocio.com" />
      </fieldset>
      <fieldset className="grid gap-3 sm:grid-cols-2">
        <legend className="mb-2 text-sm font-semibold text-slate-900">Dirección de facturación</legend>
        <F id="address" label="Dirección" required className="sm:col-span-2" value={f.line} onChange={set("line")} autoComplete="street-address" />
        <F id="city" label={f.country === "CL" ? "Comuna / ciudad" : "Ciudad"} required value={f.city} onChange={set("city")} />
        <F id="postal-code" label="Código postal" required={f.country === "ES"} value={f.postal_code} onChange={set("postal_code")} />
        <F id="region" label={REGION[f.country]} className="sm:col-span-2" value={f.region} onChange={set("region")} />
      </fieldset>
      {error && <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700" data-testid="auth-error">{error}</p>}
      <Button type="submit" disabled={loading} className="h-12 w-full rounded-lg text-base font-semibold" data-testid="auth-submit-button">
        {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Lock className="mr-2 h-4 w-4" />}Continuar al pago seguro
      </Button>
      <p className="text-center text-xs text-slate-500">Después introduces tu tarjeta de débito o crédito. Se cobra la primera cuota para activar la suscripción · Sin permanencia</p>
    </form>
  );
}
