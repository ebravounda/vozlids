import { useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, CheckCircle2, GitCompare, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { api, errMsg } from "@/lib/api";

const usd = (v, d = 4) => (v == null ? "—" : `$${v.toFixed(d)}`);
const mmss = (s) => (s == null ? "—" : `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`);
const STATUS = {
  ok: ["Coincide", "text-emerald-300"],
  diff: ["Diferente", "text-amber-300"],
  missing: ["No está en VozLeads", "text-rose-300"],
};

const Box = ({ label, value, tone = "text-white", testid }) => (
  <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3" data-testid={testid}>
    <p className="text-[10px] uppercase tracking-widest text-slate-500">{label}</p>
    <p className={`mt-1 font-mono text-lg font-semibold ${tone}`}>{value}</p>
  </div>
);

function Summary({ t }) {
  const diff = t.difference;
  const tone = Math.abs(diff) < 0.01 ? "text-emerald-300" : diff < 0 ? "text-rose-300" : "text-amber-300";
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Box label="Factura Zadarma" value={usd(t.zadarma)} testid="zc-total-zadarma" />
        <Box label="Panel VozLeads" value={usd(t.panel)} testid="zc-total-panel" />
        <Box label="Diferencia" value={`${diff > 0 ? "+" : ""}${usd(diff)}`} tone={tone} testid="zc-total-diff" />
        <Box label="Minutos Zadarma / panel" value={`${mmss(t.zadarma_seconds)} / ${mmss(Math.round(t.panel_seconds))}`} testid="zc-total-minutes" />
      </div>
      <p className="text-xs text-slate-400" data-testid="zc-counts">
        {t.ok} coinciden · {t.diff} con diferencia · <span className={t.missing ? "text-rose-300" : ""}>{t.missing} cobradas por Zadarma que no están en VozLeads</span> · {t.free} sin coste (ocupado, sin respuesta)
      </p>
      {diff < -0.01 && <p className="flex items-center gap-2 text-xs text-rose-300"><AlertTriangle className="h-4 w-4" /> El panel cuenta menos de lo que te cobra Zadarma: tus márgenes reales son algo menores.</p>}
    </div>
  );
}

function Row({ r }) {
  const [label, tone] = STATUS[r.status];
  return (
    <tr className="border-t border-slate-800" data-testid={`zc-row-${r.id}`}>
      <td className="p-2 text-xs text-slate-400">{r.start}</td>
      <td className="p-2"><p className="font-mono text-xs text-white">{r.to}</p><p className="text-[11px] text-slate-500">{r.destination}{r.business ? ` · ${r.business}` : ""}</p></td>
      <td className="p-2 font-mono text-xs">{mmss(r.zadarma_seconds)} / {mmss(r.panel_seconds)}</td>
      <td className={`p-2 font-mono text-xs ${r.rate_mismatch ? "text-amber-300" : "text-slate-300"}`}>{usd(r.zadarma_rate, 3)} / {usd(r.panel_rate, 3)}</td>
      <td className="p-2 font-mono text-xs">{usd(r.zadarma_cost)}</td>
      <td className="p-2 font-mono text-xs">{usd(r.panel_cost)}{r.panel_cost != null && <span className={`ml-1 text-[10px] ${r.line_real ? "text-emerald-400" : "text-slate-500"}`}>{r.line_real ? "real" : "est."}</span>}</td>
      <td className={`p-2 text-xs font-semibold ${tone}`} data-testid={`zc-row-status-${r.id}`}>{label}{r.status === "diff" ? ` (${r.diff > 0 ? "+" : ""}${r.diff.toFixed(4)})` : ""}</td>
    </tr>
  );
}

export function ZadarmaCompare({ days }) {
  const [open, setOpen] = useState(false);
  const [d, setD] = useState(null);
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setOpen(true); setBusy(true); setD(null);
    try { const { data } = await api.get("/admin/costs/zadarma-compare", { params: { days } }); setD(data); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <>
      <Button variant="outline" onClick={run} className="rounded-full border-slate-700 bg-transparent" data-testid="zadarma-compare-button">
        <GitCompare className="mr-2 h-4 w-4" /> Comparar con Zadarma
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90vh] max-w-5xl overflow-y-auto border-slate-800 bg-slate-900" data-testid="zadarma-compare-dialog">
          <DialogHeader>
            <DialogTitle className="text-white">Zadarma frente al panel</DialogTitle>
            <DialogDescription className="text-slate-400">Cada llamada facturada por Zadarma comparada con el coste de línea que cuenta VozLeads (máximo 29 días).</DialogDescription>
          </DialogHeader>
          {busy && <p className="flex items-center gap-2 text-sm text-slate-400"><Loader2 className="h-4 w-4 animate-spin" /> Descargando llamadas de Zadarma…</p>}
          {d?.error && <p className="text-sm text-rose-300" data-testid="zadarma-compare-error">{d.error}</p>}
          {d && !d.error && (
            <div className="space-y-4">
              <Summary t={d.totals} />
              {d.rows.length ? (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[820px] text-sm" data-testid="zadarma-compare-table">
                    <thead className="text-left text-[10px] uppercase tracking-wider text-slate-500"><tr>{["Fecha", "Destino", "Duración Zadarma / panel", "Tarifa Zadarma / panel", "Zadarma", "Panel", "Estado"].map((h) => <th key={h} className="p-2 font-medium">{h}</th>)}</tr></thead>
                    <tbody>{d.rows.map((r) => <Row key={r.id} r={r} />)}</tbody>
                  </table>
                </div>
              ) : <p className="flex items-center gap-2 text-sm text-emerald-300"><CheckCircle2 className="h-4 w-4" /> No hay llamadas con coste en este periodo.</p>}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
