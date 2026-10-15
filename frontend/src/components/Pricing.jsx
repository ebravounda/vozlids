import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Check } from "lucide-react";
import { api } from "@/lib/api";
import { formatPrice, planOverage, planPrice } from "@/lib/currency";

const PlanCard = ({ p, currency, featured, number }) => (
  <div className={`flex flex-col rounded-xl border p-7 ${featured ? "border-slate-900 shadow-[0_20px_60px_-25px_rgba(15,23,42,0.35)]" : "border-slate-200"}`} data-testid={`pricing-plan-${p.id}`}>
    <h3 className="font-semibold text-slate-900">{p.name}</h3>
    <p className="mt-4 text-4xl font-bold tracking-tight text-slate-900" style={{ fontFamily: "Plus Jakarta Sans" }} data-testid={`pricing-plan-price-${p.id}`}>
      {formatPrice(planPrice(p, currency), currency)}<span className="text-base font-medium text-slate-500"> /mes</span>
    </p>
    <p className="mt-2 text-sm text-slate-600">{p.minutes.toLocaleString("es-ES")} minutos incluidos · minuto extra {formatPrice(planOverage(p, currency), currency, 2)}</p>
    <ul className="mt-6 flex-1 space-y-2 text-sm">
      <li className="flex items-center gap-2 font-semibold text-blue-700" data-testid={`pricing-plan-number-${p.id}`}><Check className="h-4 w-4 text-blue-600" />{number}</li>
      {(p.features || []).map((f) => <li key={f} className="flex items-center gap-2"><Check className="h-4 w-4 text-blue-600" />{f}</li>)}
    </ul>
    <Link to="/registro" data-testid={`pricing-plan-cta-${p.id}`} className={`mt-8 rounded-md px-5 py-2.5 text-center text-sm font-semibold ${featured ? "bg-slate-900 text-white hover:bg-slate-800" : "border border-slate-300 text-slate-800 hover:bg-slate-100"}`}>Empezar</Link>
  </div>
);

export function Pricing({ m }) {
  const currency = m.market === "CL" ? "CLP" : "EUR";
  const [plans, setPlans] = useState([]);
  useEffect(() => { api.get("/public/plans").then((r) => setPlans(r.data)).catch(() => {}); }, []);
  if (!plans.length) return null;
  return (
    <section id="precios" className="mx-auto max-w-6xl px-6 py-24" data-testid="pricing-section">
      <div className="flex flex-col justify-between gap-6 md:flex-row md:items-end">
        <div>
          <h2 className="text-3xl font-bold tracking-tight text-slate-900" style={{ fontFamily: "Plus Jakarta Sans" }}>Precios</h2>
          <p className="mt-3 text-slate-600">Planes mensuales de minutos, sin permanencia y con {m.t.num} incluido gratis. Precios {currency === "CLP" ? "en pesos chilenos, IVA no incluido" : "en euros, IVA no incluido"}.</p>
        </div>
      </div>
      <div className="mt-12 grid gap-6 md:grid-cols-3">
        {plans.map((p, i) => <PlanCard key={p.id} p={p} currency={currency} featured={i === 1} number={m.t.short} />)}
      </div>
    </section>
  );
}
