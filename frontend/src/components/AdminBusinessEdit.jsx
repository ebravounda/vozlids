import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Pencil } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, errMsg } from "@/lib/api";

const FIELDS = [
  ["business_name", "Nombre del negocio", "Clínica Dental Sonrisa"], ["name", "Persona de contacto", "Laura Pérez"],
  ["email", "Email (también para entrar al panel)", "laura@negocio.com", "email"], ["contact_phone", "Teléfono de contacto", "+34 612 345 678", "tel"],
  ["sector", "Sector", "Inmobiliaria, taller, gimnasio…"], ["website", "Web", "www.negocio.com"],
  ["business_hours", "Horario de atención", "L–V 9:00–14:00 y 16:00–20:00"],
];

export function EditBusinessButton({ u, onSaved }) {
  const [open, setOpen] = useState(false);
  const [f, setF] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) { setF(null); api.get(`/admin/users/${u.id}/profile`).then((r) => setF(r.data)).catch((e) => toast.error(errMsg(e))); } }, [open, u.id]);
  const save = async () => {
    setBusy(true);
    try {
      const r = await api.put(`/admin/users/${u.id}/profile`, f);
      toast.success(r.data.stripe_updated === false ? "Datos guardados (no se pudo actualizar en Stripe)" : r.data.stripe_updated ? "Datos guardados y actualizados en Stripe" : "Datos guardados");
      setOpen(false); onSaved();
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <>
      <button onClick={() => setOpen(true)} className="ml-2 inline-flex items-center gap-1 rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-200 hover:border-emerald-500" data-testid={`admin-user-edit-${u.id}`}><Pencil className="h-3.5 w-3.5" /> Editar</button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="app-light max-w-lg bg-white text-slate-700" data-testid="edit-business-dialog">
          <DialogHeader>
            <DialogTitle className="text-slate-900">Editar datos del negocio</DialogTitle>
            <DialogDescription className="text-slate-500">{u.business_name} · {u.country === "CL" ? "Chile" : "España"}. Si tiene suscripción, el nombre, email y teléfono también se actualizan en Stripe.</DialogDescription>
          </DialogHeader>
          {!f ? <Loader2 className="mx-auto my-8 h-6 w-6 animate-spin text-slate-400" /> : (
            <div className="grid gap-3 sm:grid-cols-2">
              {FIELDS.map(([k, label, ph, type]) => (
                <label key={k} className={`space-y-1 ${k === "business_hours" ? "sm:col-span-2" : ""}`}>
                  <span className="text-xs font-medium text-slate-600">{label}</span>
                  <Input type={type || "text"} value={f[k]} placeholder={ph} onChange={(e) => setF({ ...f, [k]: e.target.value })} className="border-slate-200 bg-white text-slate-900" data-testid={`edit-business-${k}`} />
                </label>
              ))}
              <div className="flex justify-end gap-2 pt-2 sm:col-span-2">
                <Button variant="ghost" onClick={() => setOpen(false)} data-testid="edit-business-cancel">Cancelar</Button>
                <Button onClick={save} disabled={busy || !f.business_name || !f.name || !f.email} className="rounded-full bg-blue-600 text-white hover:bg-blue-700" data-testid="edit-business-save">{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Guardar cambios</Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
