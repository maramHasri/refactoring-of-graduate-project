import { useMonitoringDebug } from "@/context/MonitoringDebugContext";
import { Card } from "@/components/ui/Card";

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const remSeconds = seconds % 60;
  return minutes > 0 ? `${minutes}m ${remSeconds}s` : `${seconds}s`;
}

export function SessionInfoPanel() {
  const { config, session, attempt, liveEvents, violations, wsState } =
    useMonitoringDebug();

  return (
    <Card title="Session Information" subtitle="Debugging identifiers and counters">
      <dl className="grid gap-3 text-sm sm:grid-cols-2">
        <Info label="Test ID" value={config.testId || "—"} />
        <Info label="Attempt ID" value={config.attemptId || "—"} />
        <Info
          label="Student ID"
          value={attempt?.user_id ? String(attempt.user_id) : "—"}
        />
        <Info
          label="Monitoring Session ID"
          value={session?.id ? String(session.id) : "—"}
        />
        <Info
          label="Connected Since"
          value={
            wsState === "connected" && session?.started_at
              ? session.started_at
              : "—"
          }
        />
        <Info
          label="Total Events"
          value={String(session?.event_count ?? liveEvents.length)}
        />
        <Info
          label="Total Violations"
          value={String(session?.violation_count ?? violations.length)}
        />
        <Info
          label="Warning Level (score)"
          value={String(session?.violation_score ?? 0)}
        />
        <Info
          label="Current Exam Status"
          value={attempt?.status ?? "—"}
        />
        <Info label="WebSocket" value={wsState} />
      </dl>
    </Card>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-100 px-3 py-2">
      <dt className="text-xs uppercase text-slate-500">{label}</dt>
      <dd className="mt-1 font-medium text-brand-900">{value}</dd>
    </div>
  );
}

export function PerformancePanel() {
  const { performance } = useMonitoringDebug();

  return (
    <Card title="Performance Information" subtitle="WebSocket traffic statistics">
      <dl className="grid gap-3 text-sm sm:grid-cols-2">
        <Info
          label="Messages Received"
          value={String(performance.messagesReceived)}
        />
        <Info
          label="Messages Per Minute"
          value={String(performance.messagesPerMinute)}
        />
        <Info
          label="Last Message Time"
          value={performance.lastMessageTime ?? "—"}
        />
        <Info
          label="Average Delay"
          value={
            performance.averageDelayMs !== null
              ? `${performance.averageDelayMs}ms`
              : "—"
          }
        />
        <Info
          label="Connection Duration"
          value={formatDuration(performance.connectionDurationMs)}
        />
        <Info
          label="Reconnect Count"
          value={String(performance.reconnectCount)}
        />
      </dl>
    </Card>
  );
}
