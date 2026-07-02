import type { useMicrophone } from "@/hooks/useMicrophone";
import { Card, Alert, StatusRow } from "@/components/ui/Card";

type MicrophoneApi = ReturnType<typeof useMicrophone>;

export function MicrophonePanel({ microphone: mic }: { microphone: MicrophoneApi }) {

  const stateLabel = {
    idle: "Idle",
    requesting: "Requesting permission...",
    ready: "Ready",
    active: "Active",
    error: "Error",
  }[mic.state];

  const status =
    mic.state === "active"
      ? "ok"
      : mic.state === "error"
        ? "error"
        : mic.state === "requesting"
          ? "warn"
          : "idle";

  return (
    <Card
      title="Microphone"
      subtitle="Microphone permission and activity level"
      actions={
        <>
          <button type="button" className="btn-primary" onClick={() => void mic.start()}>
            Start Microphone
          </button>
          <button type="button" className="btn-secondary" onClick={mic.stop}>
            Stop Microphone
          </button>
          <button type="button" className="btn-ghost" onClick={() => void mic.restart()}>
            Restart
          </button>
        </>
      }
    >
      <StatusRow label="Microphone" value={stateLabel} status={status} />
      {mic.state === "active" ? (
        <div className="mt-3">
          <div className="label">Activity level</div>
          <div className="h-2 overflow-hidden rounded-full bg-slate-200">
            <div
              className="h-full rounded-full bg-brand-500 transition-all"
              style={{ width: `${Math.min(100, mic.level)}%` }}
            />
          </div>
        </div>
      ) : null}
      {mic.error ? <Alert tone="error">{mic.error}</Alert> : null}
    </Card>
  );
}
