import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";

const VIEWS = [["day", "Día"], ["week", "Semana"], ["month", "Mes"]];

export function Toolbar({ view, setView, label, onPrev, onNext, onToday, onNew, stats }) {
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3" data-testid="cal-toolbar">
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={onToday} className="rounded-full border-slate-200 bg-white text-slate-700" data-testid="cal-today">Hoy</Button>
        <div className="flex rounded-full border border-slate-200 bg-white">
          <button onClick={onPrev} className="rounded-l-full p-2 text-slate-600 hover:bg-slate-100" data-testid="cal-prev" aria-label="Anterior"><ChevronLeft className="h-4 w-4" /></button>
          <button onClick={onNext} className="rounded-r-full p-2 text-slate-600 hover:bg-slate-100" data-testid="cal-next" aria-label="Siguiente"><ChevronRight className="h-4 w-4" /></button>
        </div>
        <h2 className="ml-1 text-lg font-bold text-slate-900" data-testid="cal-title">{label}</h2>
        <span className="hidden rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-semibold text-blue-700 sm:inline" data-testid="cal-count">{stats}</span>
      </div>
      <div className="flex items-center gap-2">
        <div className="flex rounded-full bg-slate-100 p-1" data-testid="cal-view-switch">
          {VIEWS.map(([v, l]) => (
            <button key={v} onClick={() => setView(v)} className={`rounded-full px-3.5 py-1 text-sm font-medium transition-colors ${view === v ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800"}`} data-testid={`cal-view-${v}`}>{l}</button>
          ))}
        </div>
        <Button onClick={onNew} className="rounded-full bg-blue-600 text-white hover:bg-blue-700" data-testid="cal-new-appt"><Plus className="mr-1 h-4 w-4" />Nueva cita</Button>
      </div>
    </div>
  );
}

export const Legend = () => (
  <div className="mt-3 flex flex-wrap gap-4 text-xs text-slate-500" data-testid="cal-legend">
    {[["bg-blue-600", "Reservada por el agente IA"], ["bg-emerald-500", "Creada a mano"], ["bg-violet-500", "Ejemplo"], ["bg-slate-300", "Pasada"], ["bg-slate-200 border border-dashed border-slate-400", "Ocupado en Google"]].map(([c, l]) => <span key={l} className="flex items-center gap-1.5"><span className={`h-2 w-2 rounded-full ${c}`} />{l}</span>)}
    <span className="flex items-center gap-1.5"><span className="h-2.5 w-4 rounded-sm bg-[repeating-linear-gradient(135deg,#E2E8F0_0_3px,#F8FAFC_3px_6px)]" />Fuera de horario</span>
    <span>· Arrastra una cita para moverla · Haz clic en un hueco para crear una</span>
  </div>
);
