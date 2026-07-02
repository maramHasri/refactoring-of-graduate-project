import { useMemo } from "react";
import { useMonitoringDebug } from "@/context/MonitoringDebugContext";
import { Card } from "@/components/ui/Card";

export function ViolationsPanel() {
  const { violations } = useMonitoringDebug();

  const summary = useMemo(() => {
    const warnings = violations.filter((v) => v.severity === "LOW").length;
    const serious = violations.filter(
      (v) => v.severity === "MEDIUM" || v.severity === "HIGH",
    ).length;
    const latest = violations[0];
    return {
      warnings,
      violations: serious,
      severity: latest?.severity ?? "None",
      action: latest?.status ?? "None",
    };
  }, [violations]);

  return (
    <Card title="Violations Panel" subtitle="Real-time violation summary from backend">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Metric label="Warnings (LOW)" value={String(summary.warnings)} />
        <Metric label="Violations (MED/HIGH)" value={String(summary.violations)} />
        <Metric label="Current Severity" value={summary.severity} />
        <Metric label="Current Action" value={summary.action} />
      </div>
      {violations.length > 0 ? (
        <ul className="mt-4 space-y-2 text-sm">
          {violations.slice(0, 5).map((v) => (
            <li
              key={v.id}
              className="rounded-lg border border-slate-200 px-3 py-2"
            >
              <span className="font-medium">{v.violation_type}</span>
              <span className="ml-2 text-xs text-slate-500">({v.severity})</span>
              {v.description ? (
                <p className="mt-1 text-slate-600">{v.description}</p>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-sm text-slate-500">No violations loaded yet.</p>
      )}
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-brand-50 p-3 text-center">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-xl font-bold text-brand-700">{value}</div>
    </div>
  );
}
