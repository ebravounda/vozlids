import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Download, History, Loader2, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Switch } from "@/components/ui/switch";
import { api, errMsg } from "@/lib/api";
import { fmtDate } from "@/lib/constants";

export const downloadJson = (data, name) => {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
  Object.assign(document.createElement("a"), { href: url, download: name }).click();
  URL.revokeObjectURL(url);
};

const statusCls = (s) => (s >= 500 ? "text-rose-300" : s >= 400 ? "text-amber-300" : "text-emerald-300");

function LogRows({ rows }) {
  if (!rows.length) return <p className="py-6 text-center text-sm text-slate-500" data-testid="key-logs-empty">Sin peticiones en los últimos 30 días.</p>;
  return (
    <div className="max-h-[50vh] overflow-y-auto rounded-xl border border-slate-800" data-testid="key-logs-list">
      {rows.map((r) => (
        <div key={r.request_id + r.at} className="grid grid-cols-[3.5rem_1fr_3rem_4rem] gap-2 border-b border-slate-800/70 px-3 py-2 font-mono text-xs last:border-0">
          <span className="text-blue-300">{r.method}</span>
          <span className="truncate text-slate-200" title={`${r.path} · ${r.request_id} · ${r.ip}`}>{r.path}<span className="block text-[10px] text-slate-500">{fmtDate(r.at)} · {r.ip}</span></span>
          <span className={statusCls(r.status)}>{r.status}</span>
          <span className="text-right text-slate-400">{r.duration_ms} ms</span>
        </div>
      ))}
    </div>
  );
}

export function KeyLogs({ k, onClose }) {
  const [d, setD] = useState(null);
  const [errors, setErrors] = useState(false);
  const load = (e) => api.get(`/privacy/keys/${k.id}/requests`, { params: { errors_only: e, limit: 200 } }).then((r) => setD(r.data)).catch((x) => toast.error(errMsg(x)));
  useEffect(() => { load(false); }, [k.id]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl border-slate-800 bg-slate-950" data-testid="key-logs-dialog">
        <DialogHeader><DialogTitle className="text-white">Historial de peticiones · {k.name}</DialogTitle>
          <DialogDescription>Se conserva {d?.summary?.days || 30} días y se borra automáticamente.</DialogDescription></DialogHeader>
        {d && <div className="grid grid-cols-3 gap-2 text-center" data-testid="key-logs-summary">
          {[["Peticiones", d.summary.total], ["Errores", d.summary.errors], ["Media", `${d.summary.avg_ms} ms`]].map(([l, v]) => <div key={l} className="rounded-xl border border-slate-800 p-2"><p className="text-[10px] uppercase text-slate-500">{l}</p><p className="font-mono text-white">{v}</p></div>)}
        </div>}
        <label className="flex items-center gap-2 text-xs text-slate-300"><Switch checked={errors} onCheckedChange={(v) => { setErrors(v); load(v); }} data-testid="key-logs-errors-switch" />Solo errores (4xx/5xx)</label>
        {d ? <LogRows rows={d.data} /> : <Loader2 className="mx-auto h-5 w-5 animate-spin text-slate-400" />}
      </DialogContent>
    </Dialog>
  );
}

export const LogsButton = ({ onClick, id }) => <Button size="sm" variant="outline" onClick={onClick} className="rounded-full" data-testid={`dev-key-logs-${id}`}><History className="mr-1 h-4 w-4" />Historial</Button>;

export function SubjectActions({ subject, onErased, compact = false }) {
  const [busy, setBusy] = useState("");
  const [ask, setAsk] = useState(false);
  const exp = async () => {
    setBusy("export");
    try { const r = await api.post("/privacy/export", subject); downloadJson(r.data, `datos-rgpd-${(subject.phone || subject.email).replace(/[^\w]+/g, "")}.json`); toast.success(`Exportadas ${r.data.calls.length} llamadas`); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(""); }
  };
  const erase = async () => {
    setBusy("erase");
    try { const r = await api.post("/privacy/erase", subject); toast.success(`Borrado: ${r.data.deleted.calls} llamadas, ${r.data.deleted.appointments} citas`); onErased?.(r.data); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(""); setAsk(false); }
  };
  const cls = compact ? "rounded-full text-xs" : "rounded-full";
  return (
    <div className="flex flex-wrap gap-2">
      <Button size="sm" variant="outline" onClick={exp} disabled={!!busy} className={cls} data-testid="rgpd-export-button">{busy === "export" ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Download className="mr-1 h-4 w-4" />}Exportar datos</Button>
      <Button size="sm" variant="outline" onClick={() => setAsk(true)} disabled={!!busy} className={`${cls} border-rose-500/40 text-rose-300 hover:text-rose-200`} data-testid="rgpd-erase-button"><Trash2 className="mr-1 h-4 w-4" />Borrar datos</Button>
      <AlertDialog open={ask} onOpenChange={setAsk}>
        <AlertDialogContent className="border-slate-800 bg-slate-950" data-testid="rgpd-erase-dialog">
          <AlertDialogHeader><AlertDialogTitle className="text-white">¿Borrar todos los datos de este contacto?</AlertDialogTitle>
            <AlertDialogDescription>Se eliminan definitivamente sus llamadas, transcripciones, grabaciones, citas y llamadas programadas de {subject.phone || subject.email}. No se puede deshacer. Si está en tu lista de “No llamar” se mantiene ahí.</AlertDialogDescription></AlertDialogHeader>
          <AlertDialogFooter><AlertDialogCancel data-testid="rgpd-erase-cancel">Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={(e) => { e.preventDefault(); erase(); }} className="bg-rose-600 hover:bg-rose-500" data-testid="rgpd-erase-confirm">{busy === "erase" && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}Borrar definitivamente</AlertDialogAction></AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
