import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Loader2, Pause, Phone, Play, Plus, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";

const NUM_ST = { activo: "Activo", comprando: "Comprando…", error: "Error", liberado: "Liberado", sin_numero: "Sin número" };
const sel = (value, onChange, opts, testid, placeholder = "Elegir") => (
  <Select value={value || "none"} onValueChange={(v) => onChange(v === "none" ? "" : v)}>
    <SelectTrigger className="bg-slate-950/60" data-testid={testid}><SelectValue placeholder={placeholder} /></SelectTrigger>
    <SelectContent><SelectItem value="none">{placeholder}</SelectItem>{opts.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
  </Select>
);

function CountryOptions({ c, cfg, setCfg }) {
  const [o, setO] = useState(null);
  const load = () => api.get(`/admin/zadarma/options?country=${c}`).then((r) => setO(r.data)).catch((e) => toast.error(errMsg(e)));
  const k = c.toLowerCase();
  return (
    <div className="space-y-2 rounded-xl border border-slate-800 p-3" data-testid={`zadarma-options-${k}`}>
      <div className="flex items-center justify-between"><p className="text-sm font-semibold text-white">{c === "ES" ? "España (+34)" : "Chile (+56)"}</p>
        <button onClick={load} className="text-xs text-emerald-300 hover:underline" data-testid={`zadarma-load-options-${k}`}>Cargar ciudades</button></div>
      {o ? <>
        {sel(cfg[`direction_${k}`], (v) => setCfg({ ...cfg, [`direction_${k}`]: v }), o.directions.map((d) => [d.id, `${d.name} · ${d.monthly_fee} ${d.currency}/mes${d.documents ? " · pide documentos" : ""}`]), `zadarma-direction-${k}`, "Ciudad / tipo de número")}
        {sel(cfg[`docs_${k}`], (v) => setCfg({ ...cfg, [`docs_${k}`]: v }), o.document_groups.map((g) => [g.id, `${g.name}${g.status ? ` · ${g.status}` : ""}`]), `zadarma-docs-${k}`, "Documentos (si los pide)")}
      </> : <p className="text-xs text-slate-500">{cfg[`direction_${k}`] ? `Ciudad elegida: ${cfg[`direction_${k}`]}` : "Sin ciudad elegida"}</p>}
    </div>
  );
}

export function ZadarmaSettings() {
  const [cfg, setCfg] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = () => api.get("/admin/zadarma").then((r) => setCfg({ ...r.data, key: "", secret: "" }));
  useEffect(() => { load(); }, []);
  const save = async () => {
    setBusy(true);
    try { const r = await api.put("/admin/zadarma", cfg); setCfg({ ...r.data, key: "", secret: "" }); toast.success("Zadarma guardado"); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  if (!cfg) return null;
  return (
    <Panel className="space-y-4 lg:col-span-2" data-testid="zadarma-api-panel">
      <div className="flex items-center gap-2"><Phone className="h-5 w-5 text-emerald-300" /><h3 className="text-lg font-semibold text-white">Números automáticos con Zadarma</h3></div>
      <p className="text-xs text-slate-400">Cuando un cliente paga su plan se compra un número de su país en tu cuenta Zadarma, se crea su línea SIP y se conecta a Vapi para llamar y contestar. Si deja de pagar, se desactiva la renovación y se desconecta al momento.</p>
      {cfg.connected
        ? <p className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-200" data-testid="zadarma-status-connected">Conectado · clave …{cfg.key_last4} · saldo {cfg.balance}</p>
        : <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200" data-testid="zadarma-status-missing">Sin conectar. En my.zadarma.com → Configuración → API y webhooks, genera la clave y el secreto y pégalos aquí.</p>}
      <div className="grid gap-2 md:grid-cols-2">
        <Input value={cfg.key} onChange={(e) => setCfg({ ...cfg, key: e.target.value })} placeholder={cfg.connected ? "Nueva clave (opcional)" : "Clave (Key)"} className="bg-slate-950/60 font-mono" data-testid="zadarma-key-input" />
        <Input type="password" value={cfg.secret} onChange={(e) => setCfg({ ...cfg, secret: e.target.value })} placeholder="Secreto (Secret)" className="bg-slate-950/60 font-mono" data-testid="zadarma-secret-input" />
      </div>
      {cfg.connected && <div className="grid gap-3 md:grid-cols-2"><CountryOptions c="ES" cfg={cfg} setCfg={setCfg} /><CountryOptions c="CL" cfg={cfg} setCfg={setCfg} /></div>}
      <label className="flex items-center gap-3 text-sm text-slate-300"><Switch checked={cfg.buy_on_test} onCheckedChange={(v) => setCfg({ ...cfg, buy_on_test: v })} data-testid="zadarma-buy-on-test-switch" />Comprar número también con pagos de prueba de Stripe (cuesta dinero real en Zadarma)</label>
      <Button onClick={save} disabled={busy} className="rounded-full" data-testid="zadarma-save-button">{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Guardar</Button>
      <NumbersList connected={cfg.connected} />
    </Panel>
  );
}

function NumbersList({ connected }) {
  const [rows, setRows] = useState([]);
  const [users, setUsers] = useState([]);
  const [pick, setPick] = useState("");
  const [busy, setBusy] = useState("");
  const load = () => { api.get("/admin/numbers").then((r) => setRows(r.data)); api.get("/admin/users").then((r) => setUsers(r.data.filter((u) => u.role !== "admin"))); };
  useEffect(() => { load(); }, []);
  const act = async (uid, what) => {
    if (what === "release" && !window.confirm("¿Liberar este número? El cliente dejará de poder llamar y recibir llamadas en él.")) return;
    setBusy(uid);
    try { const r = await api.post(`/admin/numbers/${uid}/${what}`); r.data.status === "error" ? toast.error(r.data.error) : toast.success(what === "release" ? "Número liberado" : `Número ${r.data.number} activo`); load(); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(""); }
  };
  return (
    <div className="space-y-3 border-t border-slate-800 pt-4" data-testid="tenant-numbers-list">
      <p className="text-sm font-semibold text-white">Números de clientes</p>
      {rows.length === 0 && <p className="text-xs text-slate-500">Aún no hay números asignados.</p>}
      {rows.map((r) => (
        <div key={r.tenant_id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-800 p-3 text-sm" data-testid={`tenant-number-${r.tenant_id}`}>
          <span className="text-white">{r.business_name || r.email} <span className="font-mono text-xs text-slate-400">{r.number || "—"}</span>
            <span className={`ml-2 text-xs ${r.status === "activo" ? "text-emerald-300" : r.status === "error" ? "text-rose-300" : "text-slate-400"}`}>{NUM_ST[r.status] || r.status}</span>
            {r.error && <span className="block text-xs text-rose-300/80">{r.error}</span>}</span>
          <span className="flex gap-2">
            {r.status !== "activo" && connected && <Button size="sm" variant="outline" disabled={busy === r.tenant_id} onClick={() => act(r.tenant_id, "provision")} data-testid={`tenant-number-retry-${r.tenant_id}`}>Comprar número</Button>}
            {["activo", "error"].includes(r.status) && <Button size="sm" variant="ghost" className="text-rose-300" disabled={busy === r.tenant_id} onClick={() => act(r.tenant_id, "release")} data-testid={`tenant-number-release-${r.tenant_id}`}>Liberar</Button>}
          </span>
        </div>
      ))}
      {connected && (
        <div className="flex gap-2">
          <div className="flex-1">{sel(pick, setPick, users.map((u) => [u.id, `${u.business_name || u.email} · ${u.country}`]), "tenant-number-user-select", "Asignar número a un cliente…")}</div>
          <Button disabled={!pick || !!busy} onClick={() => act(pick, "provision")} className="rounded-full" data-testid="tenant-number-assign-button">{busy === pick && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Asignar</Button>
        </div>
      )}
    </div>
  );
}

function LibraryVoice({ v, country, onAdded, playing, setPlaying }) {
  const [name, setName] = useState(v.name.split(/[ -]/)[0].slice(0, 30));
  const [busy, setBusy] = useState(false);
  const add = async () => {
    setBusy(true);
    try {
      await api.post("/admin/elevenlabs/library/add", { public_owner_id: v.public_owner_id, voice_id: v.voice_id, name, gender: v.gender === "male" ? "Hombre" : "Mujer", country, tone: [v.accent, v.age].filter(Boolean).join(", ").slice(0, 80) });
      toast.success(`Voz ${name} añadida para ${country === "CL" ? "Chile" : "España"}`); onAdded();
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-800 p-3 text-sm" data-testid={`library-voice-${v.voice_id}`}>
      <button onClick={() => setPlaying(playing === v.voice_id ? "" : v.voice_id)} className="grid h-8 w-8 place-items-center rounded-full bg-emerald-500 text-slate-950" data-testid={`library-voice-play-${v.voice_id}`}>{playing === v.voice_id ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}</button>
      <div className="min-w-0 flex-1"><p className="truncate text-white">{v.name}</p><p className="truncate text-xs text-slate-500">{v.gender === "male" ? "Hombre" : "Mujer"} · {v.accent} · {v.age} · {v.uses} usos{v.free ? "" : " · requiere plan de pago"}</p></div>
      <Input value={name} onChange={(e) => setName(e.target.value)} className="h-8 w-28 bg-slate-950/60" data-testid={`library-voice-name-${v.voice_id}`} />
      <Button size="sm" onClick={add} disabled={busy || !name} data-testid={`library-voice-add-${v.voice_id}`}>{busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}</Button>
    </div>
  );
}

export function VoiceLibrary({ onAdded }) {
  const [f, setF] = useState({ country: "ES", gender: "" });
  const [list, setList] = useState(null);
  const [busy, setBusy] = useState(false);
  const [playing, setPlaying] = useState("");
  const audio = useRef(null);
  useEffect(() => {
    audio.current?.pause();
    const v = list?.find((x) => x.voice_id === playing);
    if (v?.preview_url) { audio.current = new Audio(v.preview_url); audio.current.onended = () => setPlaying(""); audio.current.play().catch(() => setPlaying("")); }
  }, [playing]); // eslint-disable-line react-hooks/exhaustive-deps
  const search = async () => {
    setBusy(true);
    try { setList((await api.get(`/admin/elevenlabs/library?country=${f.country}&gender=${f.gender}`)).data); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-3 border-t border-slate-800 pt-4" data-testid="voice-library-panel">
      <p className="text-sm font-semibold text-white">Buscar voces con acento nativo</p>
      <div className="flex flex-wrap gap-2">
        <div className="w-36">{sel(f.country, (v) => setF({ ...f, country: v || "ES" }), [["ES", "España"], ["CL", "Chile"]], "voice-library-country", "País")}</div>
        <div className="w-36">{sel(f.gender, (v) => setF({ ...f, gender: v }), [["female", "Mujer"], ["male", "Hombre"]], "voice-library-gender", "Cualquiera")}</div>
        <Button onClick={search} disabled={busy} variant="outline" data-testid="voice-library-search">{busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Search className="mr-2 h-4 w-4" />}Buscar</Button>
      </div>
      {list && list.length === 0 && <p className="text-xs text-slate-500">No hay resultados con ese filtro.</p>}
      <div className="max-h-96 space-y-2 overflow-y-auto">{(list || []).map((v) => <LibraryVoice key={v.voice_id} v={v} country={f.country} onAdded={onAdded} playing={playing} setPlaying={setPlaying} />)}</div>
    </div>
  );
}
