/**
 * Browser-side proctoring event capture.
 * Arms only after the server pushes `session_started` on the student WebSocket.
 */

export type BrowserMonitorSend = (
  type: string,
  payload?: Record<string, unknown>,
) => boolean;

export class BrowserMonitor {
  private send: BrowserMonitorSend;
  private armed = false;
  private detachFns: Array<() => void> = [];

  constructor(send: BrowserMonitorSend) {
    this.send = send;
  }

  /** Call when WS receives `{ type: "session_started", ... }`. */
  arm(): void {
    if (this.armed || typeof window === "undefined") return;
    this.armed = true;
    this.attach();
    console.log("[BrowserMonitor] armed — listening for proctoring events");
  }

  disarm(): void {
    for (const off of this.detachFns) off();
    this.detachFns = [];
    this.armed = false;
    console.log("[BrowserMonitor] disarmed");
  }

  get isArmed(): boolean {
    return this.armed;
  }

  private attach(): void {
    const onVisibility = () => {
      if (document.hidden) {
        this.emit("tab_switch", { reason: "visibilitychange", hidden: true });
      }
    };
    const onBlur = () => {
      this.emit("window_blur", { reason: "blur" });
    };
    const onCopy = () => {
      this.emit("copy_paste", { action: "copy" });
    };
    const onPaste = () => {
      this.emit("copy_paste", { action: "paste" });
    };
    const onFullscreen = () => {
      if (!document.fullscreenElement) {
        this.emit("fullscreen_exit", { reason: "fullscreenchange" });
      }
    };

    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("blur", onBlur);
    document.addEventListener("copy", onCopy);
    document.addEventListener("paste", onPaste);
    document.addEventListener("fullscreenchange", onFullscreen);

    this.detachFns.push(() =>
      document.removeEventListener("visibilitychange", onVisibility),
    );
    this.detachFns.push(() => window.removeEventListener("blur", onBlur));
    this.detachFns.push(() => document.removeEventListener("copy", onCopy));
    this.detachFns.push(() => document.removeEventListener("paste", onPaste));
    this.detachFns.push(() =>
      document.removeEventListener("fullscreenchange", onFullscreen),
    );
  }

  private emit(type: string, payload: Record<string, unknown>): void {
    // TEMP TRACE
    console.log("[FRONTEND SEND]", JSON.stringify({ type, payload }));
    this.send(type, payload);
  }
}
