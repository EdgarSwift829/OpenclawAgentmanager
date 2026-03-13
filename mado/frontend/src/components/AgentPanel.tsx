"use client";

import { useState, useEffect, useCallback } from "react";
import * as api from "@/lib/api";
import { useI18n, type Locale } from "@/lib/i18n";
import { useInlineStatus, StatusIndicator } from "@/components/Toast";
import { ROLE_META } from "@/lib/constants";

interface AgentProfile {
  title: string;
  personality: string;
}

interface Props {
  activeProject: string | null;
  agentProfiles: Record<string, AgentProfile>;
  runtimeAgents: any[]; // agents from listAgents (active session)
}

// Roles available for adding
const ADDABLE_ROLES = Object.keys(ROLE_META);

export function AgentPanel({ activeProject, agentProfiles, runtimeAgents }: Props) {
  const { t, locale } = useI18n();
  const loc = locale as Locale;
  const { status, showStatus } = useInlineStatus();

  // Assignments from config (agents.yaml)
  const [assignments, setAssignments] = useState<Record<string, string>>({});
  const [showAddMenu, setShowAddMenu] = useState(false);

  const loadAssignments = useCallback(async () => {
    try {
      const data = await api.getAssignments();
      setAssignments(data.assignments || {});
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    loadAssignments();
  }, [loadAssignments]);

  // Merge: config roles as base, runtime agents overlay status
  const runtimeMap = new Map(runtimeAgents.map((a) => [a.role, a]));
  const configuredRoles = Object.keys(assignments);

  // Roles that are in config but not added yet (for add menu)
  const addableRoles = ADDABLE_ROLES.filter((r) => !configuredRoles.includes(r));

  const handleAddRole = async (role: string) => {
    // Add with default model
    try {
      await api.switchModel(role, Object.values(assignments)[0] || "qwen3.5-9b");
      await loadAssignments();
      showStatus(`${ROLE_META[role]?.label[loc] || role} を追加しました`, "success");
    } catch (e: any) {
      showStatus(`追加エラー: ${e.message}`, "error");
    }
    setShowAddMenu(false);
  };

  return (
    <div className="agents-tab-content">
      <div className="agents-tab-header">
        <h3 className="agents-tab-title">{t("agentsTab")}</h3>
        {status && <StatusIndicator status={status} />}
      </div>

      {configuredRoles.length === 0 ? (
        <div className="agents-tab-empty">
          <p>{t("noAgentsYet")}</p>
        </div>
      ) : (
        <div className="agents-tab-list">
          {configuredRoles.map((role) => {
            const meta = ROLE_META[role] || { icon: "\uD83E\uDD16", label: { en: role, ja: role } };
            const profile = agentProfiles[role];
            const runtime = runtimeMap.get(role);
            const model = runtime?.model || assignments[role] || "\u2014";
            const isActive = !!runtime;

            return (
              <div key={role} className={`agents-tab-card ${isActive ? "agents-tab-card-active" : ""}`}>
                <div className="agents-tab-card-header">
                  <span className="agents-tab-card-icon">{meta.icon}</span>
                  <div className="agents-tab-card-info">
                    <span className="agents-tab-card-role">
                      {profile?.title || meta.label[loc]}
                    </span>
                    <span className="agents-tab-card-model">{model}</span>
                  </div>
                  <span className={`agents-tab-card-status ${isActive ? "agents-tab-status-active" : "agents-tab-status-idle"}`}>
                    {isActive ? t("running") : t("initialized")}
                  </span>
                </div>
                {profile?.personality && (
                  <div className="agents-tab-card-desc">{profile.personality}</div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Add agent button */}
      {addableRoles.length > 0 && (
        <div className="agents-tab-add-section">
          <button
            className="agents-tab-add-btn"
            onClick={() => setShowAddMenu(!showAddMenu)}
          >
            + {loc === "ja" ? "エージェント追加" : "Add Agent"}
          </button>
          {showAddMenu && (
            <div className="agents-tab-add-menu">
              {addableRoles.map((role) => {
                const meta = ROLE_META[role] || { icon: "\uD83E\uDD16", label: { en: role, ja: role } };
                return (
                  <button
                    key={role}
                    className="agents-tab-add-item"
                    onClick={() => handleAddRole(role)}
                  >
                    <span>{meta.icon}</span>
                    <span>{meta.label[loc]}</span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
