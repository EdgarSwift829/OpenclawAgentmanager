"use client";

import { useI18n } from "@/lib/i18n";

interface Props {
  events: any[];
}

export function Timeline({ events }: Props) {
  const { t } = useI18n();

  return (
    <div className="card">
      <h2>{t("iterationTimeline")}</h2>
      <div className="timeline">
        {events.length === 0 ? (
          <span style={{ color: "var(--text-secondary)", fontSize: "0.8125rem" }}>
            {t("noEventsYet")}
          </span>
        ) : (
          events
            .slice()
            .reverse()
            .map((event, i) => (
              <div key={i} className="timeline-entry">
                <span className="timeline-time">
                  {event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : "--:--"}
                </span>
                <span className="timeline-role">{event.role || event.type || "system"}</span>
                <span>
                  {event.type === "agent_message"
                    ? event.message?.slice(0, 100)
                    : event.type === "tool_call"
                    ? `${event.tool}(${JSON.stringify(event.args || {}).slice(0, 60)})`
                    : event.type === "error"
                    ? event.error?.slice(0, 100)
                    : event.type === "iteration_summary"
                    ? `[Iter ${event.iteration}] ${event.summary?.slice(0, 80)}`
                    : JSON.stringify(event).slice(0, 100)}
                </span>
              </div>
            ))
        )}
      </div>
    </div>
  );
}
