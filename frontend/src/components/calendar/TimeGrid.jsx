import { useEffect, useState } from "react";
import { Bot, CheckCircle2, UserRound } from "lucide-react";
import { HOUR_PX, addDays, apptDay, apptMin, bar, cap, dayLabel, endHm, fromMin, sameDay, toMin, tone, ymd } from "@/lib/cal";

const useNow = () => {
  const [n, setN] = useState(new Date());
  useEffect(() => { const t = setInterval(() => setN(new Date()), 60000); return () => clearInterval(t); }, []);
  return n;
};

function Event({ a, slot, h0, onOpen, now }) {
  const dur = a.duration_minutes || slot;
  const past = new Date(`${a.start}:00`) < now;
  const top = ((apptMin(a) - h0 * 60) / 60) * HOUR_PX;
  const h = Math.max(22, (dur / 60) * HOUR_PX - 3);
  const Icon = a.source === "manual" ? UserRound : Bot;
  return (
    <button draggable onDragStart={(e) => { e.dataTransfer.setData("text/appt", a.id); e.dataTransfer.effectAllowed = "move"; }}
      onClick={(e) => { e.stopPropagation(); onOpen(a); }}
      className={`cal-event absolute inset-x-1 z-10 flex overflow-hidden rounded-lg border text-left shadow-sm transition-[transform,box-shadow] hover:-translate-y-px hover:shadow-md ${tone(a, past)}`}
      style={{ top, height: h }} data-testid={`cal-event-${a.id}`}>
      <span className={`w-1 shrink-0 ${bar(a, past)}`} />
      <span className="min-w-0 px-2 py-1">
        <span className="flex items-center gap-1 truncate text-xs font-semibold"><Icon className="h-3 w-3 shrink-0 opacity-70" />{a.lead_name}{a.confirmed_at && <CheckCircle2 className="h-3 w-3 shrink-0 text-emerald-600" data-testid={`cal-event-confirmed-${a.id}`} />}</span>
        {h > 34 && <span className="block truncate font-mono text-[10px] opacity-70">{a.start.slice(11, 16)}–{endHm(a, slot)}</span>}
      </span>
    </button>
  );
}

function Column({ day, appts, gbusy, av, slot, h0, h1, onOpen, onCreate, onMove, now }) {
  const [over, setOver] = useState(false);
  const cfg = av?.days?.[(day.getDay() + 6) % 7];
  const minutesAt = (e) => {
    const y = e.clientY - e.currentTarget.getBoundingClientRect().top;
    return Math.min(h1 * 60 - slot, Math.max(h0 * 60, h0 * 60 + Math.floor((y / HOUR_PX) * 60 / slot) * slot));
  };
  const open = (lo, hi) => ({ top: ((lo - h0 * 60) / 60) * HOUR_PX, height: ((hi - lo) / 60) * HOUR_PX });
  const isToday = sameDay(day, now);
  const nowTop = ((now.getHours() * 60 + now.getMinutes() - h0 * 60) / 60) * HOUR_PX;
  return (
    <div className={`relative border-l border-slate-200 ${over ? "bg-blue-50/60" : ""}`} style={{ height: (h1 - h0) * HOUR_PX }}
      onClick={(e) => onCreate(`${ymd(day)}T${fromMin(minutesAt(e))}`)}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); onMove(e.dataTransfer.getData("text/appt"), `${ymd(day)}T${fromMin(minutesAt(e))}`); }}
      data-testid={`cal-col-${ymd(day)}`}>
      <div className="pointer-events-none absolute inset-0 bg-[repeating-linear-gradient(135deg,#F1F5F9_0_6px,#F8FAFC_6px_12px)]" />
      {cfg?.enabled && <div className="pointer-events-none absolute inset-x-0 bg-white" style={open(toMin(cfg.start), toMin(cfg.end))} />}
      {Array.from({ length: h1 - h0 }, (_, i) => <div key={i} className="pointer-events-none absolute inset-x-0 border-t border-slate-100" style={{ top: i * HOUR_PX }} />)}
      {gbusy.filter((b) => b.start.slice(0, 10) <= ymd(day) && b.end > ymd(day)).map((b, i) => {
        const lo = b.start.slice(0, 10) < ymd(day) ? 0 : toMin(b.start.slice(11, 16));
        const hi = b.end.slice(0, 10) > ymd(day) ? 24 * 60 : toMin(b.end.slice(11, 16));
        const st = open(Math.max(lo, h0 * 60), Math.min(hi, h1 * 60));
        return st.height > 0 && <div key={i} title={`Ocupado en Google: ${b.title}`} className="pointer-events-none absolute inset-x-1 z-[5] overflow-hidden rounded-md border border-dashed border-slate-300 bg-slate-100/90 px-1.5 py-0.5 text-[10px] font-medium text-slate-500" style={st} data-testid="cal-google-busy">Google · {b.title}</div>;
      })}
      {appts.filter((a) => apptDay(a) === ymd(day)).map((a) => <Event key={a.id} a={a} slot={slot} h0={h0} onOpen={onOpen} now={now} />)}
      {isToday && nowTop > 0 && nowTop < (h1 - h0) * HOUR_PX && (
        <div className="pointer-events-none absolute inset-x-0 z-20 flex items-center" style={{ top: nowTop }} data-testid="cal-now-line">
          <span className="-ml-1 h-2 w-2 rounded-full bg-rose-500" /><span className="h-px flex-1 bg-rose-500" />
        </div>
      )}
    </div>
  );
}

export function TimeGrid({ start, days, appts, gbusy = [], av, bounds, onOpen, onCreate, onMove }) {
  const now = useNow();
  const [h0, h1] = bounds;
  const slot = av?.slot_minutes || 30;
  const cols = Array.from({ length: days }, (_, i) => addDays(start, i));
  const grid = { gridTemplateColumns: `3.5rem repeat(${days}, minmax(0, 1fr))` };
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white" data-testid="cal-timegrid">
      <div className="grid border-b border-slate-200 bg-slate-50/80" style={grid}>
        <div />
        {cols.map((d) => (
          <div key={ymd(d)} className="border-l border-slate-200 px-2 py-2.5 text-center">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{cap(dayLabel(d, { weekday: "short" }))}</p>
            <p className={`mx-auto mt-0.5 flex h-8 w-8 items-center justify-center rounded-full text-base font-bold ${sameDay(d, now) ? "bg-blue-600 text-white" : "text-slate-900"}`}>{d.getDate()}</p>
          </div>
        ))}
      </div>
      <div className="max-h-[68vh] overflow-y-auto">
        <div className="grid" style={grid}>
          <div className="relative" style={{ height: (h1 - h0) * HOUR_PX }}>
            {Array.from({ length: h1 - h0 }, (_, i) => <span key={i} className="absolute right-2 -translate-y-1/2 font-mono text-[10px] text-slate-400" style={{ top: i * HOUR_PX }}>{i ? `${String(h0 + i).padStart(2, "0")}:00` : ""}</span>)}
          </div>
          {cols.map((d) => <Column key={ymd(d)} day={d} appts={appts} gbusy={gbusy} av={av} slot={slot} h0={h0} h1={h1} onOpen={onOpen} onCreate={onCreate} onMove={onMove} now={now} />)}
        </div>
      </div>
    </div>
  );
}
