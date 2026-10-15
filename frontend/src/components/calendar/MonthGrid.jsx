import { useState } from "react";
import { addDays, apptDay, bar, sameDay, ymd } from "@/lib/cal";

const WD = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

function Cell({ day, month, list, onOpen, onDay, onMove }) {
  const [over, setOver] = useState(false);
  const today = sameDay(day, new Date());
  const out = day.getMonth() !== month;
  return (
    <div onClick={() => onDay(day)} onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); const id = e.dataTransfer.getData("text/appt"); const a = list.all.find((x) => x.id === id); a && onMove(id, `${ymd(day)}T${a.start.slice(11, 16)}`); }}
      className={`min-h-[7.5rem] cursor-pointer border-l border-t border-slate-200 p-1.5 transition-colors hover:bg-slate-50 ${out ? "bg-slate-50/70" : "bg-white"} ${over ? "!bg-blue-50" : ""}`}
      data-testid={`cal-month-cell-${ymd(day)}`}>
      <p className={`mb-1 flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold ${today ? "bg-blue-600 text-white" : out ? "text-slate-400" : "text-slate-700"}`}>{day.getDate()}</p>
      <div className="space-y-0.5">
        {list.day.slice(0, 3).map((a) => (
          <button key={a.id} draggable onDragStart={(e) => e.dataTransfer.setData("text/appt", a.id)} onClick={(e) => { e.stopPropagation(); onOpen(a); }}
            className="flex w-full items-center gap-1.5 truncate rounded-md px-1.5 py-0.5 text-left text-[11px] text-slate-700 hover:bg-slate-100" data-testid={`cal-month-event-${a.id}`}>
            <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${bar(a, false)}`} /><span className="font-mono text-slate-500">{a.start.slice(11, 16)}</span><span className="truncate">{a.lead_name}</span>
          </button>
        ))}
        {list.day.length > 3 && <p className="px-1.5 text-[11px] font-semibold text-blue-600">+{list.day.length - 3} más</p>}
      </div>
    </div>
  );
}

export function MonthGrid({ start, cursor, appts, onOpen, onDay, onMove }) {
  const days = Array.from({ length: 42 }, (_, i) => addDays(start, i));
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white" data-testid="cal-monthgrid">
      <div className="grid grid-cols-7 bg-slate-50/80">{WD.map((d) => <p key={d} className="border-l border-slate-200 py-2 text-center text-[11px] font-semibold uppercase tracking-wider text-slate-500 first:border-l-0">{d}</p>)}</div>
      <div className="grid grid-cols-7 [&>*:nth-child(7n+1)]:border-l-0">
        {days.map((d) => <Cell key={ymd(d)} day={d} month={cursor.getMonth()} list={{ day: appts.filter((a) => apptDay(a) === ymd(d)), all: appts }} onOpen={onOpen} onDay={onDay} onMove={onMove} />)}
      </div>
    </div>
  );
}
