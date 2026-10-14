import { STATUS } from "@/lib/constants";

export const StatusBadge = ({ status, testid = "lead-status-badge" }) => {
  const s = STATUS[status] || STATUS.llamando;
  return (
    <span data-testid={testid} className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-semibold ${s.cls}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
      {s.label}
    </span>
  );
};

export const Logo = ({ className = "" }) => (
  <span className={`inline-flex items-center gap-2 font-display text-lg font-bold tracking-tight text-white ${className}`}>
    <span className="relative grid h-8 w-8 place-items-center rounded-lg bg-emerald-500 text-slate-950">
      <span className="flex h-3.5 items-center gap-[2px]">
        {[0, 1, 2, 3].map((i) => (
          <span key={i} className="wave-bar w-[2.5px] rounded bg-slate-950" style={{ height: 14, animationDelay: `${i * 0.15}s` }} />
        ))}
      </span>
    </span>
    VozLead
  </span>
);

export const PageHeader = ({ eyebrow, title, desc, children }) => (
  <div className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
    <div>
      {eyebrow && <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-emerald-400">{eyebrow}</p>}
      <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">{title}</h1>
      {desc && <p className="mt-2 max-w-2xl text-sm text-slate-400">{desc}</p>}
    </div>
    {children && <div className="flex flex-wrap gap-3">{children}</div>}
  </div>
);

export const Panel = ({ children, className = "", ...rest }) => (
  <div className={`rounded-2xl border border-slate-800 bg-slate-900/60 p-6 ${className}`} {...rest}>{children}</div>
);
