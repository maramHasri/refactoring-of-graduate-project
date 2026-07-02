import { useMonitoringDebug } from "@/context/MonitoringDebugContext";
import { proctoringApi } from "@/services/proctoringApi";
import { Card, CollapsibleJson } from "@/components/ui/Card";

export function ApiTesterPanel() {
  const { config, apiResults, runApiTest } = useMonitoringDebug();

  const tests = [
    {
      label: "Get Session",
      method: "GET",
      path: `/tests/${config.testId}/attempts/${config.attemptId}/proctoring/session`,
      run: () => proctoringApi.getSession(config),
    },
    {
      label: "Start Session",
      method: "POST",
      path: `/tests/${config.testId}/attempts/${config.attemptId}/proctoring/session`,
      run: () => proctoringApi.startSession(config),
    },
    {
      label: "List Violations",
      method: "GET",
      path: `/tests/${config.testId}/attempts/${config.attemptId}/proctoring/violations`,
      run: () => proctoringApi.listViolations(config),
    },
    {
      label: "List Audit Logs",
      method: "GET",
      path: `/tests/${config.testId}/attempts/${config.attemptId}/proctoring/audit-logs`,
      run: () => proctoringApi.listAuditLogs(config),
    },
    {
      label: "Ingest Event (FACE_DETECTED)",
      method: "POST",
      path: `/tests/${config.testId}/attempts/${config.attemptId}/proctoring/events`,
      run: () =>
        proctoringApi.ingestEvent(config, "FACE_DETECTED", {
          source: "monitoring-debug",
        }),
    },
    {
      label: "Get Attempt",
      method: "GET",
      path: `/tests/${config.testId}/attempts/${config.attemptId}`,
      run: () => proctoringApi.getAttempt(config),
    },
  ];

  return (
    <Card title="API Tester" subtitle="Execute proctoring REST endpoints">
      <div className="mb-4 flex flex-wrap gap-2">
        {tests.map((test) => (
          <button
            key={test.label}
            type="button"
            className="btn-secondary text-xs"
            onClick={() => void runApiTest(test.label, test.run, test.method, test.path)}
          >
            {test.method} {test.label}
          </button>
        ))}
      </div>
      <div className="max-h-96 space-y-3 overflow-y-auto">
        {apiResults.length === 0 ? (
          <p className="text-sm text-slate-500">Run an API test to see results.</p>
        ) : (
          apiResults.map((result) => (
            <div
              key={result.id}
              className="rounded-lg border border-slate-200 p-3 text-sm"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded bg-brand-50 px-2 py-0.5 text-xs font-semibold text-brand-700">
                  {result.method}
                </span>
                <code className="text-xs text-slate-600">{result.endpoint}</code>
                <span
                  className={`ml-auto text-xs font-medium ${
                    result.statusCode && result.statusCode < 400
                      ? "text-emerald-600"
                      : "text-red-600"
                  }`}
                >
                  {result.statusCode ?? "ERR"} · {result.durationMs}ms
                </span>
              </div>
              {result.error ? (
                <p className="mt-2 text-red-600">{result.error}</p>
              ) : null}
              <CollapsibleJson data={result.response} />
            </div>
          ))
        )}
      </div>
    </Card>
  );
}
