import type { DevConfig } from "@/types/monitoring";

const STORAGE_KEY = "edu_forms_monitoring_debug_config";

export const DEFAULT_CONFIG: DevConfig = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || "",
  wsBaseUrl: import.meta.env.VITE_WS_BASE_URL || "ws://127.0.0.1:5000",
  accessToken: "",
  workspaceId: "",
  testId: "",
  attemptId: "",
};

export function loadDevConfig(): DevConfig {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_CONFIG };
    return { ...DEFAULT_CONFIG, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULT_CONFIG };
  }
}

export function saveDevConfig(config: DevConfig): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
}

export function buildWsUrl(config: DevConfig): string {
  const base = (config.wsBaseUrl || "ws://127.0.0.1:5000").replace(/\/$/, "");
  const token = encodeURIComponent(config.accessToken);
  const workspaceId = encodeURIComponent(config.workspaceId);
  return `${base}/ws/proctoring/tests/${config.testId}/attempts/${config.attemptId}?token=${token}&workspace_id=${workspaceId}`;
}

export function formatTimestamp(date = new Date()): string {
  return date.toLocaleTimeString("en-GB", { hour12: false });
}

export function formatIso(date = new Date()): string {
  return date.toISOString();
}

export function downloadText(filename: string, content: string, mime = "text/plain"): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function uid(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}
