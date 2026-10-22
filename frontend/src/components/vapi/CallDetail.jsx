import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { api, errMsg } from "@/lib/api";

const usd = (n) => `$${(n || 0).toFixed(4)}`;
const dur = (s) => `${Math.floor((s || 0) / 60)}:${String((s || 0) % 60).padStart(2, "0")}`;
const Line = ({ l, v, t, b }) => (
  <div className={`flex justify-between gap-4 text-sm ${b ? "font-semibold" : "text-slate-400"}`} data-testid={t}><span>{l}</span><span>{v}</span></div>
);

const Leg = ({ title, children, t }) => (
  <div className="space-y-1 rounded-xl border border-slate-800 p-4" data-testid={t}><p className="mb-2 text-sm font-semibold">{title}</p>{children}</div>
);

const HumanLeg = ({ h }) => {
  if (!h.ok) return <Leg title={`Tramo pasado a ${h.to}`} t="call-detail-human"><p className="text-sm text-rose-400">La transferencia no se completó: la persona no llegó a hablar.</p></Leg>;
  const z = h.zadarma;
  return (
    <Leg title={`Tramo pasado a ${h.to}`} t="call-detail-human">
      <Line l="Duración" v={dur(h.seconds)} />
      <Line l="Vapi (sigue uniendo la llamada)" v={usd(h.vapi_cost)} t="call-detail-human-vapi" />
      {z?.error && <Line l="Zadarma" v={z.error} />}
      {z?.note && <Line l="Zadarma" v={z.note} />}
      {z && !z.error && !z.note && <Line l={`Zadarma: llamada a ${z.destination || "el móvil"} (${z.seconds}s)`} v={`${z.cost} ${z.currency}`} t="call-detail-human-zadarma" />}
      {!z && <Line l="Zadarma" v="Solo visible en tu servidor" />}
    </Leg>
  );
};

export const CallDetail = ({ id, onClose }) => {
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => { api.get(`/admin/vapi/calls/${id}`).then((r) => setD(r.data)).catch((e) => setErr(errMsg(e))); }, [id]);
  const zad = d?.human?.zadarma?.cost && !d.human.zadarma.error ? ` + ${d.human.zadarma.cost} ${d.human.zadarma.currency} Zadarma` : "";
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg" data-testid="call-detail-dialog">
        <DialogHeader><DialogTitle>Detalle de la llamada</DialogTitle></DialogHeader>
        {err && <p className="text-sm text-rose-400" data-testid="call-detail-error">{err}</p>}
        {!d && !err && <Loader2 className="mx-auto h-5 w-5 animate-spin" />}
        {d && (
          <div className="space-y-3">
            <p className="text-xs text-slate-400" data-testid="call-detail-summary">{new Date(d.at).toLocaleString("es-ES")} · {d.number} · {d.owner} · llamante {d.customer} · {d.reason}</p>
            <Leg title="Tramo con el agente IA" t="call-detail-ai">
              <Line l="Duración" v={dur(d.ai.seconds)} />
              {d.ai.items.map((i) => <Line key={i.label} l={i.label} v={usd(i.cost)} />)}
              <Line l="Coste Vapi de este tramo" v={usd(d.ai.cost)} b t="call-detail-ai-cost" />
            </Leg>
            {d.human && <HumanLeg h={d.human} />}
            <Line l={`Total (${dur(d.seconds)})`} v={`${usd(d.cost)} Vapi${zad}`} b t="call-detail-total" />
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
