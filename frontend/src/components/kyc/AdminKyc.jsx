import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";
import { fmtDate } from "@/lib/constants";
import { FILE_LABEL, ID_LABEL, KYC_ST } from "@/components/kyc/KycPanel";

function DocImage({ tid, f }) {
  const [url, setUrl] = useState("");
  useEffect(() => {
    let u = "";
    api.get(`/admin/kyc/${tid}/files/${f.index}`, { responseType: "blob" }).then((r) => { u = URL.createObjectURL(r.data); setUrl(u); }).catch(() => {});
    return () => u && URL.revokeObjectURL(u);
  }, [tid, f.index]);
  return (
    <a href={url || undefined} target="_blank" rel="noreferrer" className="block rounded-xl border border-slate-200 p-2" data-testid={`admin-kyc-file-${f.type}`}>
      <p className="mb-1 text-xs font-semibold text-slate-600">{FILE_LABEL[f.type]}</p>
      {!url ? <Loader2 className="h-5 w-5 animate-spin text-slate-400" /> : f.name.toLowerCase().endsWith(".pdf") ? <span className="text-sm text-blue-600 underline">Abrir PDF</span> : <img src={url} alt={FILE_LABEL[f.type]} className="max-h-56 w-full rounded-lg object-contain" />}
    </a>
  );
}

function Detail({ r, onClose, reload }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState("");
  const act = async (what) => {
    if (what === "reject" && reason.trim().length < 3) return toast.error("Escribe el motivo para el cliente");
    setBusy(what);
    try {
      const res = await api.post(`/admin/kyc/${r.tenant_id}/${what}`, what === "reject" ? { reason } : undefined);
      toast.success(what === "approve" ? "Aprobado y enviado a Zadarma" : what === "reject" ? "Rechazado: el cliente recibirá un email" : res.data.verified ? "Zadarma ya lo ha verificado" : `Zadarma: ${res.data.summary || "aún en revisión"}`);
      reload(); if (what !== "check") onClose();
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(""); }
  };
  const rows = [["Tipo", r.kind === "empresa" ? `Empresa · ${r.organization} · ${r.organization_reg_number}` : "Persona"], ["Titular", `${r.first_name} ${r.last_name}`],
    ["Documento", `${ID_LABEL[r.id_type] || r.id_type} ${r.id_number}`], ["Nacionalidad", r.nationality], ["Dirección", `${r.street} ${r.building_number}, ${r.zip_code} ${r.city} (${r.country})`],
    ["Contacto", `${r.email} · ${r.phone}`], ["Zadarma", r.zadarma_status || "—"]];
  return (
    <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto bg-white" data-testid="admin-kyc-dialog">
      <DialogHeader><DialogTitle>{r.business} · {KYC_ST[r.status]?.[0]}</DialogTitle></DialogHeader>
      <dl className="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-[140px_1fr]">{rows.map(([k, v]) => <div key={k} className="contents"><dt className="text-slate-500">{k}</dt><dd className="font-medium">{v}</dd></div>)}</dl>
      <div className="grid gap-3 sm:grid-cols-2">{r.files.map((f) => <DocImage key={f.index} tid={r.tenant_id} f={f} />)}</div>
      <div className="flex flex-wrap gap-2">
        {["pendiente", "error"].includes(r.status) && <Button onClick={() => act("approve")} disabled={!!busy} className="rounded-full" data-testid="admin-kyc-approve">{busy === "approve" && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Aprobar y enviar a Zadarma</Button>}
        {["enviado_zadarma", "verificado"].includes(r.status) && <Button variant="outline" onClick={() => act("check")} disabled={!!busy} className="rounded-full" data-testid="admin-kyc-check">{busy === "check" && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Comprobar en Zadarma</Button>}
      </div>
      {r.status !== "verificado" && <div className="space-y-2 border-t border-slate-200 pt-3">
        <Textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} placeholder="Motivo del rechazo (lo verá el cliente): ej. la foto del reverso está borrosa" data-testid="admin-kyc-reason" />
        <Button variant="ghost" onClick={() => act("reject")} disabled={!!busy} className="rounded-full text-rose-600" data-testid="admin-kyc-reject">Rechazar y pedir corrección</Button>
      </div>}
    </DialogContent>
  );
}

export function AdminKyc() {
  const [rows, setRows] = useState([]);
  const [openId, setOpenId] = useState(null);
  const open = rows.find((r) => r.tenant_id === openId);
  const setOpen = (r) => setOpenId(r ? r.tenant_id : null);
  const load = () => api.get("/admin/kyc").then((r) => setRows(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);
  const pending = rows.filter((r) => r.status === "pendiente").length;
  return (
    <Panel className="space-y-3 lg:col-span-2" id="admin-kyc" data-testid="admin-kyc-panel">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2"><ShieldCheck className="h-5 w-5 text-emerald-300" /><h3 className="text-lg font-semibold text-white">Documentos de los titulares</h3></div>
        {pending > 0 && <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800" data-testid="admin-kyc-pending-count">{pending} por revisar</span>}
      </div>
      <p className="text-xs text-slate-400">Cada cliente sube sus datos y las fotos de su documento. Al aprobar, se crea su grupo de documentos en Zadarma y sus números se compran a su nombre. Sin documentos aprobados no se compran números nuevos.</p>
      {!rows.length && <p className="text-sm text-slate-500" data-testid="admin-kyc-empty">Aún no hay clientes con verificación.</p>}
      {rows.map((r) => {
        const [l, c] = r.status === "error" ? ["Error con Zadarma", "bg-rose-100 text-rose-800"] : KYC_ST[r.status] || KYC_ST.sin_enviar;
        return (
          <button key={r.tenant_id} type="button" onClick={() => setOpen(r)} className="flex w-full flex-wrap items-center gap-3 rounded-xl border border-slate-800 p-3 text-left text-sm hover:border-slate-600" data-testid={`admin-kyc-row-${r.tenant_id}`}>
            <span className="min-w-0 flex-1"><span className="block text-white">{r.business}</span><span className="text-xs text-slate-500">{r.country} · {r.first_name ? `${r.first_name} ${r.last_name}` : "sin datos"}{r.submitted_at ? ` · enviado ${fmtDate(r.submitted_at)}` : ""}</span></span>
            {r.overdue && <span className="rounded-full bg-rose-100 px-2 py-0.5 text-xs font-semibold text-rose-700">Plazo vencido</span>}
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${c}`}>{l}</span>
          </button>
        );
      })}
      <Dialog open={!!open} onOpenChange={(v) => !v && setOpen(null)}>{open && <Detail r={open} onClose={() => setOpen(null)} reload={load} />}</Dialog>
    </Panel>
  );
}
