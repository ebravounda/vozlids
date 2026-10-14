const KEY = "vl_currency";
const CL_ZONES = ["America/Santiago", "America/Punta_Arenas", "Pacific/Easter", "Chile/Continental", "Chile/EasterIsland"];

export function detectCurrency() {
  const saved = localStorage.getItem(KEY);
  if (saved === "EUR" || saved === "CLP") return saved;
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
  const langs = navigator.languages || [navigator.language || ""];
  if (CL_ZONES.includes(tz) || langs.some((l) => /-CL$/i.test(l))) return "CLP";
  return "EUR";
}

export const saveCurrency = (c) => localStorage.setItem(KEY, c);

export function formatPrice(value, currency, decimals = 0) {
  return new Intl.NumberFormat(currency === "CLP" ? "es-CL" : "es-ES", {
    style: "currency", currency, minimumFractionDigits: currency === "CLP" ? 0 : decimals, maximumFractionDigits: currency === "CLP" ? 0 : 2,
  }).format(value || 0);
}

export const planPrice = (p, currency) => (currency === "CLP" ? p.price_clp : p.price_eur);
export const planOverage = (p, currency) => (currency === "CLP" ? p.overage_clp : p.overage_eur);
