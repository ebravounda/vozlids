const LANG = {
  es: ["Español", null], en: ["Inglés", "🇬🇧"], pt: ["Portugués", "🇵🇹"], fr: ["Francés", "🇫🇷"],
  ca: ["Catalán", "cat"], it: ["Italiano", "🇮🇹"], de: ["Alemán", "🇩🇪"],
};
export const LEAD_LANGS = Object.entries(LANG).map(([k, [n]]) => [k, n]);

const CatFlag = () => (
  <span className="inline-block h-3 w-4 rounded-[2px] align-[-1px]" style={{ background: "repeating-linear-gradient(#fcdd09 0 2px, #da121a 2px 3.3px)" }} aria-hidden />
);

export function LangFlag({ lang, phone = "", withName = false, testid }) {
  const code = lang || "es";
  const [name, flag] = LANG[code] || LANG.es;
  const f = flag === "cat" ? <CatFlag /> : flag || (phone.startsWith("+56") ? "🇨🇱" : "🇪🇸");
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap" title={`Atendida en ${name.toLowerCase()}`} data-testid={testid}>
      <span className="text-base leading-none">{f}</span>{withName && <span>{name}</span>}
    </span>
  );
}

const LINE_FLAG = { "+34": "🇪🇸", "+56": "🇨🇱" };

export function LineFlag({ number, inbound, testid }) {
  if (!number) return <span className="text-xs text-slate-500" data-testid={testid}>—</span>;
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap" title={inbound ? `Llamó a tu línea ${number}` : `Salió desde tu línea ${number}`} data-testid={testid}>
      <span className="text-base leading-none">{LINE_FLAG[number.slice(0, 3)] || "🌐"}</span>
      <span className="font-mono text-xs text-slate-300">{number}</span>
    </span>
  );
}
