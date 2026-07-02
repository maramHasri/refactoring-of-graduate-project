import { apiRequest } from "@/services/apiClient";
import type { DevConfig } from "@/types/monitoring";
import type {
  AttemptSummary,
  AuditLog,
  ProctoringSession,
  ProctoringViolation,
} from "@/types/monitoring";

function attemptPath(config: DevConfig, suffix: string): string {
  return `/tests/${config.testId}/attempts/${config.attemptId}${suffix}`;
}

export const proctoringApi = {
  startSession(config: DevConfig, metadata?: Record<string, unknown>) {
    return apiRequest<{ message: string; session: ProctoringSession }>(
      config,
      "POST",
      attemptPath(config, "/proctoring/session"),
      {
        device_metadata: metadata?.device ?? { source: "monitoring-debug" },
        browser_metadata: metadata?.browser ?? {
          userAgent: navigator.userAgent,
          source: "monitoring-debug",
        },
      },
    );
  },

  getSession(config: DevConfig) {
    return apiRequest<{ session: ProctoringSession }>(
      config,
      "GET",
      attemptPath(config, "/proctoring/session"),
    );
  },

  ingestEvent(
    config: DevConfig,
    eventType: string,
    payload?: Record<string, unknown>,
  ) {
    return apiRequest(config, "POST", attemptPath(config, "/proctoring/events"), {
      event_type: eventType,
      payload: payload ?? {},
    });
  },

  listViolations(config: DevConfig) {
    return apiRequest<{ violations: ProctoringViolation[]; count: number }>(
      config,
      "GET",
      attemptPath(config, "/proctoring/violations"),
    );
  },

  listAuditLogs(config: DevConfig) {
    return apiRequest<{ audit_logs: AuditLog[]; count: number }>(
      config,
      "GET",
      attemptPath(config, "/proctoring/audit-logs"),
    );
  },

  getAttempt(config: DevConfig) {
    return apiRequest<{ attempt: AttemptSummary }>(
      config,
      "GET",
      attemptPath(config, ""),
    );
  },
};
