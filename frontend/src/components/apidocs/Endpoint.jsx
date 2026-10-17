const COLORS = { get: "bg-emerald-100 text-emerald-700", post: "bg-blue-100 text-blue-700", put: "bg-amber-100 text-amber-700", delete: "bg-rose-100 text-rose-700", patch: "bg-violet-100 text-violet-700" };

export const Method = ({ m }) => <span className={`inline-block w-16 rounded-md py-0.5 text-center font-mono text-[11px] font-bold uppercase ${COLORS[m] || "bg-slate-100"}`}>{m}</span>;

const typeOf = (s = {}) => {
  if (s.$ref) return s.$ref.split("/").pop();
  if (s.anyOf) return s.anyOf.filter((x) => x.type !== "null").map(typeOf).join(" | ");
  if (s.enum) return s.enum.join(" | ");
  if (s.type === "array") return `${typeOf(s.items)}[]`;
  return s.type || "objeto";
};

function Fields({ rows }) {
  if (!rows.length) return null;
  return (
    <table className="mt-3 w-full text-sm">
      <tbody>
        {rows.map(([n, s, req, where]) => (
          <tr key={n} className="border-t border-slate-100 align-top">
            <td className="py-2 pr-4 font-mono text-[13px] text-slate-900">{n}{req && <span className="ml-1 text-rose-500">*</span>}</td>
            <td className="py-2 pr-4 font-mono text-xs text-blue-700">{typeOf(s)}{where && <span className="ml-1 text-slate-400">· {where}</span>}</td>
            <td className="py-2 text-slate-600">{s.description || ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function Endpoint({ method, path, op, schemas }) {
  const params = (op.parameters || []).filter((p) => p.name.toLowerCase() !== "x-api-key")
    .map((p) => [p.name, { ...p.schema, description: p.description || p.schema?.description }, p.required, p.in === "header" ? "cabecera" : p.in === "path" ? "ruta" : "query"]);
  const ref = op.requestBody?.content?.["application/json"]?.schema?.$ref;
  const body = ref ? schemas[ref.split("/").pop()] : null;
  const bodyRows = body ? Object.entries(body.properties || {}).map(([n, s]) => [n, s, (body.required || []).includes(n)]) : [];
  const responses = Object.entries(op.responses || {}).filter(([c]) => c !== "422");
  const id = op.operationId;
  return (
    <article id={id} className="scroll-mt-24 rounded-2xl border border-slate-200 bg-white p-6" data-testid={`api-endpoint-${id}`}>
      <div className="flex flex-wrap items-center gap-3"><Method m={method} /><code className="font-mono text-sm font-semibold text-slate-900">{path}</code></div>
      <h3 className="mt-3 text-lg font-semibold text-slate-900">{op.summary}</h3>
      {op.description && <p className="mt-1 whitespace-pre-line text-sm text-slate-600">{op.description}</p>}
      {params.length > 0 && <><p className="mt-5 text-xs font-semibold uppercase tracking-widest text-slate-400">Parámetros</p><Fields rows={params} /></>}
      {bodyRows.length > 0 && <><p className="mt-5 text-xs font-semibold uppercase tracking-widest text-slate-400">Cuerpo (JSON)</p><Fields rows={bodyRows} /></>}
      {responses.length > 0 && (
        <div className="mt-5 flex flex-wrap gap-2">{responses.map(([c, r]) => <span key={c} className={`rounded-full px-2.5 py-1 font-mono text-xs ${c.startsWith("2") ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>{c} · {r.description}</span>)}</div>
      )}
    </article>
  );
}
