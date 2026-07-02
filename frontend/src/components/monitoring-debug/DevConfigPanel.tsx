import { useMonitoringDebug } from "@/context/MonitoringDebugContext";

export function DevConfigPanel() {
  const { config, setConfig, saveConfig } = useMonitoringDebug();

  return (
    <section className="card border-dashed border-brand-100 bg-brand-50/40">
      <h2 className="text-base font-semibold text-brand-700">Developer Configuration</h2>
      <p className="mt-1 text-sm text-slate-600">
        Paste credentials from <code>POST /auth/login</code>. Saved to localStorage only.
      </p>
      <div className="mt-4 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Field
          label="API Base URL (empty = proxy)"
          value={config.apiBaseUrl}
          onChange={(v) => setConfig({ apiBaseUrl: v })}
          placeholder="http://127.0.0.1:5000"
        />
        <Field
          label="WebSocket Base URL"
          value={config.wsBaseUrl}
          onChange={(v) => setConfig({ wsBaseUrl: v })}
          placeholder="ws://127.0.0.1:5000"
        />
        <Field
          label="Workspace ID"
          value={config.workspaceId}
          onChange={(v) => setConfig({ workspaceId: v })}
        />
        <Field
          label="Test ID"
          value={config.testId}
          onChange={(v) => setConfig({ testId: v })}
        />
        <Field
          label="Attempt ID"
          value={config.attemptId}
          onChange={(v) => setConfig({ attemptId: v })}
        />
        <div className="md:col-span-2">
          <label className="label">Access Token (JWT)</label>
          <textarea
            className="input min-h-[80px] font-mono text-xs"
            value={config.accessToken}
            onChange={(e) => setConfig({ accessToken: e.target.value })}
            placeholder="eyJhbG..."
          />
        </div>
      </div>
      <div className="mt-4">
        <button type="button" className="btn-primary" onClick={saveConfig}>
          Save Configuration
        </button>
      </div>
    </section>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <div>
      <label className="label">{label}</label>
      <input
        className="input"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
