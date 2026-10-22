import { useState } from "react";
import { toast } from "sonner";
import { Globe, Loader2, Plus, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api, errMsg } from "@/lib/api";

export function WebScan({ agent, update }) {
  const [url, setUrl] = useState(agent.website || "");
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const scan = async () => {
    setBusy(true);
    try { setRes((await api.post("/agents/scan-website", { url }, { timeout: 120000 })).data); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const add = () => {
    const cur = (agent.product || "").trim();
    const next = `${cur}${cur ? "\n\n" : ""}— Información de la web (${url}) —\n${res.summary.trim()}`;
    if (next.length > 8000) return toast.error("No cabe: la información del negocio superaría 8000 caracteres. Acorta el resumen o lo que ya tienes.");
    update({ product: next }); setRes(null); toast.success("Añadido a la información del negocio. Recuerda guardar el agente.");
  };
  return (
    <div className="space-y-3 rounded-xl border border-blue-200 bg-blue-50/60 p-4" data-testid="webscan-panel">
      <p className="flex items-center gap-2 text-sm font-semibold text-slate-900"><Sparkles className="h-4 w-4 text-blue-600" />Leer mi web con IA</p>
      <p className="text-xs text-slate-600">Pon la web de tu negocio: la IA la lee y te prepara un resumen (servicios, precios, horarios, dirección…). Lo revisas y lo añades a lo que ya escribiste. Máximo 2 lecturas al día.</p>
      <div className="flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1"><Globe className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://tunegocio.com" className="bg-white pl-9" data-testid="webscan-url-input" /></div>
        <Button onClick={scan} disabled={busy || url.trim().length < 4} className="rounded-full" data-testid="webscan-scan-button">{busy ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Leyendo la web…</> : "Leer la web"}</Button>
      </div>
      {res && <div className="space-y-2" data-testid="webscan-result">
        <p className="text-xs text-slate-500">Leídas {res.pages} página(s) · te quedan {res.remaining} lectura(s) hoy. Revisa y corrige el resumen antes de añadirlo:</p>
        <Textarea rows={10} value={res.summary} onChange={(e) => setRes({ ...res, summary: e.target.value })} className="bg-white text-sm" data-testid="webscan-summary-input" />
        <div className="flex gap-2">
          <Button onClick={add} className="rounded-full" data-testid="webscan-add-button"><Plus className="mr-1.5 h-4 w-4" />Añadir a la información del negocio</Button>
          <Button variant="ghost" onClick={() => setRes(null)} className="rounded-full" data-testid="webscan-discard-button">Descartar</Button>
        </div>
      </div>}
    </div>
  );
}
