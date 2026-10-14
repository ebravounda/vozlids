import { useEffect, useState } from "react";
import { toast } from "sonner";
import { CreditCard, Loader2, Mic, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";

export function StripeSettings() {
  const [s, setS] = useState(null);
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () => api.get("/admin/stripe").then((r) => setS(r.data));
  useEffect(() => { load(); }, []);
  const save = async () => {
    setBusy(true);
    try { const r = await api.put("/admin/stripe", { secret_key: key }); toast.success(`Stripe conectado (${r.data.mode === "live" ? "modo real" : "modo pruebas"})`); setKey(""); load(); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const disconnect = async () => { if (!window.confirm("¿Desconectar tu cuenta de Stripe? Los nuevos pagos usarán el modo de pruebas.")) return; await api.delete("/admin/stripe"); load(); };
  if (!s) return null;
  return (
    <Panel className="space-y-4" data-testid="stripe-settings-panel">
      <div className="flex items-center gap-2"><CreditCard className="h-5 w-5 text-emerald-300" /><h3 className="text-lg font-semibold text-white">Cobros con Stripe</h3></div>
      {s.connected ? (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-200" data-testid="stripe-status-connected">
          Conectado a <b>{s.account_name}</b> · {s.mode === "live" ? "modo real (cobros de verdad)" : "modo pruebas"} · clave …{s.key_last4}{s.webhook ? " · avisos automáticos activos" : ""}
        </div>
      ) : (
        <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200" data-testid="stripe-status-test">
          Sin cuenta propia: los clientes pagan en <b>modo pruebas</b> (tarjeta 4242 4242 4242 4242). Pega tu clave secreta para cobrar de verdad.
        </p>
      )}
      <Input type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder="sk_live_… o sk_test_…" className="bg-slate-950/60 font-mono" data-testid="stripe-secret-key-input" />
      <p className="text-xs text-slate-500">Stripe → Desarrolladores → Claves de API → Clave secreta. Al guardar se configuran solos los avisos de pago (webhook).</p>
      <div className="flex gap-2">
        <Button onClick={save} disabled={busy || key.length < 10} className="rounded-full" data-testid="stripe-save-button">{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}{s.connected ? "Cambiar clave" : "Conectar Stripe"}</Button>
        {s.connected && <Button variant="ghost" onClick={disconnect} className="rounded-full" data-testid="stripe-disconnect-button">Desconectar</Button>}
      </div>
    </Panel>
  );
}

const EMPTY = { name: "", gender: "Mujer", country: "ES", voice_id: "", tone: "" };

export function CustomVoices() {
  const [items, setItems] = useState([]);
  const [f, setF] = useState(EMPTY);
  const load = () => api.get("/voices/custom").then((r) => setItems(r.data));
  useEffect(() => { load(); }, []);
  const add = async () => { try { await api.post("/admin/voices", f); toast.success("Voz añadida"); setF(EMPTY); load(); } catch (e) { toast.error(errMsg(e)); } };
  const del = async (id) => { try { await api.delete(`/admin/voices/${id}`); load(); } catch (e) { toast.error(errMsg(e)); } };
  const sel = (k, opts) => (
    <Select value={f[k]} onValueChange={(v) => setF({ ...f, [k]: v })}>
      <SelectTrigger className="bg-slate-950/60" data-testid={`voice-${k}-select`}><SelectValue /></SelectTrigger>
      <SelectContent>{opts.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
    </Select>
  );
  return (
    <Panel className="space-y-4" data-testid="custom-voices-panel">
      <div className="flex items-center gap-2"><Mic className="h-5 w-5 text-emerald-300" /><h3 className="text-lg font-semibold text-white">Voces ElevenLabs con acento nativo</h3></div>
      <p className="text-xs text-slate-400">Añade voces de la biblioteca de ElevenLabs con acento de España o de Chile. Necesitas tu clave de ElevenLabs conectada en Vapi (Integraciones → ElevenLabs). Si la voz falla, la llamada usa una voz premium de respaldo.</p>
      {items.map((v) => (
        <div key={v.id} className="flex items-center justify-between rounded-xl border border-slate-800 p-3 text-sm" data-testid={`custom-voice-${v.id}`}>
          <span className="text-white">{v.name} <span className="text-xs text-slate-500">· {v.gender} · {v.country === "CL" ? "Chile" : "España"} · {v.voice_id}</span></span>
          <button onClick={() => del(v.id)} className="text-slate-500 hover:text-rose-300" data-testid={`custom-voice-delete-${v.id}`}><Trash2 className="h-4 w-4" /></button>
        </div>
      ))}
      <div className="grid grid-cols-2 gap-2">
        <Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Nombre (ej. Carmen)" className="bg-slate-950/60" data-testid="voice-name-input" />
        <Input value={f.voice_id} onChange={(e) => setF({ ...f, voice_id: e.target.value.trim() })} placeholder="ID de voz ElevenLabs" className="bg-slate-950/60 font-mono" data-testid="voice-id-input" />
        {sel("gender", [["Mujer", "Mujer"], ["Hombre", "Hombre"]])}
        {sel("country", [["ES", "España"], ["CL", "Chile"]])}
        <Input value={f.tone} onChange={(e) => setF({ ...f, tone: e.target.value })} placeholder="Tono (opcional)" className="col-span-2 bg-slate-950/60" data-testid="voice-tone-input" />
      </div>
      <Button onClick={add} disabled={!f.name || f.voice_id.length < 10} className="rounded-full" data-testid="voice-add-button"><Plus className="mr-2 h-4 w-4" /> Añadir voz</Button>
    </Panel>
  );
}
