import { useMonitoringDebug } from "@/context/MonitoringDebugContext";
import { Card } from "@/components/ui/Card";

const severityColors = {
  info: "text-brand-500",
  warn: "text-amber-600",
  error: "text-red-600",
  debug: "text-slate-500",
};

export function MonitoringLogsPanel() {
  const {
    logs,
    clearLogs,
    downloadLogsJson,
    downloadLogsTxt,
    copyLogs,
  } = useMonitoringDebug();

  return (
    <Card
      title="Monitoring Logs"
      subtitle="Audit logs from backend + local debug events"
      actions={
        <>
          <button type="button" className="btn-ghost" onClick={clearLogs}>
            Clear Screen
          </button>
          <button type="button" className="btn-ghost" onClick={() => void copyLogs()}>
            Copy Logs
          </button>
          <button type="button" className="btn-ghost" onClick={downloadLogsJson}>
            Export JSON
          </button>
          <button type="button" className="btn-ghost" onClick={downloadLogsTxt}>
            Export TXT
          </button>
        </>
      }
    >
      <div className="max-h-80 overflow-y-auto rounded-lg border border-slate-200">
        <table className="w-full text-left text-sm">
          <thead className="sticky top-0 bg-slate-100 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-3 py-2">Time</th>
              <th className="px-3 py-2">Severity</th>
              <th className="px-3 py-2">Category</th>
              <th className="px-3 py-2">Message</th>
            </tr>
          </thead>
          <tbody>
            {logs.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-3 py-4 text-slate-500">
                  No logs yet. Events and audit logs will appear here.
                </td>
              </tr>
            ) : (
              logs.map((log) => (
                <tr key={log.id} className="border-t border-slate-100">
                  <td className="whitespace-nowrap px-3 py-2 text-xs text-slate-500">
                    {log.timestamp}
                  </td>
                  <td
                    className={`px-3 py-2 text-xs font-medium uppercase ${severityColors[log.severity]}`}
                  >
                    {log.severity}
                  </td>
                  <td className="px-3 py-2 text-xs">{log.category}</td>
                  <td className="px-3 py-2">{log.message}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
