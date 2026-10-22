import axios from "axios";

export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
export const api = axios.create({ baseURL: API, withCredentials: true });

let refreshing = null;
const NO_RETRY = ["/auth/login", "/auth/register", "/auth/refresh"];

api.interceptors.response.use(
  (r) => r,
  async (err) => {
    const cfg = err.config;
    if (err.response?.status === 401 && cfg && !cfg._retry && !NO_RETRY.some((p) => cfg.url.includes(p))) {
      cfg._retry = true;
      try {
        refreshing = refreshing || api.post("/auth/refresh");
        await refreshing;
        refreshing = null;
        return api(cfg);
      } catch (e) {
        refreshing = null;
      }
    }
    return Promise.reject(err);
  }
);

export function errMsg(e, fallback = "Algo ha fallado. Inténtalo de nuevo.") {
  const d = e?.response?.data?.detail;
  if (!d) return e?.message && !e.response ? fallback : fallback;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => (x?.msg || JSON.stringify(x)).replace(/^Value error, /, "")).join(" ");
  return d.detail || d.msg || String(d);
}
