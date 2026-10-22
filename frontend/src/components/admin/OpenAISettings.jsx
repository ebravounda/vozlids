import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Globe, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";

export function OpenAISettings() {
  const [s, setS] = useState(null);
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () => api.get("/admin/openai").then((r) => setS(r.data));
  useEffect(() => { load(); }, []);
  const save = async () => {
    setBusy(true);
    try { await api.put("/admin/openai", { api_key: key.trim() }); toast.success("OpenAI conectado: tus clientes ya pueden leer su web con IA"); setKey(""); load(); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const off = async () => { await api.delete("/admin/openai"); load(); };
  if (!s) return null;
  return (
    <Panel className="space-y-4" data-testid="openai-settings-panel">
      <div className="flex items-center gap-2"><Globe className="h-5 w-5 text-blue-500" /><h3 className="text-lg font-semibold text-white">OpenAI (leer la web del negocio)</h3></div>
      {s.connected
        ? <p className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-200" data-testid="openai-status-connected">Conectado · clave {s.hint} · modelo {s.model}. Cada cliente puede leer su web {s.per_day} veces al día.</p>
        : <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200" data-testid="openai-status-missing">Sin conectar: tus clientes no pueden usar «Leer mi web con IA».</p>}
      <Input type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder="Clave de API de OpenAI (sk-…)" className="bg-slate-950/60 font-mono" data-testid="openai-key-input" />
      <p className="text-xs text-slate-400">Créala en platform.openai.com → API keys. Al guardar se comprueba que funciona. Se usa el modelo económico {s.model}, con un máximo de {s.per_day} lecturas al día por cliente.</p>
      <div className="flex gap-2">
        <Button onClick={save} disabled={busy || key.trim().length < 20} className="rounded-full" data-testid="openai-save-button">{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}{s.connected ? "Cambiar clave" : "Conectar OpenAI"}</Button>
        {s.connected && <Button variant="ghost" onClick={off} className="rounded-full" data-testid="openai-disconnect-button">Desconectar</Button>}
      </div>
    </Panel>
  );
}
