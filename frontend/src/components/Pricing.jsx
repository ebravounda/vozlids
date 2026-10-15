import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Check } from "lucide-react";
import { api } from "@/lib/api";
import { formatPrice, planOverage } from "@/lib/currency";
import { limitLines, PlanBadge, PlanPrice, promoPrice } from "@/components/PlanPrice";

const PlanCard = ({ p, currency, featured, number }) => (
  <div className={`relative flex flex-col rounded-xl border bg-white p-7 ${promoPrice(p, currency) ? "border-rose-500 ring-1 ring-rose-500 shadow-[0_20px_60px_-25px_rgba(225,29,72,0.35)]" : featured ? "border-blue-600 ring-1 ring-blue-600 shadow-[0_20px_60px_-25px_rgba(37,99,235,0.4)]" : "border-slate-200"}`} data-testid={`pricing-plan-${p.id}`}>
    <PlanBadge p={p} currency={currency} />
    <h3 className="font-semibold text-slate-900">{p.name}</h3>
    <div className="mt-4" data-testid={`pricing-plan-price-${p.id}`}>
      <PlanPrice p={p} currency={currency} className="text-4xl font-bold tracking-tight text-slate-900" />
    </div>
    <p className="mt-2 text-sm text-slate-600">{p.minutes.toLocaleString("es-ES")} minutos incluidos · minuto extra {formatPrice(planOverage(p, currency), currency, 2)}</p>
    <ul className="mt-6 flex-1 space-y-2 text-sm">
      <li className="flex items-center gap-2 font-semibold text-blue-700" data-testid={`pricing-plan-number-${p.id}`}><Check className="h-4 w-4 text-blue-600" />{number}</li>
      {[...limitLines(p), ...(p.features || [])].map((f) => <li key={f} className="flex items-center gap-2"><Check className="h-4 w-4 text-blue-600" />{f}</li>)}
    </ul>
    <Link to={`/registro?plan=${p.id}`} data-testid={`pricing-plan-cta-${p.id}`} className={`mt-8 rounded-md px-5 py-2.5 text-center text-sm font-semibold ${promoPrice(p, currency) ? "bg-rose-600 text-white hover:bg-rose-700" : featured ? "bg-blue-600 text-white hover:bg-blue-700" : "border border-slate-300 text-slate-800 hover:bg-slate-100"}`}>{promoPrice(p, currency) ? "Aprovechar promoción" : "Empezar"}</Link>
  </div>
);

export function Pricing({ m }) {
  const currency = m.market === "CL" ? "CLP" : "EUR";
  const [plans, setPlans] = useState([]);
  useEffect(() => { api.get("/public/plans").then((r) => setPlans(r.data)).catch(() => {}); }, []);
  if (!plans.length) return null;
  return (
    <section id="precios" className={`scroll-mt-20 mx-auto px-6 py-24 ${plans.length >= 5 ? "max-w-7xl" : "max-w-6xl"}`} data-testid="pricing-section">
      <div className="flex flex-col justify-between gap-6 md:flex-row md:items-end">
        <div>
          <h2 className="text-3xl font-bold tracking-tight text-slate-900" style={{ fontFamily: "Plus Jakarta Sans" }}>Precios</h2>
          <p className="mt-3 text-slate-600">Planes mensuales de minutos, sin permanencia y con {m.t.num} incluido gratis. Precios {currency === "CLP" ? "en pesos chilenos, IVA no incluido" : "en euros, IVA no incluido"}.</p>
        </div>
      </div>
      <div className={`mt-12 grid gap-6 md:grid-cols-3 ${plans.length >= 5 ? "xl:grid-cols-5" : plans.length === 4 ? "lg:grid-cols-4" : ""}`}>
        {plans.map((p, i) => <PlanCard key={p.id} p={p} currency={currency} featured={plans.some((x) => x.recommended) ? p.recommended : i === 1} number={m.t.short} />)}
      </div>
    </section>
  );
}
