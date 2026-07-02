import { buildWsUrl } from "@/config/monitoring";
import type { ConnectionState, DevConfig } from "@/types/monitoring";

export type WsMessageHandler = (message: {
  type: string;
  payload: unknown;
  raw: string;
  receivedAt: number;
}) => void;

export type WsStateHandler = (
  state: ConnectionState,
  error?: string,
  meta?: { code?: number; reason?: string },
) => void;

export type WsOpenHandler = () => void;

export class ProctoringWebSocketClient {
  private socket: WebSocket | null = null;
  private config: DevConfig;
  private onMessage: WsMessageHandler;
  private onState: WsStateHandler;
  private intentionalClose = false;
  private reconnectAttempts = 0;
  private onOpen: WsOpenHandler | null = null;

  constructor(
    config: DevConfig,
    onMessage: WsMessageHandler,
    onState: WsStateHandler,
  ) {
    this.config = config;
    this.onMessage = onMessage;
    this.onState = onState;
  }

  getReconnectCount(): number {
    return this.reconnectAttempts;
  }

  getUrl(): string {
    return buildWsUrl(this.config);
  }

  connect(onOpen?: WsOpenHandler): void {
    this.onOpen = onOpen ?? null;
    if (!this.config.accessToken || !this.config.workspaceId) {
      this.onState("error", "Token and workspace ID are required");
      return;
    }
    if (!this.config.testId || !this.config.attemptId) {
      this.onState("error", "Test ID and Attempt ID are required");
      return;
    }

    this.intentionalClose = false;
    this.onState("connecting");

    try {
      this.socket = new WebSocket(this.getUrl());
    } catch (error) {
      this.onState(
        "error",
        error instanceof Error ? error.message : "Failed to create WebSocket",
      );
      return;
    }

    this.socket.onopen = () => {
      this.reconnectAttempts = 0;
      this.onState("connected");
      this.onOpen?.();
      this.onOpen = null;
    };

    this.socket.onmessage = (event) => {
      try {
        const parsed = JSON.parse(String(event.data));
        this.onMessage({
          type: parsed.type ?? "unknown",
          payload: parsed.payload ?? parsed,
          raw: String(event.data),
          receivedAt: performance.now(),
        });
      } catch {
        this.onMessage({
          type: "parse_error",
          payload: event.data,
          raw: String(event.data),
          receivedAt: performance.now(),
        });
      }
    };

    this.socket.onerror = () => {
      this.onState("error", "WebSocket connection error");
    };

    this.socket.onclose = (event) => {
      if (this.intentionalClose) {
        this.onState("disconnected");
        return;
      }
      const reason =
        event.reason ||
        (event.code ? `closed (code ${event.code})` : "connection closed");
      this.onState("reconnecting", reason);
      this.reconnectAttempts += 1;
      window.setTimeout(() => this.connect(), 2000);
    };
  }

  disconnect(): void {
    this.intentionalClose = true;
    this.socket?.close();
    this.socket = null;
    this.onState("disconnected");
  }

  reconnect(): void {
    this.disconnect();
    window.setTimeout(() => this.connect(), 300);
  }

  send(type: string, payload: Record<string, unknown> = {}): boolean {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      return false;
    }
    this.socket.send(JSON.stringify({ type, payload }));
    return true;
  }

  sendStudentJoined(): boolean {
    return this.send("student_joined", {
      device: { source: "monitoring-debug" },
      browser: { userAgent: navigator.userAgent },
    });
  }
}
