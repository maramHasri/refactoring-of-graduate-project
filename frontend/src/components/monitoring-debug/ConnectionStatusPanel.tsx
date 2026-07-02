import type { useCamera } from "@/hooks/useCamera";
import type { useMicrophone } from "@/hooks/useMicrophone";
import { useMonitoringDebug } from "@/context/MonitoringDebugContext";
import { Card, StatusRow } from "@/components/ui/Card";

type CameraApi = ReturnType<typeof useCamera>;
type MicrophoneApi = ReturnType<typeof useMicrophone>;

export function ConnectionStatusPanel({
  camera,
  microphone,
}: {
  camera: CameraApi;
  microphone: MicrophoneApi;
}) {
  const {
    backendOk,
    backendMessage,
    wsState,
    session,
    attempt,
  } = useMonitoringDebug();

  const wsStatus =
    wsState === "connected"
      ? "ok"
      : wsState === "connecting" || wsState === "reconnecting"
        ? "warn"
        : wsState === "error"
          ? "error"
          : "idle";

  return (
    <Card title="Connection Status" subtitle="Live monitoring session health">
      <div className="divide-y divide-slate-100">
        <StatusRow
          label="Backend Status"
          value={backendOk ? "Reachable" : backendMessage}
          status={backendOk ? "ok" : backendOk === false ? "error" : "warn"}
        />
        <StatusRow
          label="WebSocket"
          value={wsState.charAt(0).toUpperCase() + wsState.slice(1)}
          status={wsStatus}
        />
        <StatusRow
          label="Camera"
          value={
            camera.state === "active"
              ? "Ready"
              : camera.state === "error"
                ? "Error"
                : "Not active"
          }
          status={
            camera.state === "active"
              ? "ok"
              : camera.state === "error"
                ? "error"
                : "idle"
          }
        />
        <StatusRow
          label="Microphone"
          value={
            microphone.state === "active"
              ? "Ready"
              : microphone.state === "error"
                ? "Error"
                : "Not active"
          }
          status={
            microphone.state === "active"
              ? "ok"
              : microphone.state === "error"
                ? "error"
                : "idle"
          }
        />
        <StatusRow
          label="Monitoring Session"
          value={session?.status ?? "Not started"}
          status={
            session?.status === "ACTIVE"
              ? "ok"
              : session
                ? "warn"
                : "idle"
          }
        />
        <StatusRow
          label="Exam Attempt"
          value={attempt?.status ?? "Unknown"}
          status={
            attempt?.status === "IN_PROGRESS"
              ? "ok"
              : attempt
                ? "warn"
                : "idle"
          }
        />
      </div>
    </Card>
  );
}
