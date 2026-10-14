import { useEffect, useState } from "react";
import { Plus, X } from "lucide-react";
import { api } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Textarea } from "@/components/ui/textarea";
import { Panel } from "@/components/Common";
import { AmbiencePreview } from "@/components/AmbiencePreview";
import { CustomAmbiences } from "@/components/CustomAmbiences";
import { AMBIENCES, COUNTRIES, DEFAULT_VOICE, OBJECTIVES, TIER, VOICES } from "@/lib/constants";

const GROUPS = [
  ["eleven", "ElevenLabs · las más naturales", "Recomendado · algo más caro por minuto", "text-emerald-300"],
  ["premium", "Premium", "Buena calidad, más económica", "text-amber-300"],
  ["standard", "Estándar", "Opción más barata, suena más robótica", "text-slate-400"],
];

const Choice = ({ active, onClick, title, desc, testid }) => (
  <button type="button" onClick={onClick} data-testid={testid}
    className={`rounded-xl border p-4 text-left transition-colors ${active ? "border-emerald-500 bg-emerald-500/10" : "border-slate-800 bg-slate-950/40 hover:border-slate-600"}`}>
    <p className={`text-sm font-semibold ${active ? "text-emerald-200" : "text-white"}`}>{title}</p>
    {desc && <p className="mt-1 text-xs text-slate-400">{desc}</p>}
  </button>
);

const CountryPick = ({ agent, update }) => (
  <div className="space-y-3">
    <Label>País al que llama este agente</Label>
    <div className="grid gap-3 sm:grid-cols-2">
      {Object.entries(COUNTRIES).map(([code, c]) => (
        <Choice key={code} active={(agent.country || "ES") === code} testid={`agent-country-${code}`}
          onClick={() => code !== (agent.country || "ES") && update({ country: code, voice: DEFAULT_VOICE[code] })}
          title={`${c.name} (${c.prefix})`} desc={`Hora de ${c.city} · teléfonos ${c.example}`} />
      ))}
    </div>
  </div>
);

export const GeneralTab = ({ agent, update }) => (
  <Panel className="space-y-6">
    <CountryPick agent={agent} update={update} />
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
  const amb = agent.ambience.startsWith("custom:") ? { volume: true } : AMBIENCES.find((a) => a.id === agent.ambience);
  const [custom, setCustom] = useState([]);
  useEffect(() => { api.get("/voices/custom").then((r) => setCustom(r.data.map((v) => ({ ...v, eleven: true, tone: v.tone || "Voz ElevenLabs propia" })))).catch(() => {}); }, []);
  const country = agent.country || "ES";
  const list = [...custom, ...VOICES].filter((v) => v.country === country || v.country === "ALL");
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Panel className="space-y-5">
        <Label>Voz ({(agent.country || "ES") === "CL" ? "español latino y chileno" : "español de España"})</Label>
        {GROUPS.map(([tier, title, note, color]) => (
          <div key={tier} className="space-y-3" data-testid={`voice-group-${tier}`}>
            <div className="flex items-baseline justify-between">
              <p className={`text-xs font-semibold uppercase tracking-widest ${color}`}>{title}</p>
              <p className="text-xs text-slate-500">{note}</p>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {list.filter((v) => TIER(v) === tier).map((v) => <Choice key={v.id} active={agent.voice === v.id} onClick={() => update({ voice: v.id })} title={v.name} desc={`${v.gender} · ${v.tone}`} testid={`agent-voice-${v.id}`} />)}
            </div>
          </div>
        ))}
      </Panel>
      <Panel className="space-y-4">
        <Label>Ambiente de fondo</Label>
        <div className="grid gap-2" data-testid="audio-ambience-select">
          {AMBIENCES.map((a) => <Choice key={a.id} active={agent.ambience === a.id} onClick={() => update({ ambience: a.id })} title={a.real ? `${a.name} ★` : a.name} desc={a.desc} testid={`agent-ambience-${a.id}`} />)}
          <CustomAmbiences value={agent.ambience} onSelect={(id) => update({ ambience: id })} />
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
