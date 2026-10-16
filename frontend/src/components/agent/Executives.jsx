import { Plus, Trash2, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Panel } from "@/components/Common";

const MAX = 5;

export function ExecutivesPanel({ agent, update, voices }) {
  const team = agent.executives || [];
  const byId = Object.fromEntries(voices.map((v) => [v.id, v]));
  const free = voices.filter((v) => !team.some((e) => e.voice === v.id));
  const save = (next) => update({ executives: next, ...(next[0] ? { voice: next[0].voice } : {}) });
  const add = (id) => save([...team, { voice: id, name: byId[id].name }]);
  const start = () => save([{ voice: agent.voice, name: agent.name || byId[agent.voice]?.name || "" }]);
  return (
    <Panel className="space-y-4 lg:col-span-2" data-testid="executives-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2"><Users className="h-5 w-5 text-blue-500" /><h3 className="text-lg font-semibold">Varios ejecutivos en rotación</h3></div>
        {!team.length && <Button variant="outline" onClick={start} className="rounded-full" data-testid="executives-enable-button">Activar rotación</Button>}
      </div>
      <p className="text-sm text-slate-500">Cada llamada (entrante o saliente) la atiende el siguiente ejecutivo por turnos, con su voz y su nombre. Usa un nombre del mismo género que la voz. En el saludo, el nombre del agente se cambia solo por el del ejecutivo que llama.</p>
      {team.map((e, i) => <ExecRow key={e.voice} e={e} i={i} v={byId[e.voice]} onName={(name) => save(team.map((x, j) => (j === i ? { ...x, name } : x)))} onRemove={() => save(team.filter((_, j) => j !== i))} />)}
      {team.length > 0 && team.length < MAX && (
        <Select value="" onValueChange={add}>
          <SelectTrigger className="w-full sm:w-80" data-testid="executives-add-select"><Plus className="mr-2 h-4 w-4" /><SelectValue placeholder={`Añadir ejecutivo (${team.length}/${MAX})`} /></SelectTrigger>
          <SelectContent>{free.map((v) => <SelectItem key={v.id} value={v.id} data-testid={`executives-add-${v.id}`}>{v.name} · {v.gender}</SelectItem>)}</SelectContent>
        </Select>
      )}
    </Panel>
  );
}

function ExecRow({ e, i, v, onName, onRemove }) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 p-3" data-testid={`executive-row-${i}`}>
      <span className="w-6 text-center font-mono text-sm text-slate-400">{i + 1}</span>
      <div className="min-w-[140px] flex-1"><p className="text-sm font-semibold">Voz {v?.name || e.voice}</p><p className="text-xs text-slate-500">{v?.gender || ""}{i === 0 ? " · principal" : ""}</p></div>
      <Input value={e.name} maxLength={40} onChange={(ev) => onName(ev.target.value)} placeholder={v?.gender === "Hombre" ? "Nombre de hombre" : "Nombre de mujer"} className="w-48" data-testid={`executive-name-${i}`} />
      <Button variant="ghost" size="icon" onClick={onRemove} data-testid={`executive-remove-${i}`}><Trash2 className="h-4 w-4" /></Button>
    </div>
  );
}
