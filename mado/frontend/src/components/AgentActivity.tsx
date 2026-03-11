"use client";

import { useI18n } from "@/lib/i18n";

interface Agent {
  role: string;
  model: string;
  status: string;
}

interface Props {
  agents: Agent[];
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

export function AgentActivity({ agents }: Props) {
  const { t } = useI18n();

  return (
    <div className="card">
      <h2>{t("agentActivity")}</h2>
      {agents.length === 0 ? (
        <span style={{ color: "var(--text-secondary)", fontSize: "0.8125rem" }}>
          {t("noActiveAgents")}
        </span>
      ) : (
        <div className="agent-grid">
          {agents.map((agent) => (
            <div
              key={agent.role}
              className="agent-card"
              style={{ borderColor: ROLE_COLORS[agent.role] || "var(--border)" }}
            >
              <div className="role" style={{ color: ROLE_COLORS[agent.role] }}>
                {agent.role}
              </div>
              <div className="model">{agent.model}</div>
              <div style={{ marginTop: "0.25rem" }}>
                <span className={`badge badge-${agent.status === "active" ? "running" : "idle"}`}>
                  {agent.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
