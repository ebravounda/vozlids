import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/Common";
import { AlertSettings, Balances, LiveCalls, Margins } from "@/components/MonitorParts";
import { CallLog, SipLog } from "@/components/MonitorLogs";
import { api } from "@/lib/api";
import { WidgetStats } from "@/components/WidgetStats";
import { fmtDate } from "@/lib/constants";

export default function AdminMonitor() {
  const [b, setB] = useState(null);
  const [alerts, setAlerts] = useState(null);
  const loadB = (fresh = false) => { setB(null); api.get("/admin/monitor/balances", { params: { fresh } }).then((r) => setB(r.data)); };
  const loadA = () => api.get("/admin/monitor/alerts").then((r) => setAlerts(r.data));
  useEffect(() => { loadB(); loadA(); }, []);
  return (
    <div className="fade-up space-y-6" data-testid="admin-monitor-page">
      <PageHeader eyebrow="Super admin" title="Monitor de la plataforma" desc="Saldos de cada proveedor, llamadas en directo, coste de cada llamada y margen por cliente.">
        <Button variant="outline" onClick={() => loadB(true)} className="rounded-full" data-testid="monitor-refresh-button"><RefreshCw className="mr-2 h-4 w-4" />Actualizar saldos</Button>
      </PageHeader>
      <Balances b={b} alerts={alerts} />
      {b && <p className="-mt-3 text-xs text-slate-500" data-testid="monitor-checked-at">Consultado {fmtDate(b.checked_at)}</p>}
      <div className="grid gap-6 xl:grid-cols-2">
        <LiveCalls />
        {alerts && <AlertSettings data={alerts} reload={loadA} />}
      </div>
      <Margins />
      <WidgetStats url="/admin/monitor/widget-stats" title="Botón web · todos los clientes" />
      <CallLog />
      <SipLog />
    </div>
  );
}
