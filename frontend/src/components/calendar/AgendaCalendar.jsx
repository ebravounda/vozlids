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
  const [gbusy, setGbusy] = useState([]);
  const [dlg, setDlg] = useState(null);
  const [leadId, setLeadId] = useState(null);
  const [lo, hi] = useMemo(() => range(view, cursor), [view, cursor]);

  const load = useCallback(() => {
    const params = { start: ymd(lo), end: ymd(hi) };
    return Promise.all([api.get("/appointments", { params }), api.get("/callbacks", { params }).catch(() => ({ data: [] }))])
      .then(([a, c]) => setAppts([...a.data, ...c.data])).catch(() => {});
  }, [lo, hi]);
  useEffect(() => { load(); api.get("/google/busy", { params: { start: ymd(lo), end: ymd(hi) } }).then((r) => setGbusy(r.data)).catch(() => setGbusy([])); }, [load, lo, hi]);

  const bounds = useMemo(() => {
    const [a, b] = hoursBounds(av);
    const mins = appts.map(apptMin);
    return [Math.min(a, ...mins.map((m) => Math.floor(m / 60))), Math.max(b, ...mins.map((m) => Math.ceil((m + 30) / 60)))];
  }, [av, appts]);

  const move = async (id, start) => {
    const prev = appts.find((a) => a.id === id);
    if (!prev || prev.start === start) return;
    setAppts((xs) => xs.map((a) => (a.id === id ? { ...a, start } : a)));
    const cb = prev.kind === "callback";
    try { await api.patch(`/${cb ? "callbacks" : "appointments"}/${id}`, { start }); toast.success(`${cb ? "Rellamada" : "Cita"} movida a las ${start.slice(11)}`); }
    catch (e) { setAppts((xs) => xs.map((a) => (a.id === id ? prev : a))); toast.error(errMsg(e)); }
  };
  const nextSlot = () => { const n = new Date(); n.setMinutes(0, 0, 0); n.setHours(n.getHours() + 1); return `${ymd(n)}T${pad(n.getHours())}:00`; };
  const common = { appts, av, bounds, gbusy, onOpen: (a) => setDlg({ appt: a }), onCreate: (s) => (new Date(`${s}:00`) < new Date() ? toast.info("Ese hueco ya ha pasado. Elige una hora futura.") : setDlg({ create: s })), onMove: move };
  const ncb = appts.filter((a) => a.kind === "callback").length;
  const count = appts.length - ncb;

  return (
    <div data-testid="agenda-calendar">
      <Toolbar view={view} setView={setView} label={title(view, cursor)} stats={`${count} ${count === 1 ? "cita" : "citas"}${ncb ? ` · ${ncb} ${ncb === 1 ? "rellamada" : "rellamadas"}` : ""}`}
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
