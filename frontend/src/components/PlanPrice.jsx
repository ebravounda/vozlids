import { formatPrice, planPrice } from "@/lib/currency";

export const promoPrice = (p, currency) => {
  if (!p.promo_active) return 0;
  const v = currency === "CLP" ? p.promo_price_clp : p.promo_price_eur;
  return v > 0 && v < planPrice(p, currency) ? v : 0;
};

const months = (n) => `${n} ${n === 1 ? "mes" : "meses"}`;

export function PlanPrice({ p, currency, className = "", dark = false }) {
  const normal = planPrice(p, currency);
  const promo = promoPrice(p, currency);
  const sub = dark ? "text-slate-500" : "text-slate-500";
  if (!promo) return <p className={className} data-testid={`plan-price-${p.id}`}>{formatPrice(normal, currency)}<span className={`text-sm font-medium ${sub}`}> /mes</span></p>;
  return (
    <div data-testid={`plan-promo-${p.id}`}>
      <p className={`text-sm font-semibold line-through decoration-2 ${dark ? "text-slate-500 decoration-rose-400" : "text-slate-400 decoration-rose-500"}`} data-testid={`plan-price-old-${p.id}`}>{formatPrice(normal, currency)}/mes</p>
      <p className={`${className} ${dark ? "!text-rose-300" : "!text-rose-600"}`} data-testid={`plan-price-${p.id}`}>{formatPrice(promo, currency)}<span className={`text-sm font-medium ${sub}`}> /mes</span></p>
      <p className={`mt-1 text-xs font-medium ${dark ? "text-rose-300/80" : "text-rose-600/90"}`} data-testid={`plan-promo-terms-${p.id}`}>Los primeros {months(p.promo_months)}, luego {formatPrice(normal, currency)}/mes</p>
    </div>
  );
}

export function PlanBadge({ p, currency }) {
  if (promoPrice(p, currency)) {
    const pct = Math.round(100 - (100 * promoPrice(p, currency)) / planPrice(p, currency));
    return <span className="absolute -top-3 left-6 rounded-full bg-rose-600 px-3 py-1 text-[11px] font-extrabold uppercase tracking-wider text-white shadow-md" data-testid={`plan-badge-promo-${p.id}`}>{p.promo_label || "PROMOCIÓN"} · −{pct}%</span>;
  }
  if (p.recommended) return <span className="absolute -top-3 left-6 rounded-full bg-blue-600 px-3 py-1 text-[11px] font-extrabold uppercase tracking-wider text-white shadow-md" data-testid={`plan-badge-recommended-${p.id}`}>Más elegido</span>;
  return null;
}

export function limitLines(p) {
  const l = p.limits || {};
  const out = [l.max_agents ? `${l.max_agents} ${l.max_agents === 1 ? "agente IA" : "agentes IA"}` : "Agentes IA ilimitados"];
  if (l.max_concurrent) out.push(`${l.max_concurrent} ${l.max_concurrent === 1 ? "llamada" : "llamadas"} a la vez`);
  [["outbound", "Llamadas salientes"], ["widget", "Botón para tu web"], ["agenda_pro", "Google Calendar y recordatorios"], ["premium_voices", "Voces ultra naturales HD"], ["ambience", "Ambiente de oficina"], ["api", "API y webhooks"]]
    .forEach(([k, t]) => { if (l[k] !== false) out.push(t); });
  if (l.recording_days) out.push(`Grabaciones guardadas ${l.recording_days} días`);
  return out;
}
