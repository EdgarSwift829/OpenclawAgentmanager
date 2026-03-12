"use client";

import { useI18n } from "@/lib/i18n";

interface Props {
  events: any[];
}

// Event types to hide from timeline (internal system messages)
const HIDDEN_EVENTS = new Set(["connected", "pong", "history_replay"]);

// Event type -> icon/badge styling
const EVENT_STYLES: Record<string, { icon: string; color: string }> = {
  run_started:        { icon: "▶", color: "#22c55e" },
  run_complete:       { icon: "✓", color: "#22c55e" },
  run_cancelled:      { icon: "■", color: "#f59e0b" },
  run_error:          { icon: "✗", color: "#ef4444" },
  iteration_started:  { icon: "↻", color: "#3b82f6" },
  iteration_complete: { icon: "✓", color: "#3b82f6" },
  iteration_approved: { icon: "★", color: "#22c55e" },
  plan_created:       { icon: "📋", color: "#8b5cf6" },
  tasks_decomposed:   { icon: "📊", color: "#8b5cf6" },
  agent_activity:     { icon: "⚡", color: "#f59e0b" },
  task_started:       { icon: "→", color: "#6b7280" },
  task_complete:      { icon: "✓", color: "#22c55e" },
  task_timeout:       { icon: "⏱", color: "#ef4444" },
  task_error:         { icon: "✗", color: "#ef4444" },
  review_complete:    { icon: "🔍", color: "#8b5cf6" },
  dag_execution:      { icon: "⟂", color: "#3b82f6" },
  dag_layer_start:    { icon: "▸", color: "#6b7280" },
  parallel_start:     { icon: "⫘", color: "#3b82f6" },
};

function getEventDisplay(event: any): { text: string; icon: string; color: string } {
  const style = EVENT_STYLES[event.type] || { icon: "•", color: "#6b7280" };

  // Use the human-readable "message" field if present
  if (event.message) {
    return { text: event.message, ...style };
  }

  // Fallback formatting per event type
  switch (event.type) {
    case "run_started":
      return { text: `開始: ${event.agents?.length || 0}エージェント`, ...style };
    case "run_complete":
      return { text: `完了 (${event.iterations}回, ${event.elapsed_seconds}秒)`, ...style };
    case "run_error":
      return { text: `エラー: ${event.error?.slice(0, 100) || "不明"}`, ...style };
    case "iteration_started":
      return { text: `イテレーション ${event.iteration} 開始`, ...style };
    case "task_started":
      return { text: `${event.role}: ${event.task?.slice(0, 100) || ""}`, ...style };
    case "task_complete":
      return { text: `${event.role} 完了: ${event.summary?.slice(0, 100) || ""}`, ...style };
    case "review_complete":
      return {
        text: `レビュー: ${event.approved ? "承認" : "差し戻し"} (${event.score || "?"}点)`,
        icon: style.icon,
        color: event.approved ? "#22c55e" : "#ef4444",
      };
    default:
      // Skip raw JSON for unknown types
      return { text: event.type || "system event", ...style };
  }
}

export function Timeline({ events }: Props) {
  const { t } = useI18n();

  // Filter out internal system events
  const visibleEvents = events.filter((e) => !HIDDEN_EVENTS.has(e.type));

  return (
    <div className="card">
      <h2>{t("iterationTimeline")}</h2>
      <div className="timeline">
        {visibleEvents.length === 0 ? (
          <span style={{ color: "var(--text-secondary)", fontSize: "0.8125rem" }}>
            {t("noEventsYet")}
          </span>
        ) : (
          visibleEvents
            .slice()
            .reverse()
            .map((event, i) => {
              const display = getEventDisplay(event);
              return (
                <div key={i} className="timeline-entry">
                  <span className="timeline-time">
                    {event.timestamp
                      ? new Date(event.timestamp).toLocaleTimeString()
                      : "--:--"}
                  </span>
                  <span
                    className="timeline-icon"
                    style={{ color: display.color, minWidth: "1.5em", textAlign: "center" }}
                  >
                    {display.icon}
                  </span>
                  <span
                    className="timeline-role"
                    style={{ color: display.color }}
                  >
                    {event.role || ""}
                  </span>
                  <span className="timeline-message">
                    {display.text}
                  </span>
                </div>
              );
            })
        )}
      </div>
    </div>
  );
}
