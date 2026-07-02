import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  buildWsUrl,
  formatIso,
  formatTimestamp,
  loadDevConfig,
  saveDevConfig,
  uid,
} from "@/config/monitoring";
import { ApiError, checkBackendHealth } from "@/services/apiClient";
import { proctoringApi } from "@/services/proctoringApi";
import { ProctoringWebSocketClient } from "@/services/proctoringWebSocket";
import type {
  ApiTestResult,
  AttemptSummary,
  AuditLog,
  ConnectionState,
  ConsoleEntry,
  DevConfig,
  LiveEvent,
  MonitoringLogEntry,
  PerformanceStats,
  ProctoringSession,
  ProctoringViolation,
} from "@/types/monitoring";

interface MonitoringDebugContextValue {
  config: DevConfig;
  setConfig: (patch: Partial<DevConfig>) => void;
  saveConfig: () => void;
  backendOk: boolean | null;
  backendMessage: string;
  wsState: ConnectionState;
  wsError: string | null;
  wsUrl: string;
  session: ProctoringSession | null;
  attempt: AttemptSummary | null;
  violations: ProctoringViolation[];
  auditLogs: AuditLog[];
  liveEvents: LiveEvent[];
  logs: MonitoringLogEntry[];
  consoleEntries: ConsoleEntry[];
  apiResults: ApiTestResult[];
  performance: PerformanceStats;
  connectWs: () => void;
  disconnectWs: () => void;
  reconnectWs: () => void;
  startMonitoring: () => Promise<void>;
  stopMonitoring: () => void;
  resetSession: () => void;
  refreshSessionData: () => Promise<void>;
  clearEvents: () => void;
  clearConsole: () => void;
  clearLogs: () => void;
  copyLogs: () => Promise<void>;
  downloadLogsJson: () => void;
  downloadLogsTxt: () => void;
  addLog: (
    severity: MonitoringLogEntry["severity"],
    category: string,
    message: string,
    details?: unknown,
  ) => void;
  runApiTest: (
    label: string,
    runner: () => Promise<unknown>,
    method: string,
    endpoint: string,
  ) => Promise<void>;
}

const MonitoringDebugContext = createContext<MonitoringDebugContextValue | null>(
  null,
);

export function MonitoringDebugProvider({ children }: { children: ReactNode }) {
  const [config, setConfigState] = useState<DevConfig>(loadDevConfig);
  const [backendOk, setBackendOk] = useState<boolean | null>(null);
  const [backendMessage, setBackendMessage] = useState("Checking backend...");
  const [wsState, setWsState] = useState<ConnectionState>("disconnected");
  const [wsError, setWsError] = useState<string | null>(null);
  const [session, setSession] = useState<ProctoringSession | null>(null);
  const [attempt, setAttempt] = useState<AttemptSummary | null>(null);
  const [violations, setViolations] = useState<ProctoringViolation[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [liveEvents, setLiveEvents] = useState<LiveEvent[]>([]);
  const [logs, setLogs] = useState<MonitoringLogEntry[]>([]);
  const [consoleEntries, setConsoleEntries] = useState<ConsoleEntry[]>([]);
  const [apiResults, setApiResults] = useState<ApiTestResult[]>([]);
  const [performance, setPerformance] = useState<PerformanceStats>({
    messagesReceived: 0,
    messagesPerMinute: 0,
    lastMessageTime: null,
    averageDelayMs: null,
    connectionDurationMs: 0,
    reconnectCount: 0,
  });

  const wsClientRef = useRef<ProctoringWebSocketClient | null>(null);
  const connectedAtRef = useRef<number | null>(null);
  const messageTimesRef = useRef<number[]>([]);
  const delaysRef = useRef<number[]>([]);
  const auditDeniedLoggedRef = useRef(false);

  const pushConsole = useCallback(
    (entry: Omit<ConsoleEntry, "id" | "timestamp">) => {
      setConsoleEntries((prev) =>
        [
          {
            id: uid(),
            timestamp: formatIso(),
            ...entry,
          },
          ...prev,
        ].slice(0, 500),
      );
    },
    [],
  );

  const addLog = useCallback(
    (
      severity: MonitoringLogEntry["severity"],
      category: string,
      message: string,
      details?: unknown,
    ) => {
      setLogs((prev) =>
        [
          {
            id: uid(),
            timestamp: formatIso(),
            severity,
            category,
            message,
            details,
          },
          ...prev,
        ].slice(0, 500),
      );
    },
    [],
  );

  const pushLiveEvent = useCallback(
    (eventType: string, source: LiveEvent["source"], payload?: unknown) => {
      setLiveEvents((prev) => {
        const next = [
          ...prev,
          {
            id: uid(),
            timestamp: formatTimestamp(),
            eventType,
            source,
            payload,
          },
        ];
        return next.slice(-300);
      });
      addLog("info", "event", eventType, payload);
    },
    [addLog],
  );

  const setConfig = useCallback((patch: Partial<DevConfig>) => {
    setConfigState((prev) => ({ ...prev, ...patch }));
  }, []);

  const saveConfig = useCallback(() => {
    saveDevConfig(config);
    addLog("info", "config", "Configuration saved to localStorage");
  }, [config, addLog]);

  const refreshSessionData = useCallback(async () => {
    if (!config.testId || !config.attemptId || !config.accessToken) return;

    try {
      const attemptRes = await proctoringApi.getAttempt(config);
      setAttempt(attemptRes.data.attempt);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        setAttempt(null);
      } else {
        pushConsole({
          kind: "error",
          message: "Failed to load attempt",
          details: error instanceof Error ? error.message : error,
        });
      }
    }

    try {
      const sessionRes = await proctoringApi.getSession(config);
      setSession(sessionRes.data.session);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        setSession(null);
      }
    }

    try {
      const violationsRes = await proctoringApi.listViolations(config);
      setViolations(violationsRes.data.violations);
    } catch (error) {
      if (!(error instanceof ApiError && error.status === 403)) {
        pushConsole({
          kind: "warn",
          message: "Could not load violations",
          details: error instanceof Error ? error.message : error,
        });
      }
    }

    try {
      const auditRes = await proctoringApi.listAuditLogs(config);
      setAuditLogs(auditRes.data.audit_logs);
      auditRes.data.audit_logs.forEach((row) => {
        addLog("info", row.action, `Audit: ${row.action}`, row.details);
      });
    } catch (error) {
      if (error instanceof ApiError && error.status === 403) {
        if (!auditDeniedLoggedRef.current) {
          auditDeniedLoggedRef.current = true;
          addLog(
            "warn",
            "audit",
            "Audit logs require proctor/admin access — use a teacher/admin token, or rely on Live Events",
          );
        }
      }
    }
  }, [config, pushConsole, addLog]);

  const runApiTest = useCallback(
    async (
      _label: string,
      runner: () => Promise<{ status: number; durationMs: number; data: unknown; meta: { method: string; endpoint: string } }>,
      method: string,
      endpoint: string,
    ) => {
      try {
        const result = await runner();
        setApiResults((prev) =>
          [
            {
              id: uid(),
              timestamp: formatIso(),
              method,
              endpoint,
              statusCode: result.status,
              durationMs: result.durationMs,
              response: result.data,
            },
            ...prev,
          ].slice(0, 50),
        );
        pushConsole({
          kind: "rest",
          message: `${method} ${endpoint} → ${result.status} (${result.durationMs}ms)`,
          details: result.data,
        });
      } catch (error) {
        const status = error instanceof ApiError ? error.status : null;
        const body = error instanceof ApiError ? error.body : null;
        setApiResults((prev) =>
          [
            {
              id: uid(),
              timestamp: formatIso(),
              method,
              endpoint,
              statusCode: status,
              durationMs: 0,
              response: body,
              error: error instanceof Error ? error.message : "Request failed",
            },
            ...prev,
          ].slice(0, 50),
        );
        pushConsole({
          kind: "error",
          message: `${method} ${endpoint} failed`,
          details: error instanceof Error ? error.message : error,
        });
      }
    },
    [pushConsole],
  );

  const connectWs = useCallback((onOpen?: () => void) => {
    wsClientRef.current?.disconnect();
    const client = new ProctoringWebSocketClient(
      config,
      (message) => {
        const now = Date.now();
        messageTimesRef.current.push(now);
        messageTimesRef.current = messageTimesRef.current.filter(
          (t) => now - t <= 60_000,
        );
        delaysRef.current.push(0);
        if (delaysRef.current.length > 100) delaysRef.current.shift();

        setPerformance((prev) => ({
          ...prev,
          messagesReceived: prev.messagesReceived + 1,
          messagesPerMinute: messageTimesRef.current.length,
          lastMessageTime: formatTimestamp(new Date()),
          averageDelayMs:
            delaysRef.current.length > 0
              ? Math.round(
                  delaysRef.current.reduce((a, b) => a + b, 0) /
                    delaysRef.current.length,
                )
              : null,
          connectionDurationMs: connectedAtRef.current
            ? now - connectedAtRef.current
            : 0,
          reconnectCount: client.getReconnectCount(),
        }));

        pushLiveEvent(message.type, "websocket", message.payload);
        pushConsole({
          kind: "websocket",
          message: `WS ← ${message.type}`,
          details: message.payload,
        });

        if (message.type === "session_started") {
          const payload = message.payload as { session?: ProctoringSession };
          if (payload?.session) setSession(payload.session);
        }
        if (message.type === "violation_triggered") {
          void refreshSessionData();
        }
        if (message.type === "error") {
          const payload = message.payload as { error?: string };
          setWsError(payload?.error ?? "WebSocket error");
          pushConsole({ kind: "error", message: payload?.error ?? "WS error" });
        }
      },
      (state, error) => {
        setWsState(state);
        setWsError(error ?? null);
        if (state === "connected") {
          connectedAtRef.current = Date.now();
          pushConsole({ kind: "info", message: "WebSocket connected" });
        }
        if (state === "disconnected") {
          connectedAtRef.current = null;
          pushConsole({ kind: "info", message: "WebSocket disconnected" });
        }
        if (state === "reconnecting") {
          pushConsole({
            kind: "reconnect",
            message: `Reconnect attempt #${client.getReconnectCount()}`,
          });
        }
        if (state === "error" && error) {
          pushConsole({ kind: "error", message: error });
        }
      },
    );
    wsClientRef.current = client;
    client.connect(onOpen);
  }, [config, pushLiveEvent, pushConsole, refreshSessionData]);

  const disconnectWs = useCallback(() => {
    wsClientRef.current?.disconnect();
  }, []);

  const reconnectWs = useCallback(() => {
    wsClientRef.current?.reconnect();
  }, []);

  const startMonitoring = useCallback(async () => {
    try {
      const result = await proctoringApi.startSession(config);
      setSession(result.data.session);
      pushLiveEvent("SESSION_STARTED", "rest", result.data);
      pushConsole({
        kind: "rest",
        message: "Monitoring session started (REST)",
        details: result.data,
      });
      addLog("info", "session", "Monitoring session started via REST");
      const sendJoin = () => {
        if (wsClientRef.current?.sendStudentJoined()) {
          pushConsole({ kind: "websocket", message: "WS → student_joined" });
        }
      };
      if (wsState === "connected") {
        sendJoin();
      } else {
        connectWs(sendJoin);
      }
      await refreshSessionData();
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : "Failed to start monitoring";
      addLog("error", "session", message);
      pushConsole({ kind: "error", message, details: message });
      if (message.includes("in-progress")) {
        addLog(
          "warn",
          "session",
          "Backend requires attempt status IN_PROGRESS to start session",
        );
      }
    }
  }, [
    config,
    wsState,
    connectWs,
    refreshSessionData,
    pushLiveEvent,
    pushConsole,
    addLog,
  ]);

  const stopMonitoring = useCallback(() => {
    addLog(
      "warn",
      "session",
      "Stop Monitoring: no dedicated backend terminate endpoint — disconnecting WebSocket only",
    );
    disconnectWs();
    addLog(
      "info",
      "session",
      "Backend session terminate API not implemented — session remains until attempt submit",
    );
  }, [disconnectWs, addLog]);

  const clearEvents = useCallback(() => setLiveEvents([]), []);
  const clearConsole = useCallback(() => setConsoleEntries([]), []);
  const clearLogs = useCallback(() => setLogs([]), []);

  const resetSession = useCallback(() => {
    addLog(
      "warn",
      "session",
      "Reset Session: backend not implemented yet — cleared local debug state only",
    );
    setSession(null);
    setViolations([]);
    setAuditLogs([]);
    setLiveEvents([]);
  }, [addLog]);

  const copyLogs = useCallback(async () => {
    await navigator.clipboard.writeText(JSON.stringify(logs, null, 2));
    addLog("info", "utility", "Logs copied to clipboard");
  }, [logs, addLog]);

  const downloadLogsJson = useCallback(() => {
    const blob = new Blob([JSON.stringify(logs, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `monitoring-logs-${Date.now()}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }, [logs]);

  const downloadLogsTxt = useCallback(() => {
    const text = logs
      .map(
        (log) =>
          `[${log.timestamp}] [${log.severity.toUpperCase()}] [${log.category}] ${log.message}`,
      )
      .join("\n");
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `monitoring-logs-${Date.now()}.txt`;
    anchor.click();
    URL.revokeObjectURL(url);
  }, [logs]);

  useEffect(() => {
    let active = true;
    void checkBackendHealth(config).then((result) => {
      if (!active) return;
      setBackendOk(result.ok);
      setBackendMessage(result.message);
    });
    return () => {
      active = false;
    };
  }, [config.apiBaseUrl]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      void refreshSessionData();
      if (connectedAtRef.current) {
        setPerformance((prev) => ({
          ...prev,
          connectionDurationMs: Date.now() - connectedAtRef.current!,
          reconnectCount: wsClientRef.current?.getReconnectCount() ?? 0,
        }));
      }
    }, 10_000);
    return () => window.clearInterval(interval);
  }, [refreshSessionData]);

  useEffect(
    () => () => {
      wsClientRef.current?.disconnect();
    },
    [],
  );

  const wsUrl = useMemo(() => {
    if (!config.testId || !config.attemptId) return "";
    return buildWsUrl(config);
  }, [config]);

  const value: MonitoringDebugContextValue = {
    config,
    setConfig,
    saveConfig,
    backendOk,
    backendMessage,
    wsState,
    wsError,
    wsUrl,
    session,
    attempt,
    violations,
    auditLogs,
    liveEvents,
    logs,
    consoleEntries,
    apiResults,
    performance,
    connectWs,
    disconnectWs,
    reconnectWs,
    startMonitoring,
    stopMonitoring,
    resetSession,
    refreshSessionData,
    clearEvents,
    clearConsole,
    clearLogs,
    copyLogs,
    downloadLogsJson,
    downloadLogsTxt,
    addLog,
    runApiTest,
  };

  return (
    <MonitoringDebugContext.Provider value={value}>
      {children}
    </MonitoringDebugContext.Provider>
  );
}

export function useMonitoringDebug() {
  const ctx = useContext(MonitoringDebugContext);
  if (!ctx) {
    throw new Error("useMonitoringDebug must be used within MonitoringDebugProvider");
  }
  return ctx;
}
