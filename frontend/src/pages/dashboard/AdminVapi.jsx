import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, PhoneIncoming, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader, Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";
import { CallsTable, ErrorsList, NumbersTable, SpendView } from "@/components/vapi/VapiParts";

const EVERY = 15000;

export default function AdminVapi() {
  const [data, setData] = useState({});
  const [busy, setBusy] = useState(false);
  const [at, setAt] = useState(null);

  const load = useCallback(async () => {
    const keys = ["calls", "errors", "spend", "numbers"];
    const res = await Promise.allSettled(keys.map((k) => api.get(`/admin/vapi/${k}`).then((r) => r.data)));
    setData((d) => ({ ...d, ...Object.fromEntries(keys.flatMap((k, i) => (res[i].status === "fulfilled" ? [[k, res[i].value]] : [])) ) }));
    const failed = res.find((r) => r.status === "rejected");
    if (failed) toast.error(errMsg(failed.reason));
    setAt(new Date());
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(() => { if (!document.hidden) load(); }, EVERY);
    return () => clearInterval(t);
  }, [load]);

  const refresh = async () => { setBusy(true); await load(); setBusy(false); };
  const repair = async () => {
    setBusy(true);
    try {
      const r = (await api.post("/admin/lines/repair-inbound", {}, { timeout: 600000 })).data;
      const bad = r.numbers.filter((n) => !n.ok);
      bad.length ? toast.error(`${bad.length} número(s) no se pudieron reparar: revisa la pestaña Números`) : toast.success("Llamadas entrantes reparadas");
      await load();
    } catch (e) { toast.error(errMsg(e)); }
    setBusy(false);
  };

  const bad = (data.numbers?.numbers || []).filter((n) => !n.ok).length;
  const errs = (data.errors?.calls?.length || 0) + (data.errors?.events?.length || 0);
  return (
    <div className="fade-up" data-testid="admin-vapi-page">
      <PageHeader eyebrow="Super admin" title="Monitor de Vapi" desc="Todo lo que pasa en Vapi: cada llamada y por qué terminó, cómo está conectado cada número, los errores y el gasto. Se actualiza cada 15 segundos y cada 30 minutos repara solo los números mal conectados." />
      <Panel className="mt-6 space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <p className="mr-auto text-xs text-slate-400" data-testid="vapi-updated-at">{at ? `Actualizado a las ${at.toLocaleTimeString("es-ES")}` : "Cargando…"}</p>
          <Button size="sm" variant="outline" onClick={refresh} disabled={busy} className="rounded-full" data-testid="vapi-refresh-button">{busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}Actualizar</Button>
          <Button size="sm" onClick={repair} disabled={busy} className="rounded-full" data-testid="vapi-repair-button"><PhoneIncoming className="mr-2 h-4 w-4" />Reparar ahora</Button>
        </div>
        <Tabs defaultValue="calls">
          <TabsList data-testid="vapi-tabs">
            <TabsTrigger value="calls" data-testid="vapi-tab-calls">Llamadas</TabsTrigger>
            <TabsTrigger value="numbers" data-testid="vapi-tab-numbers">Números{bad ? ` (${bad} con fallo)` : ""}</TabsTrigger>
            <TabsTrigger value="errors" data-testid="vapi-tab-errors">Errores{errs ? ` (${errs})` : ""}</TabsTrigger>
            <TabsTrigger value="spend" data-testid="vapi-tab-spend">Gasto</TabsTrigger>
          </TabsList>
          <TabsContent value="calls"><CallsTable rows={data.calls} /></TabsContent>
          <TabsContent value="numbers"><NumbersTable data={data.numbers} /></TabsContent>
          <TabsContent value="errors"><ErrorsList data={data.errors} /></TabsContent>
          <TabsContent value="spend"><SpendView data={data.spend} /></TabsContent>
        </Tabs>
      </Panel>
    </div>
  );
}
