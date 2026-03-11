"use client";

interface AgentInfo {
  role: string;
  model?: string;
  status: string;
  tasks_completed?: number;
  tasks_failed?: number;
  error?: string | null;
  current_task?: string;
}

interface Props {
  agents: AgentInfo[];
  events: any[];
}

const ROLE_COLORS: Record<string, string> = {
  cto: "#f59e0b",
  manager: "#3b82f6",
  researcher: "#8b5cf6",
  engineer: "#22c55e",
  reviewer: "#ec4899",
  tester: "#06b6d4",
  optimizer: "#f97316",
  documenter: "#64748b",
};

const ROLE_ICONS: Record<string, string> = {
  cto: "\uD83D\uDCCB",
  manager: "\uD83D\uDCC1",
  researcher: "\uD83D\uDD0D",
  engineer: "\u2699\uFE0F",
  reviewer: "\uD83D\uDCDD",
  tester: "\uD83E\uDDEA",
  optimizer: "\u26A1",
  documenter: "\uD83D\uDCD6",
};

function getStatusClass(status: string): string {
  switch (status) {
    case "active":
      return "tile-active";
    case "done":
    case "idle":
      return "tile-idle";
    case "error":
      return "tile-error";
    default:
      return "tile-idle";
  }
}

/** Get the latest event for an agent role. */
function getLatestOutput(role: string, events: any[]): string {
  for (let i = events.length - 1; i >= 0; i--) {
    const ev = events[i];
    if (ev.role === role || ev.sender === role) {
      if (ev.type === "agent_message") return ev.message?.slice(0, 200) || "";
      if (ev.type === "task_complete") return "Task completed";
      if (ev.type === "task_started")
        return `Working: ${ev.task?.slice(0, 120) || "..."}`;
      if (ev.type === "task_timeout") return `Timeout (${ev.timeout}s)`;
    }
  }
  return "";
}

export function AgentGrid({ agents, events }: Props) {
  if (agents.length === 0) {
    return (
      <div className="agent-grid-container">
        <div className="agent-grid-empty">
          <div className="agent-grid-empty-icon">{"\uD83D\uDC65"}</div>
          <div>Waiting for agents...</div>
          <div className="agent-grid-empty-sub">
            Start a run to spawn agents
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="agent-grid-container">
      <div className="conf-grid">
        {agents.map((agent) => {
          const color = ROLE_COLORS[agent.role] || "var(--accent)";
          const icon = ROLE_ICONS[agent.role] || "\uD83E\uDD16";
          const latestOutput = getLatestOutput(agent.role, events);
          const statusClass = getStatusClass(agent.status);

          return (
            <div
              key={agent.role}
              className={`conf-tile ${statusClass}`}
              style={{ "--tile-color": color } as React.CSSProperties}
            >
              {/* Status indicator (top-right dot like Zoom) */}
              <div className={`tile-status-dot tile-dot-${agent.status === "active" ? "active" : agent.status === "error" ? "error" : "idle"}`} />

              {/* Avatar / role icon area */}
              <div className="tile-avatar">
                <span className="tile-icon">{icon}</span>
              </div>

              {/* Output area (like video feed) */}
              <div className="tile-output">
                {agent.error ? (
                  <span className="tile-error-text">{agent.error}</span>
                ) : latestOutput ? (
                  <span className="tile-output-text">{latestOutput}</span>
                ) : (
                  <span className="tile-output-placeholder">
                    {agent.status === "active" ? "Processing..." : "Standby"}
                  </span>
                )}
              </div>

              {/* Name bar (bottom, like Zoom name bar) */}
              <div className="tile-namebar">
                <span className="tile-role">{agent.role.toUpperCase()}</span>
                {agent.model && (
                  <span className="tile-model">{agent.model}</span>
                )}
                {(agent.tasks_completed ?? 0) > 0 && (
                  <span className="tile-tasks">
                    {agent.tasks_completed} done
                    {(agent.tasks_failed ?? 0) > 0 &&
                      ` / ${agent.tasks_failed} fail`}
                  </span>
                )}
              </div>

              {/* Active animation ring */}
              {agent.status === "active" && (
                <div className="tile-speaking-ring" />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
