import { useCallback, useEffect, useRef, useState } from "react";
import type { MediaState } from "@/types/monitoring";

export function useCamera() {
  const [state, setState] = useState<MediaState>("idle");
  const [error, setError] = useState<string | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const attachVideo = useCallback((video: HTMLVideoElement | null) => {
    videoRef.current = video;
    if (video && streamRef.current) {
      video.srcObject = streamRef.current;
      void video.play().catch(() => undefined);
    }
  }, []);

  const start = useCallback(async () => {
    setState("requesting");
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user" },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setState("active");
    } catch (err) {
      const message =
        err instanceof DOMException && err.name === "NotAllowedError"
          ? "Camera permission denied"
          : err instanceof Error
            ? err.message
            : "Camera initialization failed";
      setError(message);
      setState("error");
    }
  }, []);

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setState("idle");
    setError(null);
  }, []);

  const restart = useCallback(async () => {
    stop();
    await start();
  }, [start, stop]);

  useEffect(() => () => stop(), [stop]);

  return { state, error, start, stop, restart, attachVideo };
}
