import { useState } from "react";
import { addDays, apptDay, bar, chip, sameDay, ymd } from "@/lib/cal";

const WD = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

function Cell({ day, month, list, onOpen, onDay, onMove }) {
  const [over, setOver] = useState(false);
  const today = sameDay(day, new Date());
  const out = day.getMonth() !== month;
  return (
    <div onClick={() => onDay(day)} onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); const id = e.dataTransfer.getData("text/appt"); const a = list.all.find((x) => x.id === id); a && onMove(id, `${ymd(day)}T${a.start.slice(11, 16)}`); }}
      className={`min-h-[7.5rem] cursor-pointer p-1.5 transition-colors hover:bg-slate-50/80 ${out ? "bg-slate-50/60" : "bg-white"} ${over ? "!bg-blue-50" : ""}`}
      data-testid={`cal-month-cell-${ymd(day)}`}>
      <div className="mb-1 flex items-center justify-between px-0.5">
        <p className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${today ? "bg-blue-600 text-white shadow-sm" : out ? "text-slate-300" : "text-slate-700"}`}>{day.getDate()}</p>
        {list.day.length > 0 && <span className="text-[10px] font-semibold text-slate-400">{list.day.length}</span>}
      </div>
      <div className="space-y-1">
        {list.day.slice(0, 3).map((a) => (
          <button key={a.id} draggable onDragStart={(e) => e.dataTransfer.setData("text/appt", a.id)} onClick={(e) => { e.stopPropagation(); onOpen(a); }}
            className={`flex w-full items-center gap-1.5 truncate rounded-md px-1.5 py-0.5 text-left text-[11px] font-medium transition-[filter] hover:brightness-95 ${chip(a, new Date(`${a.start}:00`) < new Date())}`} data-testid={`cal-month-event-${a.id}`}>
            <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${bar(a, false)}`} /><span className="font-mono opacity-70">{a.start.slice(11, 16)}</span><span className="truncate">{a.lead_name}</span>
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
    <div className="overflow-hidden rounded-xl border border-slate-200/80 bg-white shadow-sm" data-testid="cal-monthgrid">
      <div className="grid grid-cols-7 border-b border-slate-200 bg-white">{WD.map((d) => <p key={d} className="py-2.5 text-center text-[11px] font-semibold uppercase tracking-wider text-slate-400">{d}</p>)}</div>
      <div className="grid grid-cols-7 gap-px bg-slate-200/70">
        {days.map((d) => <Cell key={ymd(d)} day={d} month={cursor.getMonth()} list={{ day: appts.filter((a) => apptDay(a) === ymd(d)), all: appts }} onOpen={onOpen} onDay={onDay} onMove={onMove} />)}
      </div>
    </div>
  );
}
