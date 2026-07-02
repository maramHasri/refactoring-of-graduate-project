import type { useCamera } from "@/hooks/useCamera";
import { Card, Alert, StatusRow } from "@/components/ui/Card";

type CameraApi = ReturnType<typeof useCamera>;

export function CameraPreviewPanel({ camera }: { camera: CameraApi }) {

  const stateLabel = {
    idle: "Idle",
    requesting: "Requesting permission...",
    ready: "Ready",
    active: "Active",
    error: "Error",
  }[camera.state];

  const status =
    camera.state === "active"
      ? "ok"
      : camera.state === "error"
        ? "error"
        : camera.state === "requesting"
          ? "warn"
          : "idle";

  return (
    <Card
      title="Camera Preview"
      subtitle="Local webcam stream for monitoring validation"
      actions={
        <>
          <button type="button" className="btn-primary" onClick={() => void camera.start()}>
            Start Camera
          </button>
          <button type="button" className="btn-secondary" onClick={camera.stop}>
            Stop Camera
          </button>
          <button type="button" className="btn-ghost" onClick={() => void camera.restart()}>
            Restart
          </button>
        </>
      }
    >
      <StatusRow label="Camera" value={stateLabel} status={status} />
      {camera.error ? <Alert tone="error">{camera.error}</Alert> : null}
      <div className="mt-4 overflow-hidden rounded-xl border border-slate-200 bg-slate-900">
        <video
          ref={camera.attachVideo}
          autoPlay
          muted
          playsInline
          className="aspect-video w-full object-cover"
        />
      </div>
    </Card>
  );
}
