export type ConnectionState =
  | "disconnected"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "error";

export type MediaState = "idle" | "requesting" | "ready" | "active" | "error";

export type LogSeverity = "info" | "warn" | "error" | "debug";

export interface DevConfig {
  apiBaseUrl: string;
  wsBaseUrl: string;
  accessToken: string;
  workspaceId: string;
  testId: string;
  attemptId: string;
}

export interface LiveEvent {
  id: string;
  timestamp: string;
  eventType: string;
  source: "websocket" | "rest" | "local";
  payload?: unknown;
}

export interface MonitoringLogEntry {
  id: string;
  timestamp: string;
  severity: LogSeverity;
  category: string;
  message: string;
  details?: unknown;
}

export interface ConsoleEntry {
  id: string;
  timestamp: string;
  kind: "rest" | "websocket" | "error" | "warn" | "info" | "reconnect";
  message: string;
  details?: unknown;
}

export interface ApiTestResult {
  id: string;
  timestamp: string;
  method: string;
  endpoint: string;
  statusCode: number | null;
  durationMs: number;
  response: unknown;
  error?: string;
}

export interface ProctoringSession {
  id: number;
  test_attempt_id: number;
  workspace_id: number;
  status: string;
  started_at?: string;
  ended_at?: string | null;
  violation_score?: number;
  tab_switch_count?: number;
  violation_count?: number;
  event_count?: number;
}

export interface ProctoringViolation {
  id: number;
  session_id: number;
  violation_type: string;
  severity: string;
  score_contribution: number;
  description?: string;
  status: string;
  created_at?: string;
}

export interface AuditLog {
  id: number;
  session_id?: number;
  violation_id?: number | null;
  action: string;
  details?: unknown;
  created_at?: string;
}

export interface AttemptSummary {
  id: number;
  test_id: number;
  user_id: number;
  student_membership_id: number;
  status: string;
}

export interface PerformanceStats {
  messagesReceived: number;
  messagesPerMinute: number;
  lastMessageTime: string | null;
  averageDelayMs: number | null;
  connectionDurationMs: number;
  reconnectCount: number;
}
