export const VOICES = [
  { id: "elvira", name: "Elvira", gender: "Mujer", tone: "Cálida y cercana" },
  { id: "alvaro", name: "Álvaro", gender: "Hombre", tone: "Profesional y sereno" },
  { id: "ximena", name: "Ximena", gender: "Mujer", tone: "Joven y enérgica" },
  { id: "dario", name: "Darío", gender: "Hombre", tone: "Cercano y natural" },
  { id: "irene", name: "Irene", gender: "Mujer", tone: "Clara y amable" },
  { id: "arnau", name: "Arnau", gender: "Hombre", tone: "Joven y dinámico" },
];

export const AMBIENCES = [
  { id: "oficina", name: "Oficina con teclados", desc: "Teclados y murmullo lejano de compañeros", volume: true },
  { id: "teclados", name: "Solo teclado", desc: "Tecleo suave de escritorio mientras habla", volume: true },
  { id: "call_center", name: "Call center", desc: "Muchas voces de fondo y actividad", volume: true },
  { id: "vapi_office", name: "Oficina clásica (Vapi)", desc: "Ambiente integrado de Vapi, volumen fijo", volume: false },
  { id: "none", name: "Sin ambiente", desc: "Voz limpia, sin sonido de fondo", volume: false },
];

export const OBJECTIVES = [
  { id: "agendar", name: "Calificar y agendar cita", desc: "Hace las preguntas y reserva un hueco de tu agenda." },
  { id: "calificar", name: "Solo calificar interés", desc: "Hace las preguntas y deja el lead listo para tu equipo." },
  { id: "vender", name: "Vender y cerrar", desc: "Presenta la oferta, resuelve objeciones y busca el sí." },
];

export const STATUS = {
  llamando: { label: "Llamando", cls: "bg-cyan-500/15 text-cyan-300 border-cyan-500/30", dot: "bg-cyan-400 animate-pulse" },
  sin_respuesta: { label: "Sin respuesta", cls: "bg-slate-500/15 text-slate-300 border-slate-500/30", dot: "bg-slate-400" },
  calificado: { label: "Calificado", cls: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30", dot: "bg-emerald-400" },
  no_interesado: { label: "No interesado", cls: "bg-amber-500/15 text-amber-300 border-amber-500/30", dot: "bg-amber-400" },
  cita_agendada: { label: "Cita agendada", cls: "bg-teal-400/15 text-teal-200 border-teal-400/40", dot: "bg-teal-300" },
  venta: { label: "Venta", cls: "bg-lime-400/15 text-lime-200 border-lime-400/40", dot: "bg-lime-300" },
  no_llamar: { label: "No llamar", cls: "bg-rose-500/15 text-rose-300 border-rose-500/30", dot: "bg-rose-400" },
  fallida: { label: "Fallida", cls: "bg-red-500/15 text-red-300 border-red-500/30", dot: "bg-red-400" },
};

export const DAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];

export const DEFAULT_GREETING =
  "Hola {nombre}, soy Marta, la asistente virtual de tu negocio. Te llamo porque acabas de pedir información en nuestra web. La llamada se graba para mejorar el servicio. ¿Tienes un minuto?";

export const fmtDate = (iso) =>
  iso ? new Date(iso).toLocaleString("es-ES", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "";

export const fmtSlot = (s) => {
  const [d, t] = s.split("T");
  const date = new Date(`${d}T00:00:00`);
  return `${date.toLocaleDateString("es-ES", { weekday: "long", day: "numeric", month: "long" })} · ${t}`;
};
