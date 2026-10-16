export const VOICES = [
  { id: "p_marta", name: "Marta", gender: "Mujer", tone: "Cercana, atención al cliente", premium: true, country: "ES" },
  { id: "p_nuria", name: "Nuria", gender: "Mujer", tone: "Serena y profesional", premium: true, country: "ES" },
  { id: "p_isabel", name: "Isabel", gender: "Mujer", tone: "Castellano suave y amable", premium: true, country: "ES" },
  { id: "p_elena", name: "Elena", gender: "Mujer", tone: "Castellano pausado y cálido", premium: true, country: "ES" },
  { id: "p_marcos", name: "Marcos", gender: "Hombre", tone: "Calmado, asesor de confianza", premium: true, country: "ES" },
  { id: "p_gonzalo", name: "Gonzalo", gender: "Hombre", tone: "Cálido y natural", premium: true, country: "ES" },
  { id: "p_luis", name: "Luis", gender: "Hombre", tone: "Castellano claro y firme", premium: true, country: "ES" },
  { id: "p_hector", name: "Héctor", gender: "Hombre", tone: "Castellano enérgico", premium: true, country: "ES" },
  { id: "elvira", name: "Elvira", gender: "Mujer", tone: "Cálida y cercana", country: "ES" },
  { id: "alvaro", name: "Álvaro", gender: "Hombre", tone: "Profesional y sereno", country: "ES" },
  { id: "ximena", name: "Ximena", gender: "Mujer", tone: "Joven y enérgica", country: "ES" },
  { id: "dario", name: "Darío", gender: "Hombre", tone: "Cercano y natural", country: "ES" },
  { id: "irene", name: "Irene", gender: "Mujer", tone: "Clara y amable", country: "ES" },
  { id: "arnau", name: "Arnau", gender: "Hombre", tone: "Joven y dinámico", country: "ES" },
];

export const COUNTRIES = {
  ES: { name: "España", prefix: "+34", example: "+34 600 000 000", city: "Madrid", currency: "EUR" },
  CL: { name: "Chile", prefix: "+56", example: "+56 9 1234 5678", city: "Santiago", currency: "CLP" },
};

VOICES.push(
  { id: "l_fernanda", name: "Fernanda", gender: "Mujer", tone: "Latina cercana, atención al cliente", premium: true, country: "CL" },
  { id: "l_daniela", name: "Daniela", gender: "Mujer", tone: "Latina tranquila y de confianza", premium: true, country: "CL" },
  { id: "l_regina", name: "Regina", gender: "Mujer", tone: "Latina profesional y clara", premium: true, country: "CL" },
  { id: "l_eduardo", name: "Eduardo", gender: "Hombre", tone: "Latino natural y cercano", premium: true, country: "CL" },
  { id: "l_mateo", name: "Mateo", gender: "Hombre", tone: "Latino cálido y genuino", premium: true, country: "CL" },
  { id: "l_andres", name: "Andrés", gender: "Hombre", tone: "Latino sereno y profesional", premium: true, country: "CL" },
  { id: "cl_catalina", name: "Catalina", gender: "Mujer", tone: "Acento chileno", country: "CL" },
  { id: "cl_lorenzo", name: "Lorenzo", gender: "Hombre", tone: "Acento chileno", country: "CL" },
);

VOICES.unshift(
  { id: "e_sarah", name: "Sara", gender: "Mujer", tone: "Cálida y segura, muy natural", eleven: true, country: "ALL" },
  { id: "e_matilda", name: "Matilde", gender: "Mujer", tone: "Profesional y cercana", eleven: true, country: "ALL" },
  { id: "e_jessica", name: "Jéssica", gender: "Mujer", tone: "Joven y simpática", eleven: true, country: "ALL" },
  { id: "e_laura", name: "Laura", gender: "Mujer", tone: "Alegre y entusiasta", eleven: true, country: "ALL" },
  { id: "e_chris", name: "Cristian", gender: "Hombre", tone: "Natural y cercano", eleven: true, country: "ALL" },
  { id: "e_eric", name: "Eric", gender: "Hombre", tone: "Sereno, de confianza", eleven: true, country: "ALL" },
  { id: "e_roger", name: "Roger", gender: "Hombre", tone: "Relajado y conversador", eleven: true, country: "ALL" },
  { id: "e_will", name: "Guille", gender: "Hombre", tone: "Optimista y tranquilo", eleven: true, country: "ALL" },
);

export const DEFAULT_VOICE = { ES: "e_sarah", CL: "e_sarah" };

export const AMBIENCES = [
  { id: "oficina_real", name: "Oficina real (grabación)", desc: "Oficina real grabada con tecleo bien presente", volume: true, real: true },
  { id: "teclado_real", name: "Teclado real (grabación)", desc: "Tecleo grabado de un portátil, sin voces", volume: true, real: true },
  { id: "oficina", name: "Oficina con teclados", desc: "Teclados y murmullo lejano de compañeros", volume: true },
  { id: "teclados", name: "Solo teclado", desc: "Tecleo suave de escritorio mientras habla", volume: true },
  { id: "call_center", name: "Call center (grabación)", desc: "Grabación real: compañeros hablando por teléfono y tecleo", volume: true, real: true },
  { id: "vapi_office", name: "Oficina clásica", desc: "Ambiente integrado, volumen fijo", volume: false },
  { id: "none", name: "Sin ambiente", desc: "Voz limpia, sin sonido de fondo", volume: false },
];

export const OBJECTIVES = [
  { id: "agendar", name: "Calificar y agendar cita", desc: "Hace las preguntas y reserva un hueco de tu agenda." },
  { id: "calificar", name: "Solo calificar interés", desc: "Hace las preguntas y deja el lead listo para tu equipo." },
  { id: "vender", name: "Vender y cerrar", desc: "Presenta la oferta, resuelve objeciones y busca el sí." },
  { id: "recepcion", name: "Recepcionista (llamadas entrantes)", desc: "Contesta tu número, resuelve dudas, agenda y toma recados." },
];

export const STATUS = {
  llamando: { label: "Llamando", cls: "bg-cyan-500/15 text-cyan-300 border-cyan-500/30", dot: "bg-cyan-400 animate-pulse" },
  sin_respuesta: { label: "Sin respuesta", cls: "bg-slate-500/15 text-slate-300 border-slate-500/30", dot: "bg-slate-400" },
  calificado: { label: "Calificado", cls: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30", dot: "bg-emerald-400" },
  no_interesado: { label: "No interesado", cls: "bg-amber-500/15 text-amber-300 border-amber-500/30", dot: "bg-amber-400" },
  cita_agendada: { label: "Cita agendada", cls: "bg-teal-400/15 text-teal-200 border-teal-400/40", dot: "bg-teal-300" },
  venta: { label: "Venta", cls: "bg-lime-400/15 text-lime-200 border-lime-400/40", dot: "bg-lime-300" },
  no_llamar: { label: "No llamar", cls: "bg-rose-500/15 text-rose-300 border-rose-500/30", dot: "bg-rose-400" },
  buzon: { label: "Buzón de voz", cls: "bg-slate-500/15 text-slate-300 border-slate-500/30", dot: "bg-slate-500" },
  atendida: { label: "Entrante atendida", cls: "bg-sky-500/15 text-sky-300 border-sky-500/30", dot: "bg-sky-400" },
  en_curso: { label: "En curso", cls: "bg-cyan-500/15 text-cyan-300 border-cyan-500/30", dot: "bg-cyan-400 animate-pulse" },
  rellamada: { label: "Pidió rellamada", cls: "bg-amber-400/15 text-amber-200 border-amber-400/40", dot: "bg-amber-300" },
  programada: { label: "Programada", cls: "bg-indigo-500/15 text-indigo-300 border-indigo-500/30", dot: "bg-indigo-400" },
  cancelada: { label: "Cancelada", cls: "bg-slate-500/15 text-slate-400 border-slate-500/30", dot: "bg-slate-500" },
  fallida: { label: "Fallida", cls: "bg-red-500/15 text-red-300 border-red-500/30", dot: "bg-red-400" },
};

export const DAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];

export const TIER = (v) => (v.eleven ? "eleven" : v.premium ? "premium" : "standard");

export const DEFAULT_GREETING =
  "Hola {nombre}, soy Marta, de tu negocio. Te llamo porque acabas de pedir información en nuestra web. La llamada se graba para mejorar el servicio. ¿Tienes un minuto?";

export const fmtDate = (iso) =>
  iso ? new Date(iso).toLocaleString("es-ES", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "";

export const fmtSlot = (s) => {
  const [d, t] = s.split("T");
  const date = new Date(`${d}T00:00:00`);
  return `${date.toLocaleDateString("es-ES", { weekday: "long", day: "numeric", month: "long" })} · ${t}`;
};
