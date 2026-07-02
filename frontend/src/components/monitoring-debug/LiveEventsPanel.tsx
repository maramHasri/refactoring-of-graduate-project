import { useEffect, useRef } from "react";
import { useMonitoringDebug } from "@/context/MonitoringDebugContext";
import { Card, CollapsibleJson } from "@/components/ui/Card";

export function LiveEventsPanel() {
  const { liveEvents, clearEvents } = useMonitoringDebug();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [liveEvents.length]);

  return (
    <Card
      title="Live Events Panel"
      subtitle="WebSocket and REST events in real time"
      actions={
        <button type="button" className="btn-ghost" onClick={clearEvents}>
          Clear Events
        </button>
      }
    >
      <div className="max-h-96 space-y-3 overflow-y-auto rounded-lg border border-slate-200 bg-slate-50 p-3">
        {liveEvents.length === 0 ? (
          <p className="text-sm text-slate-500">No events yet. Connect WebSocket or start monitoring.</p>
        ) : (
          liveEvents.map((event, index) => (
            <div
              key={event.id}
              className={`py-3 ${index < liveEvents.length - 1 ? "border-b border-slate-200" : ""}`}
            >
              <div className="text-xs font-medium text-slate-500">{event.timestamp}</div>
              <div className="mt-1 font-semibold text-brand-700">{event.eventType}</div>
              <div className="text-xs text-slate-500">Source: {event.source}</div>
              <CollapsibleJson data={event.payload} />
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </Card>
  );
}
