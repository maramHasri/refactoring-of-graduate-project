import { useMonitoringDebug } from "@/context/MonitoringDebugContext";
import { Card, Alert } from "@/components/ui/Card";

export function MonitoringControlsPanel() {
  const {
    startMonitoring,
    stopMonitoring,
    resetSession,
    refreshSessionData,
  } = useMonitoringDebug();

  return (
    <Card
      title="Monitoring Controls"
      subtitle="Calls existing backend proctoring endpoints only"
      actions={
        <>
          <button
            type="button"
            className="btn-primary"
            onClick={() => void startMonitoring()}
          >
            Start Monitoring
          </button>
          <button type="button" className="btn-secondary" onClick={stopMonitoring}>
            Stop Monitoring
          </button>
          <button type="button" className="btn-ghost" onClick={resetSession}>
            Reset Session
          </button>
          <button
            type="button"
            className="btn-ghost"
            onClick={() => void refreshSessionData()}
          >
            Refresh
          </button>
        </>
      }
    >
      <Alert tone="info">
        Start Monitoring calls <code>POST .../proctoring/session</code> and sends{" "}
        <code>student_joined</code> over WebSocket when connected. Attempt must be{" "}
        <strong>IN_PROGRESS</strong> with proctoring enabled on the test.
      </Alert>
      <Alert tone="warn">
        Stop Monitoring disconnects WebSocket only — backend terminate endpoint not
        implemented yet. Reset Session clears local debug state only.
      </Alert>
    </Card>
  );
}
