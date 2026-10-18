export const HOUR_PX = 56;
export const pad = (n) => String(n).padStart(2, "0");
export const ymd = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
export const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
export const startOfWeek = (d) => { const x = new Date(d.getFullYear(), d.getMonth(), d.getDate()); return addDays(x, -((x.getDay() + 6) % 7)); };
export const startOfMonthGrid = (d) => startOfWeek(new Date(d.getFullYear(), d.getMonth(), 1));
export const toMin = (hm) => { const [h, m] = hm.split(":").map(Number); return h * 60 + m; };
export const fromMin = (m) => `${pad(Math.floor(m / 60))}:${pad(m % 60)}`;
export const apptDay = (a) => a.start.slice(0, 10);
export const apptMin = (a) => toMin(a.start.slice(11, 16));
export const endHm = (a, slot) => fromMin(apptMin(a) + (a.duration_minutes || slot));
export const sameDay = (a, b) => ymd(a) === ymd(b);
export const dayLabel = (d, opts) => d.toLocaleDateString("es-ES", opts);
export const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

export function range(view, cursor) {
  if (view === "day") return [cursor, addDays(cursor, 1)];
  if (view === "week") { const s = startOfWeek(cursor); return [s, addDays(s, 7)]; }
  const s = startOfMonthGrid(cursor);
  return [s, addDays(s, 42)];
}

export function title(view, cursor) {
  if (view === "day") return cap(dayLabel(cursor, { weekday: "long", day: "numeric", month: "long", year: "numeric" }));
  if (view === "month") return cap(dayLabel(cursor, { month: "long", year: "numeric" }));
  const s = startOfWeek(cursor), e = addDays(s, 6);
  const sameM = s.getMonth() === e.getMonth();
  return `${s.getDate()}${sameM ? "" : " " + dayLabel(s, { month: "short" })} – ${e.getDate()} ${dayLabel(e, { month: "long", year: "numeric" })}`;
}

export function hoursBounds(av) {
  const on = (av?.days || []).filter((d) => d.enabled);
  const lo = on.length ? Math.min(...on.map((d) => toMin(d.start))) : 9 * 60;
  const hi = on.length ? Math.max(...on.map((d) => toMin(d.end))) : 19 * 60;
  return [Math.max(0, Math.floor(lo / 60) - 1), Math.min(24, Math.ceil(hi / 60) + 1)];
}

export const kindOf = (a, past) => (past ? "past" : a.kind === "callback" ? "callback" : a.is_sample ? "sample" : a.source === "manual" ? "manual" : "ai");
const TONES = {
  past: "border-slate-200 border-l-slate-400 bg-slate-100/70 text-slate-500 hover:bg-slate-200/60",
  callback: "border-amber-200/70 border-l-amber-500 bg-amber-50/90 text-amber-950 hover:bg-amber-100/90",
  sample: "border-violet-200/70 border-l-violet-600 bg-violet-50/90 text-violet-950 hover:bg-violet-100/90",
  manual: "border-emerald-200/70 border-l-emerald-600 bg-emerald-50/90 text-emerald-950 hover:bg-emerald-100/90",
  ai: "border-blue-200/70 border-l-blue-600 bg-blue-50/90 text-blue-950 hover:bg-blue-100/90",
};
export const KIND_LABEL = { past: "Pasada", callback: "Rellamada", sample: "Ejemplo", manual: "A mano", ai: "Agente IA" };
export const tone = (a, past) => TONES[kindOf(a, past)];
export const chip = (a, past) => TONES[kindOf(a, past)].replace(/border-\S+/g, "").trim();
export const bar = (a, past) => (past ? "bg-slate-300" : a.kind === "callback" ? "bg-amber-500" : a.is_sample ? "bg-violet-500" : a.source === "manual" ? "bg-emerald-500" : "bg-blue-600");
