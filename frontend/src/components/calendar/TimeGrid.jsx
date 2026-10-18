import { useEffect, useState } from "react";
import { Bot, CheckCircle2, PhoneCall, UserRound } from "lucide-react";
import { HOUR_PX, KIND_LABEL, addDays, apptDay, apptMin, cap, dayLabel, endHm, fromMin, kindOf, sameDay, toMin, tone, ymd } from "@/lib/cal";

const useNow = () => {
  const [n, setN] = useState(new Date());
  useEffect(() => { const t = setInterval(() => setN(new Date()), 60000); return () => clearInterval(t); }, []);
  return n;
};

const lanes = (list, slot) => {
  const out = {}, sorted = [...list].sort((x, y) => apptMin(x) - apptMin(y));
  let group = [], ends = [], groupEnd = -1;
  const flush = () => group.forEach((id) => { out[id].n = ends.length; });
  sorted.forEach((a) => {
    const s = apptMin(a), e = s + (a.duration_minutes || slot);
    if (s >= groupEnd) { flush(); group = []; ends = []; }
    let lane = ends.findIndex((x) => x <= s);
    if (lane < 0) { lane = ends.length; ends.push(e); } else ends[lane] = e;
    out[a.id] = { lane, n: 1 };
    group.push(a.id);
    groupEnd = Math.max(groupEnd, e);
  });
  flush();
  return out;
};

function Event({ a, slot, h0, onOpen, now, lane = { lane: 0, n: 1 } }) {
  const dur = a.duration_minutes || slot;
  const past = new Date(`${a.start}:00`) < now;
  const top = ((apptMin(a) - h0 * 60) / 60) * HOUR_PX;
  const h = Math.max(22, (dur / 60) * HOUR_PX - 3);
  const Icon = a.kind === "callback" ? PhoneCall : a.source === "manual" ? UserRound : Bot;
  return (
    <button draggable onDragStart={(e) => { e.dataTransfer.setData("text/appt", a.id); e.dataTransfer.effectAllowed = "move"; }}
      onClick={(e) => { e.stopPropagation(); onOpen(a); }}
      className={`cal-event absolute z-10 flex flex-col overflow-hidden rounded-lg border border-l-4 px-2 py-1 text-left shadow-[0_1px_2px_rgba(15,23,42,0.06)] transition-[transform,box-shadow,background-color] hover:z-30 hover:-translate-y-px hover:shadow-md ${tone(a, past)}`}
      style={{ top, height: h, left: `calc(${(lane.lane / lane.n) * 100}% + 4px)`, width: `calc(${100 / lane.n}% - 8px)`, right: "auto" }} data-testid={`cal-event-${a.id}`}>
      <span className="flex min-w-0 items-center gap-1 truncate text-xs font-semibold leading-snug" style={{ fontFamily: "Plus Jakarta Sans" }}><Icon className="h-3 w-3 shrink-0 opacity-60" /><span className="truncate">{a.lead_name}</span>{a.confirmed_at && <CheckCircle2 className="h-3 w-3 shrink-0 text-emerald-600" data-testid={`cal-event-confirmed-${a.id}`} />}</span>
      {h > 34 && <span className="mt-0.5 block truncate font-mono text-[11px] opacity-75">{a.start.slice(11, 16)} – {endHm(a, slot)}</span>}
      {h > 60 && <span className="mt-auto truncate text-[10px] font-semibold uppercase tracking-wider opacity-60">{KIND_LABEL[kindOf(a, past)]}</span>}
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
    <div className={`relative cursor-pointer border-l border-slate-200/70 transition-colors ${over ? "bg-blue-50/60" : ""}`} style={{ height: (h1 - h0) * HOUR_PX }}
      onClick={(e) => onCreate(`${ymd(day)}T${fromMin(minutesAt(e))}`)}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); onMove(e.dataTransfer.getData("text/appt"), `${ymd(day)}T${fromMin(minutesAt(e))}`); }}
      data-testid={`cal-col-${ymd(day)}`}>
      <div className="pointer-events-none absolute inset-0 bg-slate-50/80" />
      {cfg?.enabled && <div className="pointer-events-none absolute inset-x-0 border-y border-slate-200/60 bg-white" style={open(toMin(cfg.start), toMin(cfg.end))} />}
      {Array.from({ length: h1 - h0 }, (_, i) => <div key={i} className="pointer-events-none absolute inset-x-0 border-t border-slate-100" style={{ top: i * HOUR_PX }} />)}
      {Array.from({ length: h1 - h0 }, (_, i) => <div key={`h${i}`} className="pointer-events-none absolute inset-x-0 border-t border-dashed border-slate-100/80" style={{ top: i * HOUR_PX + HOUR_PX / 2 }} />)}
      {gbusy.filter((b) => b.start.slice(0, 10) <= ymd(day) && b.end > ymd(day)).map((b, i) => {
        const lo = b.start.slice(0, 10) < ymd(day) ? 0 : toMin(b.start.slice(11, 16));
        const hi = b.end.slice(0, 10) > ymd(day) ? 24 * 60 : toMin(b.end.slice(11, 16));
        const st = open(Math.max(lo, h0 * 60), Math.min(hi, h1 * 60));
        return st.height > 0 && <div key={i} title={`Ocupado en Google: ${b.title}`} className="pointer-events-none absolute inset-x-1 z-[5] overflow-hidden rounded-md border border-dashed border-slate-300 bg-slate-100/90 px-1.5 py-0.5 text-[10px] font-medium text-slate-500" style={st} data-testid="cal-google-busy">Google · {b.title}</div>;
      })}
      {(() => { const list = appts.filter((a) => apptDay(a) === ymd(day)); const L = lanes(list, slot); return list.map((a) => <Event key={a.id} a={a} slot={slot} h0={h0} onOpen={onOpen} now={now} lane={L[a.id]} />); })()}
      {isToday && nowTop > 0 && nowTop < (h1 - h0) * HOUR_PX && (
        <div className="pointer-events-none absolute inset-x-0 z-20 flex items-center" style={{ top: nowTop }} data-testid="cal-now-line">
          <span className="-ml-1.5 h-3 w-3 rounded-full bg-rose-500 shadow-sm ring-2 ring-white" /><span className="h-0.5 flex-1 bg-rose-500" />
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
  const grid = { gridTemplateColumns: `4rem repeat(${days}, minmax(0, 1fr))` };
  return (
    <div className="overflow-hidden rounded-xl border border-slate-200/80 bg-white shadow-sm" data-testid="cal-timegrid">
      <div className="grid border-b border-slate-200 bg-white" style={grid}>
        <div />
        {cols.map((d) => (
          <div key={ymd(d)} className="border-l border-slate-200/70 px-2 py-3 text-center">
            <p className={`text-[11px] font-semibold uppercase tracking-wider ${sameDay(d, now) ? "text-blue-600" : "text-slate-400"}`}>{cap(dayLabel(d, { weekday: "short" }))}</p>
            <p className={`mx-auto mt-1 flex h-9 w-9 items-center justify-center rounded-full text-lg font-bold transition-colors ${sameDay(d, now) ? "bg-blue-600 text-white shadow-sm" : "text-slate-800 hover:bg-slate-100"}`} style={{ fontFamily: "Plus Jakarta Sans" }}>{d.getDate()}</p>
          </div>
        ))}
      </div>
      <div className="max-h-[68vh] overflow-y-auto">
        <div className="grid" style={grid}>
          <div className="relative" style={{ height: (h1 - h0) * HOUR_PX }}>
            {Array.from({ length: h1 - h0 }, (_, i) => <span key={i} className="absolute right-3 -translate-y-1/2 text-[11px] font-medium text-slate-400" style={{ top: i * HOUR_PX }}>{i ? `${String(h0 + i).padStart(2, "0")}:00` : ""}</span>)}
          </div>
          {cols.map((d) => <Column key={ymd(d)} day={d} appts={appts} gbusy={gbusy} av={av} slot={slot} h0={h0} h1={h1} onOpen={onOpen} onCreate={onCreate} onMove={onMove} now={now} />)}
        </div>
      </div>
    </div>
  );
}
