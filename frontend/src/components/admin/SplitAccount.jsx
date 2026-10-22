import { useState } from "react";
import { toast } from "sonner";
import { ArrowRightLeft, Loader2, UserRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export const goToClient = async (id) => {
  try { await api.post(`/admin/users/${id}/impersonate`); window.location.href = "/app"; }
  catch (e) { toast.error(errMsg(e)); }
};

export function SwitchToClient({ className = "" }) {
  const { user } = useAuth();
  if (!user?.admin_only || !user?.client_id) return null;
  return (
    <button onClick={() => goToClient(user.client_id)} className={`flex shrink-0 items-center gap-3 rounded-xl border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-700 transition-colors hover:bg-blue-100 ${className}`} data-testid="switch-to-client-button">
      <UserRound className="h-4 w-4" /> Mi cuenta de llamadas
    </button>
  );
}

export function SplitAccount() {
  const { user } = useAuth();
  const [email, setEmail] = useState("ed0.2580@gmail.com");
  const [busy, setBusy] = useState(false);
  if (!user || user.admin_only) return null;
  const run = async () => {
    if (!window.confirm(`Se creará la cuenta de cliente ${email} y se moverán a ella tus agentes, leads, citas, números y ajustes. Tu cuenta ${user.email} quedará solo para administrar. ¿Continuar?`)) return;
    setBusy(true);
    try {
      const r = await api.post("/admin/split-account", { email });
      toast.success(`Cuenta de cliente ${r.data.email} creada`);
      window.location.href = "/app/admin";
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <Panel className="space-y-3 lg:col-span-2" data-testid="split-account-panel">
      <div className="flex items-center gap-2"><ArrowRightLeft className="h-5 w-5 text-blue-600" /><h3 className="text-lg font-semibold text-white">Separar tu cuenta de administrador y tu cuenta de llamadas</h3></div>
      <p className="text-sm text-slate-400">Se crea una cuenta de cliente normal con tus agentes, leads, citas, números y ajustes actuales. Entrarás en ella con este email y <b>tu misma contraseña</b>, o desde aquí con el botón «Mi cuenta de llamadas». Tendrá su plan y sus minutos como cualquier cliente: asígnale un plan después en la lista de cuentas.</p>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input value={email} onChange={(e) => setEmail(e.target.value)} className="bg-slate-950/60" data-testid="split-account-email-input" />
        <Button onClick={run} disabled={busy || !email.includes("@")} className="rounded-full" data-testid="split-account-button">{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Separar cuentas</Button>
      </div>
    </Panel>
  );
}
