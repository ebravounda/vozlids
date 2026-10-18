import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";

const VIEWS = [["day", "Día"], ["week", "Semana"], ["month", "Mes"]];

export function Toolbar({ view, setView, label, onPrev, onNext, onToday, onNew, stats }) {
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200/80 bg-white p-3 shadow-sm" data-testid="cal-toolbar">
      <div className="flex items-center gap-2">
        <button onClick={onToday} className="rounded-lg bg-slate-100 px-3 py-1.5 text-sm font-medium text-slate-700 transition-[background-color,transform] hover:bg-slate-200 active:scale-95" data-testid="cal-today">Hoy</button>
        <button onClick={onPrev} className="rounded-lg border border-slate-200 p-1.5 text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900" data-testid="cal-prev" aria-label="Anterior"><ChevronLeft className="h-4 w-4" /></button>
        <button onClick={onNext} className="rounded-lg border border-slate-200 p-1.5 text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900" data-testid="cal-next" aria-label="Siguiente"><ChevronRight className="h-4 w-4" /></button>
        <h2 className="ml-1 text-lg font-bold tracking-tight text-slate-900 md:text-xl" style={{ fontFamily: "Plus Jakarta Sans" }} data-testid="cal-title">{label}</h2>
        <span className="hidden rounded-full border border-slate-200/60 bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600 sm:inline" data-testid="cal-count">{stats}</span>
      </div>
      <div className="flex items-center gap-2">
        <div className="inline-flex gap-1 rounded-lg border border-slate-200/60 bg-slate-100 p-1" data-testid="cal-view-switch">
          {VIEWS.map(([v, l]) => (
            <button key={v} onClick={() => setView(v)} className={`rounded-md px-3 py-1 text-xs font-semibold transition-colors ${view === v ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-900"}`} data-testid={`cal-view-${v}`}>{l}</button>
          ))}
        </div>
        <Button onClick={onNew} className="rounded-lg bg-blue-600 text-white shadow-sm transition-transform hover:bg-blue-700 active:scale-95" data-testid="cal-new-appt"><Plus className="mr-1 h-4 w-4" />Nueva cita</Button>
      </div>
    </div>
  );
}

export const Legend = () => (
  <div className="mt-4 flex flex-wrap items-center gap-4 rounded-xl border border-slate-200/80 bg-white p-3 text-xs text-slate-600 shadow-sm" data-testid="cal-legend">
    {[["bg-blue-600", "Reservada por el agente IA"], ["bg-emerald-500", "Creada a mano"], ["bg-amber-500", "Rellamada automática"], ["bg-violet-500", "Ejemplo"], ["bg-slate-300", "Pasada"], ["bg-slate-200 border border-dashed border-slate-400", "Ocupado en Google"]].map(([c, l]) => <span key={l} className="flex items-center gap-1.5"><span className={`h-2 w-2 rounded-full ${c}`} />{l}</span>)}
    <span className="flex items-center gap-1.5"><span className="h-2.5 w-4 rounded-sm border border-slate-200 bg-slate-50" />Fuera de horario</span>
    <span>· Arrastra una cita para moverla · Haz clic en un hueco para crear una</span>
  </div>
);
