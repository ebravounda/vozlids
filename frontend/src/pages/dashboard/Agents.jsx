import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bot, ExternalLink, Pencil, Plus } from "lucide-react";
import { PageHeader, Panel } from "@/components/Common";
import { api } from "@/lib/api";
import { AMBIENCES, OBJECTIVES, VOICES } from "@/lib/constants";

const name = (list, id) => list.find((x) => x.id === id)?.name || id;

export default function Agents() {
  const [agents, setAgents] = useState(null);
  useEffect(() => { api.get("/agents").then((r) => setAgents(r.data)).catch(() => setAgents([])); }, []);

  return (
    <div className="fade-up">
      <PageHeader eyebrow="Agentes IA" title="Tus agentes de voz" desc="Cada agente tiene su objetivo, su voz, su ambiente y su propio formulario.">
        <Link to="/app/agentes/nuevo" data-testid="agents-create-button" className="inline-flex items-center gap-2 rounded-full bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-slate-950 hover:bg-emerald-400">
          <Plus className="h-4 w-4" /> Nuevo agente
        </Link>
      </PageHeader>
      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        {agents?.map((a) => (
          <Panel key={a.id} className="flex flex-col transition-colors hover:border-emerald-500/40" data-testid={`agent-card-${a.id}`}>
            <div className="flex items-start justify-between">
              <span className="grid h-11 w-11 place-items-center rounded-xl bg-emerald-500/15 text-emerald-300"><Bot className="h-5 w-5" /></span>
              <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${a.active ? "bg-emerald-500/15 text-emerald-300" : "bg-slate-700 text-slate-300"}`}>{a.active ? "Activo" : "Pausado"}</span>
            </div>
            <h3 className="mt-5 text-xl font-semibold text-white">{a.name}</h3>
            <p className="text-sm text-slate-400">{a.business_name}{a.is_sample ? " · ejemplo" : ""}</p>
            <dl className="mt-5 space-y-1.5 text-xs text-slate-400">
              <div className="flex justify-between"><dt>Objetivo</dt><dd className="text-slate-200">{name(OBJECTIVES, a.objective)}</dd></div>
              <div className="flex justify-between"><dt>Voz</dt><dd className="text-slate-200">{name(VOICES, a.voice)}</dd></div>
              <div className="flex justify-between"><dt>Ambiente</dt><dd className="text-slate-200">{name(AMBIENCES, a.ambience)}</dd></div>
            </dl>
            <div className="mt-6 flex gap-2 pt-2">
              <Link to={`/app/agentes/${a.id}`} data-testid={`agent-edit-${a.id}`} className="inline-flex flex-1 items-center justify-center gap-2 rounded-full border border-slate-700 py-2 text-sm text-slate-200 hover:border-emerald-500/50 hover:text-white">
                <Pencil className="h-3.5 w-3.5" /> Editar y probar
              </Link>
              <a href={`/f/${a.id}`} target="_blank" rel="noreferrer" data-testid={`agent-form-link-${a.id}`} className="inline-flex items-center justify-center rounded-full border border-slate-700 px-3 text-slate-300 hover:text-white" title="Ver formulario">
                <ExternalLink className="h-4 w-4" />
              </a>
            </div>
          </Panel>
        ))}
      </div>
      {agents && !agents.length && (
        <Panel className="text-center" data-testid="agents-empty">
          <p className="text-slate-400">Todavía no tienes agentes.</p>
          <Link to="/app/agentes/nuevo" className="mt-4 inline-block font-semibold text-emerald-400">Crear el primero →</Link>
        </Panel>
      )}
    </div>
  );
}
