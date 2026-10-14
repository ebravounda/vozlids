import { useEffect, useState } from "react";
import { CheckCircle2, LifeBuoy, UserRound } from "lucide-react";
import { PageHeader, Panel } from "@/components/Common";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/constants";

export default function Support() {
  const [items, setItems] = useState([]);
  const load = () => api.get("/support-tickets").then((r) => setItems(r.data));
  useEffect(() => { load(); }, []);
  const resolve = async (id) => { await api.put(`/support-tickets/${id}/resolve`); load(); };
  return (
    <div className="fade-up">
      <PageHeader eyebrow="Asistencia técnica" title="Clientes que necesitan ayuda" desc="Cuando un cliente pide ayuda o quiere hablar con una persona durante una llamada, el agente lo registra aquí y te avisa por email." />
      <div className="space-y-3" data-testid="support-list">
        {items.map((t) => (
          <Panel key={t.id} className="flex items-start justify-between gap-4 p-5" data-testid={`support-${t.id}`}>
            <div className="flex gap-3">
              {t.kind === "humano" ? <UserRound className={`mt-0.5 h-5 w-5 ${t.status === "abierta" ? "text-rose-300" : "text-slate-600"}`} /> : <LifeBuoy className={`mt-0.5 h-5 w-5 ${t.status === "abierta" ? "text-amber-300" : "text-slate-600"}`} />}
              <div>
                {t.kind === "humano" && <span className="mb-1 inline-block rounded-full bg-rose-500/15 px-2 py-0.5 text-xs font-semibold text-rose-300" data-testid={`support-human-badge-${t.id}`}>Quiere hablar con una persona</span>}
                <p className="font-semibold text-white">{t.lead_name} <a href={`tel:${t.lead_phone}`} className="font-mono text-xs text-slate-400 hover:text-emerald-300" data-testid={`support-call-${t.id}`}>{t.lead_phone}</a></p>
                <p className="mt-1 text-sm text-slate-300">{t.issue}</p>
                {t.best_time && <p className="mt-1 text-xs text-slate-400">Mejor momento: {t.best_time}</p>}
                <p className="mt-1 text-xs text-slate-500">{fmtDate(t.created_at)} · {t.status}</p>
              </div>
            </div>
            {t.status === "abierta" && <button onClick={() => resolve(t.id)} className="inline-flex items-center gap-1.5 rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-200 hover:border-emerald-500" data-testid={`support-resolve-${t.id}`}><CheckCircle2 className="h-3.5 w-3.5" /> Resuelta</button>}
          </Panel>
        ))}
        {!items.length && <Panel><p className="text-sm text-slate-500" data-testid="support-empty">No hay solicitudes de asistencia.</p></Panel>}
      </div>
    </div>
  );
}
