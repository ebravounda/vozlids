import { useEffect, useState } from "react";
import { CalendarClock, Phone } from "lucide-react";
import { api } from "@/lib/api";
import { KIND_LABEL, kindOf, tone, ymd } from "@/lib/cal";

export function TodayPanel({ onOpen, refresh }) {
  const [items, setItems] = useState([]);
  useEffect(() => {
    const d = new Date(), n = new Date(d); n.setDate(d.getDate() + 1);
    api.get("/appointments", { params: { start: ymd(d), end: ymd(n) } }).then((r) => setItems(r.data)).catch(() => setItems([]));
  }, [refresh]);
  const now = new Date();
  const next = items.filter((a) => new Date(`${a.start}:00`) >= new Date(now.getTime() - 30 * 60000)).sort((a, b) => a.start.localeCompare(b.start));
  return (
    <aside className="hidden w-72 shrink-0 flex-col gap-3 self-start rounded-xl border border-slate-200/80 bg-white p-4 shadow-sm xl:flex" data-testid="cal-today-panel">
      <div className="flex items-center justify-between"><p className="text-sm font-bold text-slate-900" style={{ fontFamily: "Plus Jakarta Sans" }}>Próximas citas de hoy</p><span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs font-semibold text-blue-700">{next.length}</span></div>
      {!next.length && <p className="flex items-center gap-2 rounded-lg bg-slate-50 p-3 text-sm text-slate-500" data-testid="cal-today-empty"><CalendarClock className="h-4 w-4" /> No te quedan citas hoy.</p>}
      <div className="max-h-[520px] space-y-2 overflow-y-auto">
        {next.map((a) => (
          <button key={a.id} onClick={() => onOpen(a)} className={`w-full rounded-lg border border-l-4 p-2.5 text-left transition-[transform,box-shadow] hover:-translate-y-px hover:shadow-sm ${tone(a, false)}`} data-testid={`cal-today-item-${a.id}`}>
            <p className="flex items-center justify-between font-mono text-xs font-semibold">{a.start.slice(11, 16)}<span className="font-sans text-[10px] uppercase tracking-wider opacity-60">{KIND_LABEL[kindOf(a, false)]}</span></p>
            <p className="mt-0.5 truncate text-sm font-semibold">{a.lead_name}</p>
            {a.lead_phone && <p className="mt-0.5 flex items-center gap-1 text-xs opacity-70"><Phone className="h-3 w-3" />{a.lead_phone}</p>}
          </button>
        ))}
      </div>
    </aside>
  );
}
