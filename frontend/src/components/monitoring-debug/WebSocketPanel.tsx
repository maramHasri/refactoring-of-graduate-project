import { useMonitoringDebug } from "@/context/MonitoringDebugContext";
import { Card, Alert, StatusRow } from "@/components/ui/Card";

export function WebSocketPanel() {
  const {
    wsState,
    wsError,
    wsUrl,
    connectWs,
    disconnectWs,
    reconnectWs,
  } = useMonitoringDebug();

  const status =
    wsState === "connected"
      ? "ok"
      : wsState === "error"
        ? "error"
        : wsState === "connecting" || wsState === "reconnecting"
          ? "warn"
          : "idle";

  return (
    <Card
      title="WebSocket Connection"
      subtitle="Proctoring real-time channel"
      actions={
        <>
          <button type="button" className="btn-primary" onClick={connectWs}>
            Connect
          </button>
          <button type="button" className="btn-secondary" onClick={disconnectWs}>
            Disconnect
          </button>
          <button type="button" className="btn-ghost" onClick={reconnectWs}>
            Reconnect
          </button>
        </>
      }
    >
      <StatusRow
        label="Current Status"
        value={wsState.charAt(0).toUpperCase() + wsState.slice(1)}
        status={status}
      />
      {wsError ? <Alert tone="error">{wsError}</Alert> : null}
      <div className="mt-3">
        <div className="label">WebSocket URL</div>
        <code className="block break-all rounded-lg bg-slate-100 p-3 text-xs text-slate-700">
          {wsUrl || "Configure test ID, attempt ID, token, and workspace ID"}
        </code>
      </div>
    </Card>
  );
}
