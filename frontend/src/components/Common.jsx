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

export const Logo = ({ className = "", white = false, size = "h-9" }) => (
  <img src={white ? "/brand/vozleads-logo-white.png" : "/brand/vozleads-logo.png"} alt="VozLeads by GoRoky" width="140" height="33"
    className={`${size} w-auto select-none ${className}`} draggable="false" data-testid="brand-logo" />
);

export const PageHeader = ({ eyebrow, title, desc, children }) => (
  <div className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
    <div>
      {eyebrow && <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-blue-600">{eyebrow}</p>}
      <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 sm:text-3xl">{title}</h1>
      {desc && <p className="mt-2 max-w-2xl text-sm text-slate-500">{desc}</p>}
    </div>
    {children && <div className="flex flex-wrap gap-3">{children}</div>}
  </div>
);

export const Panel = ({ children, className = "", ...rest }) => (
  <div className={`rounded-2xl border border-slate-200 bg-white p-6 shadow-[0_1px_2px_rgba(15,23,42,0.04)] transition-shadow hover:shadow-[0_8px_30px_-12px_rgba(15,23,42,0.12)] ${className}`} {...rest}>{children}</div>
);
