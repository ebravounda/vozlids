import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Copy, Download, Loader2, PhoneCall } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageHeader, Panel } from "@/components/Common";
import { api, errMsg } from "@/lib/api";
import { WidgetStats } from "@/components/WidgetStats";

const COLORS = ["#2563EB", "#059669", "#DC2626", "#7C3AED", "#EA580C", "#0F172A", "#DB2777"];
const API = process.env.REACT_APP_BACKEND_URL;

function Preview({ w }) {
  const side = w.position === "left" ? "left-4" : "right-4";
  return (
    <div className="relative h-[340px] overflow-hidden rounded-2xl border border-slate-200 bg-slate-50" data-testid="widget-preview">
      <div className="flex items-center gap-1.5 border-b border-slate-200 bg-white px-3 py-2"><span className="h-2.5 w-2.5 rounded-full bg-rose-300" /><span className="h-2.5 w-2.5 rounded-full bg-amber-300" /><span className="h-2.5 w-2.5 rounded-full bg-emerald-300" /><span className="ml-3 h-4 w-48 rounded bg-slate-100" /></div>
      <div className="space-y-3 p-6">{[70, 90, 55, 80].map((x) => <div key={x} className="h-3 rounded bg-slate-200" style={{ width: `${x}%` }} />)}</div>
      {w.greeting && <div className={`absolute bottom-20 ${side} max-w-[230px] rounded-2xl bg-white px-3.5 py-2.5 text-sm text-slate-800 shadow-lg`} data-testid="widget-preview-greeting">{w.greeting}</div>}
      <div className={`absolute bottom-4 ${side} flex items-center gap-2 rounded-full px-5 py-3 text-sm font-semibold text-white shadow-xl`} style={{ background: w.color }} data-testid="widget-preview-button">
        <PhoneCall className="h-4 w-4" />{w.text || "Solicitar llamada"}
      </div>
    </div>
  );
}

function CodeBox({ code, testid }) {
  const copy = () => navigator.clipboard.writeText(code).then(() => toast.success("Código copiado"));
  return (
    <div className="space-y-2">
      <pre className="overflow-x-auto rounded-xl bg-slate-900 p-4 font-mono text-xs text-emerald-200" data-testid={testid}>{code}</pre>
      <Button variant="outline" size="sm" onClick={copy} className="rounded-full" data-testid={`${testid}-copy`}><Copy className="mr-2 h-4 w-4" />Copiar código</Button>
    </div>
  );
}

const Steps = ({ items }) => <ol className="list-decimal space-y-1.5 pl-5 text-sm text-slate-300">{items.map((t) => <li key={t}>{t}</li>)}</ol>;

function Install({ id }) {
  const code = `<script src="${API}/api/public/widget.js" data-id="${id}" async></script>`;
  const [busy, setBusy] = useState(false);
  const download = async () => {
    setBusy(true);
    try {
      const r = await api.get("/widget/wordpress.zip", { responseType: "blob" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(r.data);
      a.download = "vozleads-widget.zip";
      a.click();
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <Panel className="space-y-4" data-testid="widget-install-panel">
      <h3 className="text-lg font-semibold text-white">Instálalo en tu web</h3>
      <Tabs defaultValue="wordpress">
        <TabsList className="flex-wrap">
          {[["wordpress", "WordPress"], ["shopify", "Shopify"], ["wix", "Wix"], ["otra", "Otra web"]].map(([v, l]) => <TabsTrigger key={v} value={v} data-testid={`widget-tab-${v}`}>{l}</TabsTrigger>)}
        </TabsList>
        <TabsContent value="wordpress" className="space-y-4 pt-3">
          <Steps items={["Descarga el plugin (ya lleva tu botón configurado).", "En WordPress ve a Plugins → Añadir nuevo → Subir plugin y elige el archivo .zip.", "Pulsa «Instalar ahora» y después «Activar». El botón aparece al instante en tu web."]} />
          <Button onClick={download} disabled={busy} className="rounded-full" data-testid="widget-wordpress-download">{busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}Descargar plugin de WordPress</Button>
        </TabsContent>
        <TabsContent value="shopify" className="space-y-4 pt-3">
          <Steps items={["En Shopify ve a Tienda online → Temas → … → Editar código.", "Abre el archivo layout/theme.liquid.", "Pega este código justo antes de </body> y pulsa Guardar."]} />
          <CodeBox code={code} testid="widget-code-shopify" />
        </TabsContent>
        <TabsContent value="wix" className="space-y-4 pt-3">
          <Steps items={["En Wix ve a Ajustes → Avanzado → Código personalizado → Añadir código.", "Pega este código, elige «Todas las páginas» y la ubicación «Body - final».", "Pulsa Aplicar y publica tu web. (Necesitas un plan Premium de Wix con dominio propio.)"]} />
          <CodeBox code={code} testid="widget-code-wix" />
        </TabsContent>
        <TabsContent value="otra" className="space-y-4 pt-3">
          <Steps items={["Pega este código en tu web justo antes de </body>, en todas las páginas donde quieras el botón.", "Funciona en cualquier web: HTML, Webflow, Squarespace, Joomla, PrestaShop…"]} />
          <CodeBox code={code} testid="widget-code-generic" />
        </TabsContent>
      </Tabs>
      <p className="text-xs text-slate-500">Los cambios de texto, color, posición y horario se aplican solos en tu web en un minuto, sin volver a instalar nada.</p>
    </Panel>
  );
}

export default function WebWidget() {
  const [w, setW] = useState(null);
  const [agents, setAgents] = useState([]);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api.get("/widget").then((r) => setW(r.data));
    api.get("/agents").then((r) => setAgents(r.data.filter((a) => a.active !== false)));
  }, []);
  if (!w) return <p className="text-sm text-slate-400"><Loader2 className="mr-2 inline h-4 w-4 animate-spin" />Cargando…</p>;
  const set = (k) => (v) => setW({ ...w, [k]: v });
  const save = async () => {
    setBusy(true);
    try { setW((await api.put("/widget", { ...w, greeting_delay: Number(w.greeting_delay) })).data); toast.success("Botón guardado"); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <div className="fade-up space-y-6" data-testid="web-widget-page">
      <PageHeader eyebrow="Para tu web" title="Botón «Solicitar llamada»" desc="Un botón flotante en tu web o tienda: tu cliente deja su nombre y teléfono y tu asistente con IA le llama en segundos." />
      <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
        <Panel className="space-y-4" data-testid="widget-settings-panel">
          <div className="space-y-1.5"><Label className="text-xs">Agente que llama</Label>
            <Select value={w.agent_id} onValueChange={set("agent_id")}>
              <SelectTrigger className="bg-slate-950/60" data-testid="widget-agent-select"><SelectValue placeholder="Elige un agente" /></SelectTrigger>
              <SelectContent>{agents.map((a) => <SelectItem key={a.id} value={a.id}>{a.name} · {a.business_name}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5"><Label className="text-xs">Texto del botón</Label><Input value={w.text} maxLength={30} onChange={(e) => set("text")(e.target.value)} className="bg-slate-950/60" data-testid="widget-text-input" /></div>
          <div className="space-y-1.5"><Label className="text-xs">Color</Label>
            <div className="flex flex-wrap items-center gap-2">
              {COLORS.map((c) => <button key={c} onClick={() => set("color")(c)} className={`h-8 w-8 rounded-full ring-offset-2 transition-transform hover:scale-110 ${w.color === c ? "ring-2 ring-slate-900" : ""}`} style={{ background: c }} aria-label={c} data-testid={`widget-color-${c.slice(1)}`} />)}
              <input type="color" value={w.color} onChange={(e) => set("color")(e.target.value.toUpperCase())} className="h-8 w-10 cursor-pointer rounded border border-slate-300" data-testid="widget-color-picker" />
            </div>
          </div>
          <div className="space-y-1.5"><Label className="text-xs">Posición</Label>
            <div className="flex gap-2">{[["left", "Izquierda"], ["right", "Derecha"]].map(([v, l]) => <Button key={v} type="button" variant={w.position === v ? "default" : "outline"} onClick={() => set("position")(v)} className="rounded-full" data-testid={`widget-position-${v}`}>{l}</Button>)}</div>
          </div>
          <label className="flex items-center justify-between gap-3 rounded-xl border border-slate-800 p-3 text-sm text-slate-300">
            <span>Mostrar solo en horario del negocio<span className="block text-xs text-slate-500">Usa el horario de «Agenda y citas»</span></span>
            <Switch checked={w.hours_only} onCheckedChange={set("hours_only")} data-testid="widget-hours-switch" />
          </label>
          <div className="grid gap-3 sm:grid-cols-[1fr_120px]">
            <div className="space-y-1.5"><Label className="text-xs">Mensaje de saludo (opcional)</Label><Input value={w.greeting} maxLength={120} placeholder="¿Te llamamos ahora? Sin esperas 👋" onChange={(e) => set("greeting")(e.target.value)} className="bg-slate-950/60" data-testid="widget-greeting-input" /></div>
            <div className="space-y-1.5"><Label className="text-xs">Aparece a los (s)</Label><Input type="number" min={1} max={60} value={w.greeting_delay} onChange={(e) => set("greeting_delay")(e.target.value)} className="bg-slate-950/60 font-mono" data-testid="widget-greeting-delay-input" /></div>
          </div>
          <Button onClick={save} disabled={busy || !w.agent_id} className="rounded-full" data-testid="widget-save-button">{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Guardar botón</Button>
        </Panel>
        <div className="space-y-3"><Label className="text-xs text-slate-500">Vista previa</Label><Preview w={w} /></div>
      </div>
      {w.agent_id && <WidgetStats />}
      {w.agent_id ? <Install id={w.id} /> : <Panel className="text-sm text-amber-300" data-testid="widget-install-locked">Elige el agente y guarda el botón para ver cómo instalarlo.</Panel>}
    </div>
  );
}
