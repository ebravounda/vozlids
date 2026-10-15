import { createContext, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";

export const DEMO = [
  ["ES", "España", "+34", "🇪🇸", "612 345 678"], ["CL", "Chile", "+56", "🇨🇱", "9 1234 5678"],
  ["AR", "Argentina", "+54", "🇦🇷", "9 11 2345 6789"], ["BO", "Bolivia", "+591", "🇧🇴", "7123 4567"],
  ["CO", "Colombia", "+57", "🇨🇴", "301 234 5678"], ["CR", "Costa Rica", "+506", "🇨🇷", "8312 3456"],
  ["DO", "República Dominicana", "+1", "🇩🇴", "809 234 5678"], ["EC", "Ecuador", "+593", "🇪🇨", "99 123 4567"],
  ["SV", "El Salvador", "+503", "🇸🇻", "7012 3456"], ["GT", "Guatemala", "+502", "🇬🇹", "5123 4567"],
  ["HN", "Honduras", "+504", "🇭🇳", "9123 4567"], ["MX", "México", "+52", "🇲🇽", "55 1234 5678"],
  ["NI", "Nicaragua", "+505", "🇳🇮", "8123 4567"], ["PA", "Panamá", "+507", "🇵🇦", "6123 4567"],
  ["PY", "Paraguay", "+595", "🇵🇾", "961 234 567"], ["PE", "Perú", "+51", "🇵🇪", "912 345 678"],
  ["UY", "Uruguay", "+598", "🇺🇾", "94 123 456"], ["VE", "Venezuela", "+58", "🇻🇪", "412 123 4567"],
].map(([code, name, dial, flag, ph]) => ({ code, name, dial, flag, ph }));
export const byCode = (c) => DEMO.find((d) => d.code === c);

const TZ = {
  "Europe/Madrid": "ES", "Atlantic/Canary": "ES", "Africa/Ceuta": "ES", "America/Santiago": "CL", "America/Punta_Arenas": "CL",
  "Pacific/Easter": "CL", "America/Argentina/Buenos_Aires": "AR", "America/Buenos_Aires": "AR", "America/Cordoba": "AR",
  "America/La_Paz": "BO", "America/Bogota": "CO", "America/Costa_Rica": "CR", "America/Santo_Domingo": "DO",
  "America/Guayaquil": "EC", "America/El_Salvador": "SV", "America/Guatemala": "GT", "America/Tegucigalpa": "HN",
  "America/Mexico_City": "MX", "America/Monterrey": "MX", "America/Cancun": "MX", "America/Tijuana": "MX", "America/Merida": "MX",
  "America/Chihuahua": "MX", "America/Hermosillo": "MX", "America/Mazatlan": "MX", "America/Managua": "NI", "America/Panama": "PA",
  "America/Asuncion": "PY", "America/Lima": "PE", "America/Montevideo": "UY", "America/Caracas": "VE",
};
const tzCountry = () => {
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
  return TZ[tz] || (tz.startsWith("America/Argentina") ? "AR" : "");
};

export const TXT = {
  ES: { num: "número de España (+34)", short: "Número +34 de España gratis", where: "en España", dial: "+34 6••" },
  CL: { num: "número de Chile (+56)", short: "Número +56 de Chile gratis", where: "en Chile", dial: "+56 9••" },
  INT: { num: "número de teléfono", short: "Número de teléfono incluido", where: "en tu país", line: "Agente de voz en español", dial: "+52 55•" },
};

const GeoCtx = createContext({ country: "", market: "INT", ready: false });
let cache = null;

export function GeoProvider({ children }) {
  const [geo, setGeo] = useState(cache || { country: "", ready: false });
  useEffect(() => {
    if (cache) return;
    api.get("/public/geo").then((r) => r.data.country).catch(() => "").then((c) => {
      cache = { country: (c && c !== "XX" ? c : tzCountry()) || "", ready: true };
      setGeo(cache);
    });
  }, []);
  return <GeoCtx.Provider value={geo}>{children}</GeoCtx.Provider>;
}

export function useMarket(pageCountry) {
  const geo = useContext(GeoCtx);
  const fixed = pageCountry === "ES" || pageCountry === "CL";
  const local = !fixed && byCode(pageCountry);
  const market = fixed ? pageCountry : local ? "INT" : geo.country === "ES" || geo.country === "CL" ? geo.country : "INT";
  const visitor = byCode(fixed ? pageCountry : local ? pageCountry : geo.country) || null;
  return { market, fixed, visitor, country: geo.country, ready: fixed || geo.ready, t: TXT[market] };
}
