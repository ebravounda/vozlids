import { useState } from "react";
import { toast } from "sonner";
import { Copy, ExternalLink, Loader2, PhoneCall } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel, StatusBadge } from "@/components/Common";
import { api, errMsg } from "@/lib/api";
import { COUNTRIES } from "@/lib/constants";

export const TestPublishTab = ({ agentId, country }) => {
  const [phone, setPhone] = useState("");
  const [calling, setCalling] = useState(false);
  const [result, setResult] = useState(null);

  if (!agentId) return <Panel><p className="text-slate-400" data-testid="agent-test-save-first">Guarda el agente para poder probarlo y obtener su formulario.</p></Panel>;

  const formUrl = `${window.location.origin}/f/${agentId}`;
  const snippet = `<iframe src="${formUrl}" width="100%" height="560" style="border:0;border-radius:16px" title="Solicita una llamada"></iframe>`;

  const callMe = async () => {
    setCalling(true);
    setResult(null);
    try {
      const { data } = await api.post(`/agents/${agentId}/test-call`, { phone });
      setResult(data);
      if (data.status === "fallida") toast.error(data.error);
      else toast.success("¡Llamando! Tu móvil sonará en unos segundos.");
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setCalling(false);
    }
  };

  const copy = () => {
    navigator.clipboard?.writeText(snippet);
    toast.success("Código copiado");
  };

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Panel className="space-y-4">
        <h3 className="text-xl font-semibold text-white">Llamarme ahora</h3>
        <p className="text-sm text-slate-400">Recibe una llamada real del agente en tu móvil, con su voz y su ambiente. Guarda antes los cambios.</p>
        <div className="flex gap-2">
          <Input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder={COUNTRIES[country].example} className="h-11 bg-slate-950/60 font-mono" data-testid="agent-test-phone-input" />
          <Button onClick={callMe} disabled={calling || !phone} className="h-11 rounded-full px-5 font-semibold" data-testid="agent-builder-call-me-button">
            {calling ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <PhoneCall className="mr-2 h-4 w-4" />} Llamarme
          </Button>
        </div>
        {result && (
          <div className="space-y-2 rounded-xl border border-slate-800 p-4 text-sm" data-testid="agent-test-result">
            <StatusBadge status={result.status} testid="agent-test-status" />
            {result.error ? <p className="text-red-300">{result.error}</p> : <p className="text-slate-400">Verás la grabación y el resumen en “Leads y llamadas” al colgar.</p>}
          </div>
        )}
      </Panel>
      <Panel className="space-y-4">
        <h3 className="text-xl font-semibold text-white">Formulario para tu web</h3>
        <p className="text-sm text-slate-400">Pega este código en tu web. Cada envío llama al lead al instante.</p>
        <pre className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950 p-4 font-mono text-xs text-emerald-200" data-testid="embed-code-snippet">{snippet}</pre>
        <div className="flex flex-wrap gap-3">
          <Button onClick={copy} variant="outline" className="rounded-full border-slate-700 bg-transparent" data-testid="embed-copy-code-button"><Copy className="mr-2 h-4 w-4" /> Copiar código</Button>
          <a href={formUrl} target="_blank" rel="noreferrer" data-testid="embed-open-form-link" className="inline-flex items-center gap-2 rounded-full border border-slate-700 px-4 py-2 text-sm text-slate-200 hover:text-white">
            <ExternalLink className="h-4 w-4" /> Abrir formulario
          </a>
        </div>
      </Panel>
    </div>
  );
};
