import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Loader2, Save, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/Common";
import { useAuth } from "@/context/AuthContext";
import { api, errMsg } from "@/lib/api";
import { DEFAULT_GREETING } from "@/lib/constants";
import { GeneralTab, ScriptTab, VoiceTab } from "@/pages/dashboard/AgentTabs";
import { TestPublishTab } from "@/pages/dashboard/TestPublishTab";

const blank = (business) => ({
  name: "Marta", business_name: business || "", product: "", objective: "agendar", questions: [""],
  voice: "p_marta", ambience: "oficina", ambience_volume: 35,
  greeting: DEFAULT_GREETING.replace("tu negocio", business || "tu negocio"), extra_instructions: "", active: true,
});

export default function AgentBuilder() {
  const { agentId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [agent, setAgent] = useState(agentId ? null : blank(user?.business_name));
  const [saving, setSaving] = useState(false);
  const [tab, setTab] = useState("general");

  useEffect(() => {
    if (agentId) api.get(`/agents/${agentId}`).then((r) => setAgent({ ...r.data, questions: r.data.questions.length ? r.data.questions : [""] })).catch(() => navigate("/app/agentes"));
  }, [agentId, navigate]);

  const update = (patch) => setAgent((a) => ({ ...a, ...patch }));

  const save = async () => {
    setSaving(true);
    const payload = { ...agent, questions: agent.questions.map((q) => q.trim()).filter(Boolean) };
    ["id", "tenant_id", "created_at", "updated_at", "is_sample"].forEach((k) => delete payload[k]);
    try {
      const { data } = agentId ? await api.put(`/agents/${agentId}`, payload) : await api.post("/agents", payload);
      toast.success("Agente guardado");
      if (!agentId) { navigate(`/app/agentes/${data.id}`, { replace: true }); setTab("test"); }
      else setAgent({ ...data, questions: data.questions.length ? data.questions : [""] });
    } catch (e) {
      toast.error(errMsg(e));
      if (!payload.product || !payload.business_name) setTab("general");
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!window.confirm("¿Eliminar este agente? Su formulario dejará de funcionar.")) return;
    await api.delete(`/agents/${agentId}`);
    toast.success("Agente eliminado");
    navigate("/app/agentes");
  };

  if (!agent) return <p className="text-slate-400">Cargando…</p>;

  return (
    <div className="fade-up">
      <PageHeader eyebrow={agentId ? "Editar agente" : "Nuevo agente"} title={agentId ? agent.name : "Crea tu agente de voz"} desc="Configura qué dice, cómo suena y qué consigue en cada llamada.">
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <Switch checked={agent.active} onCheckedChange={(v) => update({ active: v })} data-testid="agent-active-switch" /> {agent.active ? "Activo" : "Pausado"}
        </label>
        {agentId && <Button variant="outline" onClick={remove} className="rounded-full border-slate-700 bg-transparent text-rose-300 hover:bg-rose-500/10 hover:text-rose-200" data-testid="agent-delete-button"><Trash2 className="mr-2 h-4 w-4" /> Eliminar</Button>}
        <Button onClick={save} disabled={saving} className="rounded-full px-6 font-semibold" data-testid="agent-builder-save-button">
          {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />} Guardar
        </Button>
      </PageHeader>
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="mb-6 h-auto flex-wrap bg-slate-900 p-1">
          <TabsTrigger value="general" data-testid="agent-tab-general">1. General</TabsTrigger>
          <TabsTrigger value="voice" data-testid="agent-tab-voice">2. Voz y ambiente</TabsTrigger>
          <TabsTrigger value="script" data-testid="agent-tab-script">3. Guion</TabsTrigger>
          <TabsTrigger value="test" data-testid="agent-tab-test">4. Probar y publicar</TabsTrigger>
        </TabsList>
        <TabsContent value="general"><GeneralTab agent={agent} update={update} /></TabsContent>
        <TabsContent value="voice"><VoiceTab agent={agent} update={update} /></TabsContent>
        <TabsContent value="script"><ScriptTab agent={agent} update={update} /></TabsContent>
        <TabsContent value="test"><TestPublishTab agentId={agentId} /></TabsContent>
      </Tabs>
    </div>
  );
}
