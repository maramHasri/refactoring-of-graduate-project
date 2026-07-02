import { MonitoringDebugProvider } from "@/context/MonitoringDebugContext";
import { DevConfigPanel } from "@/components/monitoring-debug/DevConfigPanel";
import { ConnectionStatusPanel } from "@/components/monitoring-debug/ConnectionStatusPanel";
import { CameraPreviewPanel } from "@/components/monitoring-debug/CameraPreviewPanel";
import { MicrophonePanel } from "@/components/monitoring-debug/MicrophonePanel";
import { WebSocketPanel } from "@/components/monitoring-debug/WebSocketPanel";
import { MonitoringControlsPanel } from "@/components/monitoring-debug/MonitoringControlsPanel";
import { LiveEventsPanel } from "@/components/monitoring-debug/LiveEventsPanel";
import { MonitoringLogsPanel } from "@/components/monitoring-debug/MonitoringLogsPanel";
import { ViolationsPanel } from "@/components/monitoring-debug/ViolationsPanel";
import {
  PerformancePanel,
  SessionInfoPanel,
} from "@/components/monitoring-debug/SessionInfoPanel";
import { ApiTesterPanel } from "@/components/monitoring-debug/ApiTesterPanel";
import { DevConsolePanel } from "@/components/monitoring-debug/DevConsolePanel";
import { DeveloperUtilitiesBar } from "@/components/monitoring-debug/DeveloperUtilitiesBar";
import { useCamera } from "@/hooks/useCamera";
import { useMicrophone } from "@/hooks/useMicrophone";

function MonitoringDebugContent() {
  const camera = useCamera();
  const microphone = useMicrophone();

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-5 lg:px-8">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-brand-500">
              DEV ONLY
            </p>
            <h1 className="text-2xl font-bold text-brand-700">Monitoring Debug</h1>
            <p className="mt-1 text-sm text-slate-600">
              Validate proctoring camera, microphone, WebSocket, and backend APIs
              before exam integration.
            </p>
          </div>
          <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800">
            Not for production
          </span>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-6 px-4 py-8 lg:px-8">
        <DevConfigPanel />
        <ConnectionStatusPanel camera={camera} microphone={microphone} />

        <div className="grid gap-6 lg:grid-cols-2">
          <CameraPreviewPanel camera={camera} />
          <MicrophonePanel microphone={microphone} />
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <WebSocketPanel />
          <MonitoringControlsPanel />
        </div>

        <div className="grid gap-6 xl:grid-cols-2">
          <LiveEventsPanel />
          <ViolationsPanel />
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <SessionInfoPanel />
          <PerformancePanel />
        </div>

        <MonitoringLogsPanel />
        <ApiTesterPanel />
        <DevConsolePanel />
        <DeveloperUtilitiesBar
          onRestartCamera={() => void camera.restart()}
          onRestartMicrophone={() => void microphone.restart()}
        />
      </main>
    </div>
  );
}

export function MonitoringDebugPage() {
  if (!import.meta.env.DEV) {
    return (
      <div className="flex min-h-screen items-center justify-center p-8 text-center">
        <div>
          <h1 className="text-xl font-bold text-brand-700">Development Only</h1>
          <p className="mt-2 text-slate-600">
            The Monitoring Debug module is not available in production builds.
          </p>
        </div>
      </div>
    );
  }

  return (
    <MonitoringDebugProvider>
      <MonitoringDebugContent />
    </MonitoringDebugProvider>
  );
}
