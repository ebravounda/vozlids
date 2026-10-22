import { toast } from "sonner";
import { api, errMsg } from "@/lib/api";

// Singleton browser phone on top of Zadarma's WebRTC engine (no Zadarma UI). Survives page changes.
const LIB = "https://my.zadarma.com/webphoneWebRTCWidget/v9/js/loader-phone-lib.js?sub_v=1";
const ERRORS = {
  integrationDisabled: "Activa el widget WebRTC en Zadarma (Configuración → Integraciones y API → Widget WebRTC), añade el dominio de tu panel y marca la línea.",
  noMicrophone: "No hay micrófono disponible o no diste permiso.",
  BROWSER_NOT_SUPPORTED: "Este navegador no permite llamadas. Usa Chrome, Edge o Safari actualizados.",
};

let state = { status: "off", line: "", to: "", startedAt: 0, deadline: null, muted: false, held: false, error: "", log: [] };
const subs = new Set();
const set = (patch) => { state = { ...state, ...patch }; subs.forEach((f) => f(state)); };
export const subscribe = (f) => { subs.add(f); f(state); return () => subs.delete(f); };
export const getState = () => state;

let phone = null, pid = null, tick = null, warned = false;

const loadLib = () => new Promise((ok, fail) => {
  if (window.ZadarmaWebphoneAPI) return ok();
  if (!document.querySelector(`script[src="${LIB}"]`)) {
    const s = document.createElement("script");
    s.src = LIB; s.onerror = () => fail(new Error("No se pudo cargar el teléfono de Zadarma"));
    document.body.appendChild(s);
  }
  let n = 0;
  const t = setInterval(() => {
    if (window.ZadarmaWebphoneAPI && window.DetectRTC && window.JsSIP) { clearInterval(t); ok(); }
    else if (++n > 150) { clearInterval(t); fail(new Error("El teléfono de Zadarma no respondió")); }
  }, 100);
});

export function normalize(raw, line) {
  let d = String(raw || "").replace(/[^\d+]/g, "");
  if (d.startsWith("+")) return d.slice(1);
  if (d.startsWith("00")) return d.slice(2);
  const cc = line.startsWith("+56") ? "56" : "34";
  return d.length === 9 ? cc + d : d;
}

function onConfirmed() {
  const startedAt = Date.now();
  warned = false;
  set({ status: "talking", startedAt, deadline: null });
  api.post("/dialer/pending", { to: state.to }).then((r) => { pid = r.data.id; }).catch(() => {});
  api.get("/dialer/remaining").then(({ data }) => {
    if (state.startedAt === startedAt && data.seconds != null) set({ deadline: startedAt + data.seconds * 1000 });
  }).catch(() => {});
  clearInterval(tick);
  tick = setInterval(() => {
    if (state.status !== "talking" || state.deadline == null) return;
    const left = state.deadline - Date.now();
    if (left <= 60000 && !warned) { warned = true; toast.warning("Queda menos de 1 minuto de tu plan: la llamada se cortará"); }
    if (left <= 0) { toast.error("Has agotado los minutos de tu plan. Llamada finalizada."); hangup(); }
  }, 500);
}

function onEnded() {
  if (state.status !== "calling" && state.status !== "talking") return;
  clearInterval(tick);
  if (state.startedAt && pid) api.post(`/dialer/pending/${pid}/end`, { seconds: Math.round((Date.now() - state.startedAt) / 1000) }).catch(() => {});
  pid = null;
  set({ status: "ready", startedAt: 0, deadline: null, muted: false, held: false });
  window.dispatchEvent(new Event("voz-dialer-ended"));
}

function trace(event, data) {
  let txt = "";
  try { txt = data == null ? "" : JSON.stringify(data).slice(0, 300); } catch { txt = String(data); }
  set({ log: [{ at: new Date().toLocaleTimeString(), event, txt }, ...state.log].slice(0, 30) });
}

function onStatus(msg, params) {
  trace(msg, params);
  if (msg === "confirmed") onConfirmed();
  else if (["canceled", "rejected", "busy"].includes(msg)) {
    if (msg === "busy") toast("El número está ocupado");
    if (state.status === "calling" || state.status === "talking") onEnded();
  } else if (msg === "incoming") phone?.cancel?.();
  else if (msg === "hold" || msg === "unhold") set({ held: msg === "hold" });
  else if (ERRORS[msg]) set({ status: "error", error: ERRORS[msg] });
}

export async function connect(number) {
  if (phone && state.status !== "error") return;
  set({ status: "loading", error: "" });
  try {
    const st = await navigator.mediaDevices.getUserMedia({ audio: true });
    st.getTracks().forEach((t) => t.stop());
    const { data } = await api.post("/dialer/session", { number });
    await loadLib();
    phone = new window.ZadarmaWebphoneAPI();
    phone.init({
      key: data.key, sip: data.sip, type: "site", language: "es",
      getStatusMessage: onStatus,
      getSipsCallback: (sips, code, text) => {
        trace("sips", { sips, code, text });
        if (sips?.disabled || code) set({ status: "error", error: ERRORS[code] || `${code || "Zadarma"}: ${text || "la línea no está disponible para llamadas web"}` });
      },
      callbackEndCall: (d) => { trace("fin de llamada", d); onEnded(); },
      callbackGetPrice: (d) => trace("tarifa", d),
    });
    phone.reg(data.sip);
    set({ status: "ready", line: data.number });
  } catch (e) {
    phone = null;
    set({ status: "error", error: e?.name === "NotAllowedError" ? "Permite el micrófono en el navegador para poder llamar." : errMsg(e) });
  }
}

export function dial(raw) {
  if (!phone || state.status !== "ready") return;
  const to = normalize(raw, state.line);
  if (to.length < 6) { toast.error("Escribe un número válido"); return; }
  set({ status: "calling", to });
  trace("marcando", { to, line: state.line });
  phone.call(to);
}

export function hangup() { phone?.finishCall?.(); onEnded(); }
export function dtmf(d) { if (state.status === "talking") phone?.sendDTMF?.(d); }
export function toggleMute() { const m = !state.muted; phone?.micSwitch?.(m ? "on" : "off"); set({ muted: m }); }
export function toggleHold() { if (state.held) phone?.unhold?.(); else phone?.hold?.(); set({ held: !state.held }); }
