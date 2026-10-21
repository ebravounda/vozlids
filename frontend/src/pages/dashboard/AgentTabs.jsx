import { FEATURE_INFO, useFeature } from "@/components/PlanGate";
import { Link } from "react-router-dom";
import { Lock } from "lucide-react";
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
import { AMBIENCES, COUNTRIES, OBJECTIVES, TIER, customVoice, voicesForLang } from "@/lib/constants";
import { ExecutivesPanel } from "@/components/agent/Executives";
import { LanguagesPanel } from "@/components/agent/Languages";

const GROUPS = [
  ["eleven", "Ultra natural HD · las más humanas", "Recomendado · algo más caro por minuto", "text-emerald-300"],
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
          onClick={() => update({ country: code })}
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
      <Label>Información del negocio (lo único que sabe el agente)</Label>
      <Textarea rows={8} maxLength={8000} value={agent.product} onChange={(e) => update({ product: e.target.value })} data-testid="agent-product-input" className="bg-slate-950/60"
        placeholder={"Qué vendes y precios, ofertas, horarios, dirección y zona de servicio, formas de pago, plazos, preguntas frecuentes con su respuesta…"} />
      <p className="flex justify-between gap-3 text-xs text-slate-500" data-testid="agent-product-help">
        <span>El agente solo responde con lo que escribas aquí y en «Instrucciones adicionales». Cualquier pregunta ajena al negocio la rechaza con amabilidad.</span>
        <span className="shrink-0 tabular-nums">{(agent.product || "").length}/8000</span>
      </p>
    </div>
    <div className="space-y-3">
      <Label>Objetivo de la llamada</Label>
      <div className="grid gap-3 md:grid-cols-3">
        {OBJECTIVES.map((o) => <Choice key={o.id} active={agent.objective === o.id} onClick={() => update({ objective: o.id })} title={o.name} desc={o.desc} testid={`agent-objective-${o.id}`} />)}
      </div>
    </div>
  </Panel>
);

const PlanLockNote = ({ f }) => (
  <Link to="/app/plan" className="flex items-center gap-3 rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600 hover:border-slate-400" data-testid={`plan-lock-${f}`}>
    <Lock className="h-4 w-4 shrink-0 text-slate-400" /><span><b className="text-slate-800">{FEATURE_INFO[f][0]}</b> no está incluido en tu plan. <span className="font-semibold text-blue-600">Mejorar plan →</span></span>
  </Link>
);

export const VoiceTab = ({ agent, update }) => {
  const ambOk = useFeature("ambience");
  const amb = agent.ambience.startsWith("custom:") ? { volume: true } : AMBIENCES.find((a) => a.id === agent.ambience);
  const [custom, setCustom] = useState([]);
  const [accent, setAccent] = useState("");
  useEffect(() => { api.get("/voices/custom").then((r) => setCustom(r.data.map(customVoice))).catch(() => {}); }, []);
  const list = voicesForLang("es", custom);
  const accents = [...new Set(list.map((v) => v.accent))];
  const team = agent.executives || [];
  const pickVoice = (id) => update(team.length ? { voice: id, executives: [{ voice: id, name: list.find((v) => v.id === id)?.name || team[0].name }, ...team.slice(1).filter((e) => e.voice !== id)] } : { voice: id });
  return (
    <div className="grid gap-6 lg:grid-cols-2 [&>*]:min-w-0">
      <ExecutivesPanel agent={agent} update={update} voices={list} />
      <LanguagesPanel agent={agent} update={update} custom={custom} />
      <Panel className="space-y-5">
        <Label>Voz principal (español, todos los acentos)</Label>
        <div className="flex flex-wrap gap-2" data-testid="voice-accent-filter">
          {["", ...accents].map((a) => (
            <button key={a || "all"} type="button" onClick={() => setAccent(a)} data-testid={`voice-accent-${a || "todos"}`}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${accent === a ? "border-emerald-500 bg-emerald-500/10 text-emerald-700" : "border-slate-300 text-slate-600 hover:border-slate-400"}`}>{a ? `Acento ${a}` : "Todos"}</button>
          ))}
        </div>
        {GROUPS.map(([tier, title, note, color]) => (
          <div key={tier} className="space-y-3" data-testid={`voice-group-${tier}`}>
            <div className="flex items-baseline justify-between">
              <p className={`text-xs font-semibold uppercase tracking-widest ${color}`}>{title}</p>
              <p className="text-xs text-slate-500">{note}</p>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {list.filter((v) => TIER(v) === tier && (!accent || v.accent === accent)).map((v) => <Choice key={v.id} active={agent.voice === v.id} onClick={() => pickVoice(v.id)} title={v.name} desc={`${v.gender} · Acento ${v.accent} · ${v.tone}`} testid={`agent-voice-${v.id}`} />)}
            </div>
          </div>
        ))}
      </Panel>
      <Panel className="space-y-4">
        <Label>Ambiente de fondo</Label>
        <div className="grid gap-2" data-testid="audio-ambience-select">
          {AMBIENCES.filter((a) => ambOk || a.id === "none").map((a) => <Choice key={a.id} active={agent.ambience === a.id} onClick={() => update({ ambience: a.id })} title={a.real ? `${a.name} ★` : a.name} desc={a.desc} testid={`agent-ambience-${a.id}`} />)}
          {ambOk ? <CustomAmbiences value={agent.ambience} onSelect={(id) => update({ ambience: id })} /> : <PlanLockNote f="ambience" />}
        </div>
        {amb?.volume && (
          <div className="space-y-3 pt-2">
            <div className="flex justify-between text-sm"><Label>Volumen del ambiente</Label><span className="font-mono text-emerald-300" data-testid="audio-volume-value">{agent.ambience_volume}%</span></div>
            <Slider min={5} max={100} step={5} value={[agent.ambience_volume]} onValueChange={([v]) => update({ ambience_volume: v })} data-testid="audio-volume-slider" />
            <p className="text-xs text-slate-500">Recomendado: 25–45%. Muy alto puede dificultar que el agente entienda al lead.</p>
          </div>
        )}
        <div className="border-t border-slate-800 pt-4">
          <AmbiencePreview ambience={agent.ambience} volume={agent.ambience_volume} voice={agent.voice} text={agent.greeting.replace("{nombre}", "Laura").replace("{empresa}", agent.business_name || "").replace("{agente}", agent.name || "")} />
          <p className="mt-3 text-xs text-slate-500">El ambiente es el mismo que sonará en la llamada. La vista previa usa la misma voz de las llamadas; en la llamada real suena con calidad telefónica.</p>
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
          <p className="text-xs text-slate-500">Usa <code className="text-emerald-300">{"{nombre}"}</code> para decir el nombre del lead. Menciona que la llamada se graba.</p>
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
