import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Loader2, Mic, Trash2, Upload } from "lucide-react";
import { api, errMsg } from "@/lib/api";

export const CustomAmbiences = ({ value, onSelect }) => {
  const [items, setItems] = useState([]);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);

  const load = () => api.get("/ambiences/custom").then((r) => setItems(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const upload = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setBusy(true);
    const fd = new FormData();
    fd.append("name", name.trim() || file.name.replace(/\.[^.]+$/, "").slice(0, 60));
    fd.append("file", file);
    try {
      const { data } = await api.post("/ambiences/custom", fd);
      toast.success("Grabación subida y limpiada de zumbidos");
      setName("");
      await load();
      onSelect(`custom:${data.id}`);
    } catch (err) { toast.error(errMsg(err)); }
    finally { setBusy(false); }
  };

  const remove = async (id) => {
    if (!window.confirm("¿Eliminar esta grabación? Los agentes que la usen pasarán a «Oficina real».")) return;
    await api.delete(`/ambiences/custom/${id}`).catch((err) => toast.error(errMsg(err)));
    if (value === `custom:${id}`) onSelect("oficina_real");
    load();
  };

  return (
    <div className="space-y-2 rounded-xl border border-dashed border-slate-700 p-4" data-testid="custom-ambience-section">
      <p className="flex items-center gap-2 text-sm font-semibold text-white"><Mic className="h-4 w-4 text-emerald-400" /> Tu propia grabación de oficina</p>
      <p className="text-xs text-slate-500">Graba 1–3 minutos de tu oficina con el móvil (sin música) y súbela. Quitamos zumbidos y ruido grave automáticamente.</p>
      {items.map((it) => (
        <div key={it.id} className={`flex items-center justify-between rounded-lg border px-3 py-2 ${value === `custom:${it.id}` ? "border-emerald-500 bg-emerald-500/10" : "border-slate-800"}`}>
          <button type="button" onClick={() => onSelect(`custom:${it.id}`)} className="flex-1 text-left text-sm text-slate-200" data-testid={`custom-ambience-${it.id}`}>
            {it.name} <span className="text-xs text-slate-500">· {Math.round(it.duration)} s{it.shared ? " · biblioteca" : ""}</span>
          </button>
          <button type="button" onClick={() => remove(it.id)} className="p-1 text-slate-500 hover:text-rose-300" data-testid={`custom-ambience-delete-${it.id}`}><Trash2 className="h-4 w-4" /></button>
        </div>
      ))}
      <div className="flex gap-2 pt-1">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Nombre (ej. Oficina Madrid)" className="h-9 flex-1 rounded-lg border border-slate-700 bg-slate-950/60 px-3 text-sm text-white" data-testid="custom-ambience-name-input" />
        <input ref={fileRef} type="file" accept="audio/*,.m4a,.mp3,.wav,.ogg" className="hidden" onChange={upload} data-testid="custom-ambience-file-input" />
        <button type="button" disabled={busy} onClick={() => fileRef.current?.click()} className="inline-flex items-center gap-2 rounded-full bg-emerald-500 px-4 text-sm font-semibold text-slate-950 hover:bg-emerald-400 disabled:opacity-60" data-testid="custom-ambience-upload-button">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />} Subir audio
        </button>
      </div>
    </div>
  );
};
