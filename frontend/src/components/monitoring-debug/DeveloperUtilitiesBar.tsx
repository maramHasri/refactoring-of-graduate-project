import { useMonitoringDebug } from "@/context/MonitoringDebugContext";

export function DeveloperUtilitiesBar({
  onRestartCamera,
  onRestartMicrophone,
}: {
  onRestartCamera: () => void;
  onRestartMicrophone: () => void;
}) {
  const {
    copyLogs,
    downloadLogsJson,
    downloadLogsTxt,
    clearEvents,
    clearConsole,
    reconnectWs,
  } = useMonitoringDebug();

  return (
    <section className="card bg-slate-900 text-white">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-300">
        Developer Utilities
      </h2>
      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" className="btn-secondary" onClick={() => void copyLogs()}>
          Copy Logs
        </button>
        <button type="button" className="btn-secondary" onClick={downloadLogsJson}>
          Download JSON
        </button>
        <button type="button" className="btn-secondary" onClick={downloadLogsTxt}>
          Download TXT
        </button>
        <button type="button" className="btn-secondary" onClick={clearEvents}>
          Clear Events
        </button>
        <button type="button" className="btn-secondary" onClick={clearConsole}>
          Clear Console
        </button>
        <button type="button" className="btn-secondary" onClick={reconnectWs}>
          Reconnect WebSocket
        </button>
        <button type="button" className="btn-secondary" onClick={onRestartCamera}>
          Restart Camera
        </button>
        <button type="button" className="btn-secondary" onClick={onRestartMicrophone}>
          Restart Microphone
        </button>
      </div>
    </section>
  );
}
