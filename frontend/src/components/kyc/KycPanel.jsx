import { useEffect, useState } from "react";
import { toast } from "sonner";
import { CheckCircle2, FileUp, Loader2, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";
import { fmtDate } from "@/lib/constants";

export const KYC_ST = {
  sin_enviar: ["Pendiente de enviar", "bg-amber-100 text-amber-800"], rechazado: ["Rechazada: revisa y reenvía", "bg-rose-100 text-rose-800"],
  pendiente: ["En revisión", "bg-blue-100 text-blue-800"], enviado_zadarma: ["Aprobada · validando con el operador", "bg-blue-100 text-blue-800"],
  verificado: ["Verificada", "bg-emerald-100 text-emerald-800"], error: ["En revisión", "bg-blue-100 text-blue-800"],
};
export const ID_LABEL = { DNI: "DNI", NIE: "NIE", PASSPORT: "Pasaporte", NATIONAL_ID_CARD: "Cédula de identidad" };
export const FILE_LABEL = { id_front: "Documento · cara delantera", id_back: "Documento · cara trasera", passport: "Pasaporte · página de la foto", company_cert: "Certificado de la empresa" };
const FIELDS = [["first_name", "Nombre"], ["last_name", "Apellidos"], ["id_number", "Número de documento"], ["email", "Email de contacto"],
  ["phone", "Teléfono de contacto"], ["street", "Calle"], ["building_number", "Número"], ["zip_code", "Código postal"], ["city", "Ciudad"]];

async function shrink(file) {
  if (!file.type.startsWith("image/")) return file;
  const img = await createImageBitmap(file);
  const k = Math.min(1, 1800 / Math.max(img.width, img.height));
  const c = document.createElement("canvas");
  c.width = Math.round(img.width * k); c.height = Math.round(img.height * k);
  c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
  const blob = await new Promise((r) => c.toBlob(r, "image/jpeg", 0.85));
  return new File([blob], file.name.replace(/\.\w+$/, "") + ".jpg", { type: "image/jpeg" });
}

function Slot({ type, have, locked, onUpload }) {
  const [busy, setBusy] = useState(false);
  const pick = async (e) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    setBusy(true);
    try { await onUpload(type, await shrink(f)); } finally { setBusy(false); }
  };
  return (
    <label className={`flex items-center gap-3 rounded-xl border p-3 text-sm ${have ? "border-emerald-300 bg-emerald-50" : "border-dashed border-slate-300"} ${locked ? "" : "cursor-pointer hover:border-slate-400"}`} data-testid={`kyc-slot-${type}`}>
      {busy ? <Loader2 className="h-5 w-5 animate-spin text-slate-400" /> : have ? <CheckCircle2 className="h-5 w-5 text-emerald-600" /> : <FileUp className="h-5 w-5 text-slate-400" />}
      <span className="flex-1"><span className="block font-medium">{FILE_LABEL[type]}</span><span className="text-xs text-slate-500">{have ? `Subido: ${have.name}` : "Foto nítida (o PDF), que se lean todos los datos"}</span></span>
      {!locked && <input type="file" accept="image/*,application/pdf" capture="environment" className="hidden" onChange={pick} data-testid={`kyc-file-${type}`} />}
    </label>
  );
}

export function KycPanel() {
  const [d, setD] = useState(null);
  const [f, setF] = useState(null);
  const [busy, setBusy] = useState("");
  const apply = (data) => { setD(data); setF((cur) => cur || { ...data, kind: data.kind || "persona", nationality: data.nationality || data.country, id_type: data.id_type || data.id_types[0] }); };
  useEffect(() => { api.get("/kyc").then((r) => apply(r.data)).catch(() => {}); }, []);
  if (!d || !f || (!d.required && d.status === "sin_enviar" && !d.first_name)) return null;
  const locked = ["pendiente", "enviado_zadarma", "verificado", "error"].includes(d.status);
  const [label, cls] = KYC_ST[d.status] || KYC_ST.sin_enviar;
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const run = async (key, fn) => { setBusy(key); try { const r = await fn(); setD(r.data); return true; } catch (e) { toast.error(errMsg(e)); return false; } finally { setBusy(""); } };
  const body = () => Object.fromEntries(["kind", "nationality", "id_type", "organization", "organization_reg_number", ...FIELDS.map(([k]) => k)].map((k) => [k, (f[k] || "").trim()]));
  const save = () => run("save", () => api.put("/kyc", body())).then((ok) => ok && toast.success("Datos guardados"));
  const upload = (type, file) => { const fd = new FormData(); fd.append("file", file); return run(type, () => api.post(`/kyc/files?type=${type}`, fd)); };
  const submit = async () => { if (await run("save", () => api.put("/kyc", body())) && await run("submit", () => api.post("/kyc/submit"))) toast.success("Documentos enviados. Te avisaremos por email."); };
  const need = f.id_type === "PASSPORT" ? ["passport"] : ["id_front", "id_back"];
  const files = [...need, ...(f.kind === "empresa" ? ["company_cert"] : [])];
  return (
    <Panel className="space-y-5" data-testid="kyc-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2"><ShieldCheck className="h-5 w-5 text-blue-600" /><h3 className="text-lg font-semibold">Titular de tus líneas</h3></div>
        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${cls}`} data-testid="kyc-status">{label}</span>
      </div>
      <p className="rounded-xl border border-blue-100 bg-blue-50 p-4 text-sm leading-relaxed text-slate-700" data-testid="kyc-notice">{d.notice}</p>
      {d.deadline && ["sin_enviar", "rechazado"].includes(d.status) && <p className="text-sm font-semibold text-amber-700" data-testid="kyc-deadline">Tu línea sigue funcionando. Envía tus documentos antes del {fmtDate(d.deadline)}.</p>}
      {d.status === "rechazado" && d.reject_reason && <p className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800" data-testid="kyc-reject-reason">Motivo: {d.reject_reason}</p>}
      {locked ? <p className="text-sm text-slate-600" data-testid="kyc-locked-note">{d.status === "verificado" ? "Tu identidad está verificada: tus líneas están a tu nombre." : "Hemos recibido tus documentos. Te avisaremos por email cuando estén revisados."}</p> : <>
        <div className="grid grid-cols-2 gap-2">
          {[["persona", "Soy una persona"], ["empresa", "Soy una empresa"]].map(([k, l]) => (
            <button key={k} type="button" onClick={() => setF({ ...f, kind: k })} data-testid={`kyc-kind-${k}`}
              className={`rounded-xl border p-3 text-sm font-semibold transition-colors ${f.kind === k ? "border-blue-500 bg-blue-50 text-blue-700" : "border-slate-200 hover:border-slate-400"}`}>{l}</button>
          ))}
        </div>
        {f.kind === "empresa" && <div className="grid gap-2 sm:grid-cols-2">
          <Input value={f.organization || ""} onChange={set("organization")} placeholder="Nombre de la empresa" data-testid="kyc-organization" />
          <Input value={f.organization_reg_number || ""} onChange={set("organization_reg_number")} placeholder={d.country === "CL" ? "RUT de la empresa" : "CIF de la empresa"} data-testid="kyc-org-number" />
          <p className="text-xs text-slate-500 sm:col-span-2">Los datos personales de abajo son del representante legal.</p>
        </div>}
        <div className="grid gap-2 sm:grid-cols-2">
          <Select value={f.id_type} onValueChange={(v) => setF({ ...f, id_type: v })}>
            <SelectTrigger data-testid="kyc-id-type"><SelectValue /></SelectTrigger>
            <SelectContent>{d.id_types.map((t) => <SelectItem key={t} value={t}>{ID_LABEL[t]}</SelectItem>)}</SelectContent>
          </Select>
          <Input value={f.nationality || ""} onChange={(e) => setF({ ...f, nationality: e.target.value.toUpperCase().slice(0, 2) })} placeholder="Nacionalidad (ES, CL, AR…)" data-testid="kyc-nationality" />
          {FIELDS.map(([k, l]) => <Input key={k} value={f[k] || ""} onChange={set(k)} placeholder={k === "id_number" && d.country === "CL" && f.id_type !== "PASSPORT" ? "RUT (ej. 12.345.678-9)" : l} data-testid={`kyc-${k}`} />)}
        </div>
        <Button variant="outline" onClick={save} disabled={!!busy} className="rounded-full" data-testid="kyc-save-button">{busy === "save" && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Guardar datos</Button>
      </>}
      <div className="space-y-2">
        <p className="text-sm font-semibold">Fotos de tus documentos</p>
        {(locked ? d.required_files : files).map((t) => <Slot key={t} type={t} have={d.files.find((x) => x.type === t)} locked={locked} onUpload={upload} />)}
      </div>
      {!locked && <Button onClick={submit} disabled={!!busy} className="w-full rounded-full" data-testid="kyc-submit-button">{busy === "submit" && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Enviar para revisión</Button>}
      <p className="text-xs text-slate-500">Tus documentos se guardan cifrados y solo los ve el equipo de VozLeads para dar de alta tus líneas ante el operador. Puedes pedir su borrado en «Privacidad».</p>
    </Panel>
  );
}

export function KycBanner() {
  const [d, setD] = useState(null);
  useEffect(() => { api.get("/kyc").then((r) => setD(r.data)).catch(() => {}); }, []);
  if (!d?.required || !["sin_enviar", "rechazado"].includes(d.status)) return null;
  return (
    <a href="/app/numero" className="flex items-center justify-center gap-2 bg-amber-50 px-4 py-2 text-center text-sm font-semibold text-amber-800 hover:bg-amber-100" data-testid="kyc-banner">
      <ShieldCheck className="h-4 w-4 shrink-0" />{d.status === "rechazado" ? "Revisa tus documentos: necesitamos que corrijas algo" : "Por ley, sube tus documentos de identidad para tener tus líneas a tu nombre"}{d.deadline ? ` · antes del ${fmtDate(d.deadline)}` : ""}
    </a>
  );
}
