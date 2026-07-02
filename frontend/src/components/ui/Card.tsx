import type { ReactNode } from "react";

export function Card({
  title,
  subtitle,
  actions,
  children,
  className = "",
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`card ${className}`}>
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-brand-700">{title}</h2>
          {subtitle ? (
            <p className="mt-1 text-sm text-slate-500">{subtitle}</p>
          ) : null}
        </div>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </div>
      {children}
    </section>
  );
}

export function StatusDot({ status }: { status: "ok" | "warn" | "error" | "idle" }) {
  const colors = {
    ok: "bg-emerald-500",
    warn: "bg-amber-500",
    error: "bg-red-500",
    idle: "bg-slate-300",
  };
  return (
    <span className={`inline-block h-2.5 w-2.5 rounded-full ${colors[status]}`} />
  );
}

export function StatusRow({
  label,
  value,
  status = "idle",
}: {
  label: string;
  value: string;
  status?: "ok" | "warn" | "error" | "idle";
}) {
  return (
    <div className="flex items-center justify-between gap-3 py-2 text-sm">
      <span className="text-slate-600">{label}</span>
      <span className="flex items-center gap-2 font-medium text-brand-900">
        <StatusDot status={status} />
        {value}
      </span>
    </div>
  );
}

export function Alert({
  tone = "info",
  children,
}: {
  tone?: "info" | "warn" | "error";
  children: ReactNode;
}) {
  const tones = {
    info: "border-brand-100 bg-brand-50 text-brand-700",
    warn: "border-amber-200 bg-amber-50 text-amber-800",
    error: "border-red-200 bg-red-50 text-red-800",
  };
  return (
    <div className={`rounded-lg border px-3 py-2 text-sm ${tones[tone]}`}>
      {children}
    </div>
  );
}

export function CollapsibleJson({ data }: { data: unknown }) {
  if (data === undefined || data === null) return null;
  return (
    <details className="mt-2">
      <summary className="cursor-pointer text-xs font-medium text-brand-500">
        View payload
      </summary>
      <pre className="mt-2 max-h-40 overflow-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">
        {JSON.stringify(data, null, 2)}
      </pre>
    </details>
  );
}
