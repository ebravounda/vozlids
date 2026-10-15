import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/api";
import { addDays, apptMin, hoursBounds, pad, range, title, ymd } from "@/lib/cal";
import { LeadDetail } from "@/pages/dashboard/LeadDetail";
import { ApptDialog } from "./ApptDialog";
import { MonthGrid } from "./MonthGrid";
import { TimeGrid } from "./TimeGrid";
import { Legend, Toolbar } from "./Toolbar";

const step = (view, d, dir) => (view === "month" ? new Date(d.getFullYear(), d.getMonth() + dir, 1) : addDays(d, dir * (view === "week" ? 7 : 1)));

export function AgendaCalendar({ av }) {
  const [view, setView] = useState(() => (window.innerWidth < 768 ? "day" : "week"));
  const [cursor, setCursor] = useState(new Date());
  const [appts, setAppts] = useState([]);
  const [dlg, setDlg] = useState(null);
  const [leadId, setLeadId] = useState(null);
  const [lo, hi] = useMemo(() => range(view, cursor), [view, cursor]);

  const load = useCallback(() => api.get("/appointments", { params: { start: ymd(lo), end: ymd(hi) } }).then((r) => setAppts(r.data)).catch(() => {}), [lo, hi]);
  useEffect(() => { load(); }, [load]);

  const bounds = useMemo(() => {
    const [a, b] = hoursBounds(av);
    const mins = appts.map(apptMin);
    return [Math.min(a, ...mins.map((m) => Math.floor(m / 60))), Math.max(b, ...mins.map((m) => Math.ceil((m + 30) / 60)))];
  }, [av, appts]);

  const move = async (id, start) => {
    const prev = appts.find((a) => a.id === id);
    if (!prev || prev.start === start) return;
    setAppts((xs) => xs.map((a) => (a.id === id ? { ...a, start } : a)));
    try { await api.patch(`/appointments/${id}`, { start }); toast.success(`Cita movida a las ${start.slice(11)}`); }
    catch (e) { setAppts((xs) => xs.map((a) => (a.id === id ? prev : a))); toast.error(errMsg(e)); }
  };
  const nextSlot = () => { const n = new Date(); n.setMinutes(0, 0, 0); n.setHours(n.getHours() + 1); return `${ymd(n)}T${pad(n.getHours())}:00`; };
  const common = { appts, av, bounds, onOpen: (a) => setDlg({ appt: a }), onCreate: (s) => (new Date(`${s}:00`) < new Date() ? toast.info("Ese hueco ya ha pasado. Elige una hora futura.") : setDlg({ create: s })), onMove: move };
  const count = appts.length;

  return (
    <div data-testid="agenda-calendar">
      <Toolbar view={view} setView={setView} label={title(view, cursor)} stats={`${count} ${count === 1 ? "cita" : "citas"}`}
        onPrev={() => setCursor((d) => step(view, d, -1))} onNext={() => setCursor((d) => step(view, d, 1))} onToday={() => setCursor(new Date())}
        onNew={() => setDlg({ create: nextSlot() })} />
      {view === "month"
        ? <MonthGrid start={lo} cursor={cursor} appts={appts} onOpen={common.onOpen} onMove={move} onDay={(d) => { setCursor(d); setView("day"); }} />
        : <TimeGrid start={lo} days={view === "week" ? 7 : 1} {...common} />}
      <Legend />
      <ApptDialog state={dlg} slot={av.slot_minutes} onClose={() => setDlg(null)} onChanged={load} onLead={setLeadId} />
      <LeadDetail id={leadId} onClose={() => setLeadId(null)} />
    </div>
  );
}
