import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Globe2, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";

const names = new Intl.DisplayNames(["es"], { type: "region" });
const nameOf = (c) => { try { return names.of(c) || c; } catch { return c; } };
const flag = (c) => String.fromCodePoint(...[...c].map((ch) => 127397 + ch.charCodeAt(0)));
const MARKETS = ["ES", "CL"];

export function CountryBlock() {
  const [d, setD] = useState(null);
  const [q, setQ] = useState("");
  useEffect(() => { api.get("/admin/country-block").then((r) => setD(r.data)); }, []);
  const save = async (countries, msg) => {
    try { const r = await api.put("/admin/country-block", { countries }); setD({ ...d, ...r.data }); toast.success(msg); }
    catch (e) { toast.error(errMsg(e)); }
  };
  const options = useMemo(() => {
    if (!d || q.trim().length < 2) return [];
    const t = q.trim().toLowerCase();
    return d.all.filter((c) => !MARKETS.includes(c) && !d.countries.includes(c) && (nameOf(c).toLowerCase().includes(t) || c.toLowerCase() === t)).slice(0, 8);
  }, [d, q]);
  if (!d) return null;
  return (
    <Panel className="space-y-4" data-testid="country-block-panel">
      <div>
        <h3 className="flex items-center gap-2 text-lg font-semibold text-white"><Globe2 className="h-5 w-5 text-rose-300" />Bloqueo por país</h3>
        <p className="text-xs text-slate-500">Rechaza demos, formularios y el botón web cuando la conexión (IP) o el prefijo del teléfono son de un país bloqueado. España y Chile no se pueden bloquear.</p>
      </div>
      <div className="relative">
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Busca un país para bloquearlo (ej. Nigeria)" className="bg-slate-950/60" data-testid="country-block-search" />
        {options.length > 0 && (
          <div className="absolute z-20 mt-1 w-full overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg" data-testid="country-block-options">
            {options.map((c) => (
              <button key={c} onClick={() => { setQ(""); save([...d.countries, c], `${nameOf(c)} bloqueado`); }} className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-slate-800 hover:bg-slate-50" data-testid={`country-option-${c}`}>
                <span>{flag(c)}</span>{nameOf(c)}<span className="ml-auto font-mono text-xs text-slate-400">{c}</span>
              </button>
            ))}
          </div>
        )}
      </div>
      {d.countries.length ? (
        <div className="flex flex-wrap gap-2" data-testid="country-block-list">
          {d.countries.map((c) => (
            <span key={c} className="inline-flex items-center gap-1.5 rounded-full border border-rose-300 bg-rose-50 px-3 py-1 text-sm text-rose-800" data-testid={`country-chip-${c}`}>
              {flag(c)} {nameOf(c)}
              <button onClick={() => save(d.countries.filter((x) => x !== c), `${nameOf(c)} desbloqueado`)} className="text-rose-400 hover:text-rose-700" title="Desbloquear" data-testid={`country-unblock-${c}`}><X className="h-3.5 w-3.5" /></button>
            </span>
          ))}
        </div>
      ) : <p className="text-sm text-slate-500" data-testid="country-block-empty">Ningún país bloqueado.</p>}
      <p className="text-xs text-slate-500" data-testid="country-block-total">{d.blocked_total} {d.blocked_total === 1 ? "solicitud rechazada" : "solicitudes rechazadas"} por país hasta ahora.</p>
    </Panel>
  );
}
