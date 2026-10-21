import { Languages as LangIcon } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Panel } from "@/components/Common";
import { AmbiencePreview } from "@/components/AmbiencePreview";
import { LockedCard, useFeature } from "@/components/PlanGate";
import { LANGUAGES, TIER, TIER_NAME, voicesForLang } from "@/lib/constants";

function LangRow({ code, entry, custom, onChange, onToggle }) {
  const L = LANGUAGES[code];
  const voices = voicesForLang(code, custom);
  const v = voices.find((x) => x.id === entry?.voice);
  return (
    <div className="space-y-3 rounded-xl border border-slate-200 p-3" data-testid={`language-row-${code}`}>
      <label className="flex items-center justify-between gap-3">
        <span className="text-sm font-semibold">{L.name} <span className="font-normal text-slate-500">· {L.native}</span></span>
        <Switch checked={!!entry} onCheckedChange={(on) => onToggle(on ? { lang: code, voice: voices[0].id, name: voices[0].name } : null)} data-testid={`language-toggle-${code}`} />
      </label>
      {entry && (
        <div className="flex flex-wrap items-center gap-2">
          <Select value={entry.voice} onValueChange={(id) => onChange({ ...entry, voice: id, name: voices.find((x) => x.id === id).name })}>
            <SelectTrigger className="w-full sm:w-64" data-testid={`language-voice-${code}`}><SelectValue /></SelectTrigger>
            <SelectContent>{voices.map((x) => <SelectItem key={x.id} value={x.id}>{x.name} · {x.gender} · {x.accent} · {TIER_NAME[TIER(x)]}</SelectItem>)}</SelectContent>
          </Select>
          <Input value={entry.name} maxLength={40} onChange={(e) => onChange({ ...entry, name: e.target.value })} placeholder={v?.gender === "Hombre" ? "Nombre de hombre" : "Nombre de mujer"} className="w-40" data-testid={`language-name-${code}`} />
          <AmbiencePreview voice={entry.voice} lang={code} text={L.sample.replace("{n}", entry.name || v?.name || "")} label="Escuchar" testid={`language-preview-${code}`} className="!px-3 !py-1.5" />
        </div>
      )}
    </div>
  );
}

export function LanguagesPanel({ agent, update, custom }) {
  const ok = useFeature("multilang");
  const list = agent.languages || [];
  const set = (code, entry) => update({ languages: Object.keys(LANGUAGES).map((c) => (c === code ? entry : list.find((e) => e.lang === c))).filter(Boolean) });
  return (
    <Panel className="space-y-4 lg:col-span-2" data-testid="languages-panel">
      <div className="flex items-center gap-2"><LangIcon className="h-5 w-5 text-blue-500" /><h3 className="text-lg font-semibold">Atención en varios idiomas</h3></div>
      <p className="text-sm text-slate-500">Activa los idiomas que puede atender este agente. Al empezar la llamada pregunta en qué idioma prefieren que le atiendan y, si eligen otro distinto del español, pasa la llamada a un ejecutivo nativo de ese idioma, con su propia voz y nombre.</p>
      {!ok ? <LockedCard f="multilang" compact /> : (
        <div className="grid gap-3 md:grid-cols-2">
          {Object.keys(LANGUAGES).map((code) => <LangRow key={code} code={code} entry={list.find((e) => e.lang === code)} custom={custom}
            onChange={(e) => set(code, e)} onToggle={(e) => set(code, e)} />)}
        </div>
      )}
    </Panel>
  );
}
