import { toast } from "sonner";
import { api } from "@/lib/api";

// Watches the Zadarma widget and hangs up when the plan minutes run out.
const talking = () => {
  const w = window.zdrmWPhI;
  const box = document.getElementsByClassName("zdrm-webphone-media-box")[0];
  return !!w && w.status === "call" && !!box && !box.className.includes("zdrm-webphone-hide");
};

export function startDialerGuard() {
  if (window.__vozGuard) return;
  let startedAt = 0, deadline = null, warned = false, pid = null;
  const dialed = () => window.zdrmWPhI?.number || document.getElementById("zdrm-webphone-phonenumber-input")?.value || "";
  const end = () => {
    const secs = Math.round((Date.now() - startedAt) / 1000);
    if (pid) api.post(`/dialer/pending/${pid}/end`, { seconds: secs }).catch(() => {});
    startedAt = 0; deadline = null; warned = false; pid = null;
  };
  window.__vozGuard = setInterval(async () => {
    const on = talking();
    if (on && !startedAt) {
      startedAt = Date.now();
      api.post("/dialer/pending", { to: dialed() }).then((r) => { pid = r.data.id; }).catch(() => {});
      try {
        const { data } = await api.get("/dialer/remaining");
        deadline = data.seconds == null ? null : startedAt + data.seconds * 1000;
      } catch { deadline = null; }
    } else if (!on && startedAt) {
      end();
      return;
    }
    if (!startedAt || deadline == null) return;
    const left = deadline - Date.now();
    if (left <= 60000 && !warned) { warned = true; toast.warning("Queda menos de 1 minuto de tu plan: la llamada se cortará"); }
    if (left <= 0) {
      window.zdrmWPhI?.finishCall?.();
      toast.error("Has agotado los minutos de tu plan. Llamada finalizada.");
      end();
    }
  }, 1000);
}
