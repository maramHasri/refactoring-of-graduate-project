import type { DevConfig } from "@/types/monitoring";

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export interface RequestMeta {
  method: string;
  endpoint: string;
  startedAt: number;
}

export async function apiRequest<T = unknown>(
  config: DevConfig,
  method: string,
  path: string,
  body?: unknown,
): Promise<{ data: T; meta: RequestMeta; status: number; durationMs: number }> {
  if (!config.accessToken) {
    throw new ApiError("Access token is required", 0, null);
  }
  if (!config.workspaceId) {
    throw new ApiError("Workspace ID is required", 0, null);
  }

  const base = config.apiBaseUrl.replace(/\/$/, "");
  const endpoint = `${base}${path}`;
  const startedAt = performance.now();

  const response = await fetch(endpoint, {
    method,
    headers: {
      Authorization: `Bearer ${config.accessToken}`,
      "X-Workspace-Id": config.workspaceId,
      "Content-Type": "application/json",
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  const durationMs = Math.round(performance.now() - startedAt);
  let data: unknown = null;
  const text = await response.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }

  if (!response.ok) {
    const message =
      typeof data === "object" && data && "error" in data
        ? String((data as { error: string }).error)
        : `HTTP ${response.status}`;
    throw new ApiError(message, response.status, data);
  }

  return {
    data: data as T,
    meta: { method, endpoint, startedAt },
    status: response.status,
    durationMs,
  };
}

export async function checkBackendHealth(
  config: DevConfig,
): Promise<{ ok: boolean; message: string }> {
  try {
    const base = config.apiBaseUrl.replace(/\/$/, "") || "";
    const response = await fetch(`${base}/health`, { method: "GET" });
    if (!response.ok) {
      return { ok: false, message: `Health check failed (${response.status})` };
    }
    return { ok: true, message: "Backend reachable" };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : "Backend unavailable",
    };
  }
}
