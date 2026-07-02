import { useMonitoringDebug } from "@/context/MonitoringDebugContext";
import { Card } from "@/components/ui/Card";

const kindColors = {
  rest: "text-brand-500",
  websocket: "text-violet-600",
  error: "text-red-600",
  warn: "text-amber-600",
  info: "text-slate-600",
  reconnect: "text-orange-600",
};

export function DevConsolePanel() {
  const { consoleEntries, clearConsole } = useMonitoringDebug();

  return (
    <Card
      title="Developer Console"
      subtitle="REST, WebSocket, errors, and reconnect attempts"
      actions={
        <button type="button" className="btn-ghost" onClick={clearConsole}>
          Clear Console
        </button>
      }
    >
      <div className="max-h-80 overflow-y-auto rounded-lg bg-slate-900 p-3 font-mono text-xs text-slate-100">
        {consoleEntries.length === 0 ? (
          <p className="text-slate-400">Console empty.</p>
        ) : (
          consoleEntries.map((entry) => (
            <div key={entry.id} className="mb-2 border-b border-slate-700 pb-2">
              <span className="text-slate-500">{entry.timestamp}</span>{" "}
              <span className={kindColors[entry.kind]}>[{entry.kind}]</span>{" "}
              {entry.message}
            </div>
          ))
        )}
      </div>
    </Card>
  );
}
