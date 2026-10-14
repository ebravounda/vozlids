import { Plus, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Textarea } from "@/components/ui/textarea";
import { Panel } from "@/components/Common";
import { AmbiencePreview } from "@/components/AmbiencePreview";
import { AMBIENCES, OBJECTIVES, VOICES } from "@/lib/constants";

const Choice = ({ active, onClick, title, desc, testid }) => (
  <button type="button" onClick={onClick} data-testid={testid}
    className={`rounded-xl border p-4 text-left transition-colors ${active ? "border-emerald-500 bg-emerald-500/10" : "border-slate-800 bg-slate-950/40 hover:border-slate-600"}`}>
    <p className={`text-sm font-semibold ${active ? "text-emerald-200" : "text-white"}`}>{title}</p>
    {desc && <p className="mt-1 text-xs text-slate-400">{desc}</p>}
  </button>
);

export const GeneralTab = ({ agent, update }) => (
  <Panel className="space-y-6">
    <div className="grid gap-5 md:grid-cols-2">
      <div className="space-y-2"><Label>Nombre del agente</Label><Input value={agent.name} onChange={(e) => update({ name: e.target.value })} data-testid="agent-name-input" className="bg-slate-950/60" /></div>
      <div className="space-y-2"><Label>Nombre del negocio</Label><Input value={agent.business_name} onChange={(e) => update({ business_name: e.target.value })} data-testid="agent-business-input" className="bg-slate-950/60" /></div>
    </div>
    <div className="space-y-2">
      <Label>Producto o servicio</Label>
      <Textarea rows={5} value={agent.product} onChange={(e) => update({ product: e.target.value })} data-testid="agent-product-input" className="bg-slate-950/60"
        placeholder="Qué vendes, precios, ofertas, zona, horarios… Todo lo que el agente pueda necesitar para responder dudas." />
    </div>
    <div className="space-y-3">
      <Label>Objetivo de la llamada</Label>
      <div className="grid gap-3 md:grid-cols-3">
        {OBJECTIVES.map((o) => <Choice key={o.id} active={agent.objective === o.id} onClick={() => update({ objective: o.id })} title={o.name} desc={o.desc} testid={`agent-objective-${o.id}`} />)}
      </div>
    </div>
  </Panel>
);

export const VoiceTab = ({ agent, update }) => {
  const amb = AMBIENCES.find((a) => a.id === agent.ambience);
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Panel className="space-y-4">
        <Label>Voz (español de España)</Label>
        <div className="grid grid-cols-2 gap-3">
          {VOICES.map((v) => <Choice key={v.id} active={agent.voice === v.id} onClick={() => update({ voice: v.id })} title={v.name} desc={`${v.gender} · ${v.tone}`} testid={`agent-voice-${v.id}`} />)}
        </div>
      </Panel>
      <Panel className="space-y-4">
        <Label>Ambiente de fondo</Label>
        <div className="grid gap-2" data-testid="audio-ambience-select">
          {AMBIENCES.map((a) => <Choice key={a.id} active={agent.ambience === a.id} onClick={() => update({ ambience: a.id })} title={a.name} desc={a.desc} testid={`agent-ambience-${a.id}`} />)}
        </div>
        {amb?.volume && (
          <div className="space-y-3 pt-2">
            <div className="flex justify-between text-sm"><Label>Volumen del ambiente</Label><span className="font-mono text-emerald-300" data-testid="audio-volume-value">{agent.ambience_volume}%</span></div>
            <Slider min={5} max={100} step={5} value={[agent.ambience_volume]} onValueChange={([v]) => update({ ambience_volume: v })} data-testid="audio-volume-slider" />
            <p className="text-xs text-slate-500">Recomendado: 25–45%. Muy alto puede dificultar que el agente entienda al lead.</p>
          </div>
        )}
        <div className="border-t border-slate-800 pt-4">
          <AmbiencePreview ambience={agent.ambience} volume={agent.ambience_volume} voice={agent.voice} text={agent.greeting.replace("{nombre}", "Laura")} />
          <p className="mt-3 text-xs text-slate-500">El ambiente es el mismo que sonará en la llamada. La voz de esta vista previa es la de tu navegador; para oír la voz real usa “Llamarme ahora”.</p>
        </div>
      </Panel>
    </div>
  );
};

export const ScriptTab = ({ agent, update }) => {
  const setQ = (i, v) => update({ questions: agent.questions.map((q, j) => (j === i ? v : q)) });
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Panel className="space-y-4">
        <div className="space-y-2">
          <Label>Saludo inicial</Label>
          <Textarea rows={5} value={agent.greeting} onChange={(e) => update({ greeting: e.target.value })} data-testid="agent-greeting-input" className="bg-slate-950/60" />
          <p className="text-xs text-slate-500">Usa <code className="text-emerald-300">{"{nombre}"}</code> para decir el nombre del lead. Mantén que es un asistente virtual y que la llamada se graba: lo exige la normativa.</p>
        </div>
        <div className="space-y-2">
          <Label>Instrucciones adicionales (opcional)</Label>
          <Textarea rows={4} value={agent.extra_instructions} onChange={(e) => update({ extra_instructions: e.target.value })} data-testid="agent-extra-input" className="bg-slate-950/60" placeholder="Ej.: si preguntan por aparcamiento, di que hay parking gratuito en la puerta." />
        </div>
      </Panel>
      <Panel className="space-y-3">
        <Label>Preguntas de calificación</Label>
        {agent.questions.map((q, i) => (
          <div key={i} className="flex gap-2">
            <Input value={q} onChange={(e) => setQ(i, e.target.value)} placeholder="¿Qué presupuesto tienes?" data-testid={`agent-question-input-${i}`} className="bg-slate-950/60" />
            <button type="button" onClick={() => update({ questions: agent.questions.filter((_, j) => j !== i) })} className="rounded-lg px-2 text-slate-500 hover:text-rose-300" data-testid={`agent-question-remove-${i}`}><X className="h-4 w-4" /></button>
          </div>
        ))}
        {agent.questions.length < 10 && (
          <button type="button" onClick={() => update({ questions: [...agent.questions, ""] })} className="inline-flex items-center gap-2 text-sm font-semibold text-emerald-400 hover:text-emerald-300" data-testid="agent-question-add-button">
            <Plus className="h-4 w-4" /> Añadir pregunta
          </button>
        )}
      </Panel>
    </div>
  );
};
