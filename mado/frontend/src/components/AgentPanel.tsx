"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import * as api from "@/lib/api";
import { useI18n, type Locale } from "@/lib/i18n";
import { useInlineStatus, StatusIndicator } from "@/components/Toast";

interface AgentProfile {
  title: string;
  personality: string;
}

interface Props {
  activeProject: string | null;
  agentProfiles: Record<string, AgentProfile>;
  runtimeAgents: any[];
  onProfilesChange?: (profiles: Record<string, AgentProfile>) => void;
}

const AGENT_ROLES: {
  key: string;
  icon: string;
  label: { en: string; ja: string };
  defaultTitle: { en: string; ja: string };
  shortDesc: { en: string; ja: string };
}[] = [
  {
    key: "cto",
    icon: "\uD83C\uDFD7",
    label: { en: "CTO", ja: "CTO" },
    defaultTitle: { en: "Chief Technology Officer", ja: "最高技術責任者" },
    shortDesc: { en: "Architecture & Planning", ja: "設計・計画" },
  },
  {
    key: "manager",
    icon: "\uD83D\uDCCB",
    label: { en: "PM", ja: "PM" },
    defaultTitle: { en: "Project Manager", ja: "プロジェクトマネージャー" },
    shortDesc: { en: "Task Management", ja: "タスク管理" },
  },
  {
    key: "researcher",
    icon: "\uD83D\uDD0D",
    label: { en: "Researcher", ja: "リサーチャー" },
    defaultTitle: { en: "Technical Researcher", ja: "テクニカルリサーチャー" },
    shortDesc: { en: "Research & Analysis", ja: "調査・分析" },
  },
  {
    key: "engineer",
    icon: "\u2699\uFE0F",
    label: { en: "Engineer", ja: "エンジニア" },
    defaultTitle: { en: "Full-Stack Developer", ja: "フルスタック開発者" },
    shortDesc: { en: "Code Generation", ja: "コード生成" },
  },
  {
    key: "reviewer",
    icon: "\uD83D\uDCDD",
    label: { en: "Reviewer", ja: "レビュアー" },
    defaultTitle: { en: "Code Quality Lead", ja: "コード品質リード" },
    shortDesc: { en: "Code Review", ja: "コードレビュー" },
  },
  {
    key: "tester",
    icon: "\uD83E\uDDEA",
    label: { en: "Tester", ja: "テスター" },
    defaultTitle: { en: "QA Engineer", ja: "QAエンジニア" },
    shortDesc: { en: "Testing", ja: "テスト" },
  },
  {
    key: "optimizer",
    icon: "\u26A1",
    label: { en: "Optimizer", ja: "オプティマイザー" },
    defaultTitle: { en: "Performance Engineer", ja: "パフォーマンスエンジニア" },
    shortDesc: { en: "Optimization", ja: "最適化" },
  },
  {
    key: "documenter",
    icon: "\uD83D\uDCD6",
    label: { en: "Documenter", ja: "ドキュメンター" },
    defaultTitle: { en: "Technical Writer", ja: "テクニカルライター" },
    shortDesc: { en: "Documentation", ja: "ドキュメント" },
  },
  {
    key: "marketer",
    icon: "\uD83D\uDCE2",
    label: { en: "Marketer", ja: "マーケター" },
    defaultTitle: { en: "Growth Specialist", ja: "グロース担当" },
    shortDesc: { en: "Marketing", ja: "マーケティング" },
  },
];

// Default roles that are always pre-registered
const DEFAULT_ROLES = ["cto", "manager", "researcher", "engineer", "reviewer", "tester", "documenter"];

const PROVIDER_BADGE: Record<string, string> = {
  lmstudio: "LM Studio",
  ollama: "Ollama",
  vllm: "vLLM",
};

export function AgentPanel({ activeProject, agentProfiles, runtimeAgents, onProfilesChange }: Props) {
  const { t, locale } = useI18n();
  const loc = locale as Locale;
  const { status, showStatus } = useInlineStatus();

  const [models, setModels] = useState<Record<string, any>>({});
  const [roles, setRoles] = useState<string[]>([]);
  const [assignments, setAssignments] = useState<Record<string, string>>({});
  const [expandedRole, setExpandedRole] = useState<string | null>(null);
  const [showAddMenu, setShowAddMenu] = useState(false);

  // Drag state
  const [dragIdx, setDragIdx] = useState<number | null>(null);
  const [overIdx, setOverIdx] = useState<number | null>(null);
  const dragCounterRef = useRef(0);

  const runtimeMap = new Map(runtimeAgents.map((a: any) => [a.role, a]));

  const load = useCallback(async () => {
    try {
      const m = await api.listModels();
      setModels(m.models || {});
      const a = await api.getAssignments();
      const asgn = a.assignments || {};

      // Ensure default roles are always present
      let needsSave = false;
      const merged = { ...asgn };
      for (const role of DEFAULT_ROLES) {
        if (!(role in merged)) {
          const isHighTier = ["cto", "manager", "researcher", "reviewer"].includes(role);
          merged[role] = isHighTier ? "qwen3.5-9b" : "qwen2.5-coder-7b";
          needsSave = true;
        }
      }
      if (needsSave) {
        for (const role of DEFAULT_ROLES) {
          if (!(role in asgn)) {
            try { await api.switchModel(role, merged[role]); } catch { /* ignore */ }
          }
        }
      }
      setAssignments(merged);
      setRoles(Object.keys(merged));
    } catch {
      // API not available - show defaults
      const defaults: Record<string, string> = {};
      for (const role of DEFAULT_ROLES) {
        const isHighTier = ["cto", "manager", "researcher", "reviewer"].includes(role);
        defaults[role] = isHighTier ? "qwen3.5-9b" : "qwen2.5-coder-7b";
      }
      setAssignments(defaults);
      setRoles(Object.keys(defaults));
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const addableRoles = AGENT_ROLES.map(r => r.key).filter((r) => !roles.includes(r));

  // Drag & Drop handlers
  const handleDragStart = (e: React.DragEvent, idx: number) => {
    setDragIdx(idx);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", String(idx));
    requestAnimationFrame(() => (e.currentTarget as HTMLElement).classList.add("block-dragging"));
  };
  const handleDragEnd = (e: React.DragEvent) => {
    (e.currentTarget as HTMLElement).classList.remove("block-dragging");
    setDragIdx(null);
    setOverIdx(null);
    dragCounterRef.current = 0;
  };
  const handleDragEnter = (e: React.DragEvent, idx: number) => {
    e.preventDefault();
    dragCounterRef.current++;
    setOverIdx(idx);
  };
  const handleDragLeave = () => {
    dragCounterRef.current--;
    if (dragCounterRef.current <= 0) { setOverIdx(null); dragCounterRef.current = 0; }
  };
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  };
  const handleDrop = async (e: React.DragEvent, dropIdx: number) => {
    e.preventDefault();
    dragCounterRef.current = 0;
    setOverIdx(null);
    if (dragIdx === null || dragIdx === dropIdx) return;
    const newRoles = [...roles];
    const [moved] = newRoles.splice(dragIdx, 1);
    newRoles.splice(dropIdx, 0, moved);
    setRoles(newRoles);
    setDragIdx(null);
    try { await api.reorderRoles(newRoles); } catch { /* best effort */ }
  };

  const handleSwitch = async (role: string, newModel: string) => {
    try {
      await api.switchModel(role, newModel);
      setAssignments((prev) => ({ ...prev, [role]: newModel }));
      showStatus(`${role}: ${newModel} ${loc === "ja" ? "に変更" : "switched"}`, "success");
    } catch (e: any) {
      showStatus(`${loc === "ja" ? "モデル切替エラー" : "Switch error"}: ${e.message}`, "error");
    }
  };

  const updateProfile = (role: string, field: "title" | "personality", value: string) => {
    if (!onProfilesChange) return;
    const current = agentProfiles[role] || { title: "", personality: "" };
    onProfilesChange({
      ...agentProfiles,
      [role]: { ...current, [field]: value },
    });
  };

  const handleAddRole = async (role: string) => {
    const isHighTier = ["cto", "manager", "researcher", "reviewer"].includes(role);
    const defaultModel = isHighTier ? "qwen3.5-9b" : "qwen2.5-coder-7b";
    try {
      await api.switchModel(role, defaultModel);
      setAssignments((prev) => ({ ...prev, [role]: defaultModel }));
      setRoles((prev) => [...prev, role]);
      const meta = AGENT_ROLES.find(r => r.key === role);
      showStatus(`${meta?.label[loc] || role} ${loc === "ja" ? "を追加しました" : "added"}`, "success");
    } catch (e: any) {
      showStatus(`${loc === "ja" ? "追加エラー" : "Add error"}: ${e.message}`, "error");
    }
    setShowAddMenu(false);
  };

  const modelNames = Object.keys(models);

  return (
    <div className="agents-unified-panel">
      <div className="agents-unified-header">
        <h3 className="agents-unified-title">{t("agentPipeline")}</h3>
        <span className="agents-unified-hint">{t("dragToReorder")}</span>
        {status && <StatusIndicator status={status} />}
      </div>

      {roles.length === 0 ? (
        <div className="agents-unified-empty">
          <p>{t("noAgentConfig")}</p>
          <button className="agents-unified-reload-btn" onClick={load}>
            {t("refresh")}
          </button>
        </div>
      ) : (
        <div className="block-list">
          {roles.map((role, idx) => {
            const roleMeta = AGENT_ROLES.find((r) => r.key === role) || {
              key: role, icon: "\uD83E\uDD16", label: { en: role, ja: role },
              defaultTitle: { en: role, ja: role }, shortDesc: { en: "", ja: "" },
            };
            const model = assignments[role] || "\u2014";
            const modelConfig = models[model] || {};
            const provider = modelConfig.provider || "lmstudio";
            const isOver = overIdx === idx && dragIdx !== idx;
            const isDragged = dragIdx === idx;
            const isExpanded = expandedRole === role;
            const profile = agentProfiles[role] || { title: "", personality: "" };
            const displayTitle = profile.title || roleMeta.defaultTitle[loc];
            const runtime = runtimeMap.get(role);
            const isActive = !!runtime;

            return (
              <div
                key={role}
                className={`block-item ${isDragged ? "block-dragging" : ""} ${isOver ? "block-over" : ""} ${isExpanded ? "block-expanded" : ""}`}
                draggable={!isExpanded}
                onDragStart={(e) => handleDragStart(e, idx)}
                onDragEnd={handleDragEnd}
                onDragEnter={(e) => handleDragEnter(e, idx)}
                onDragLeave={handleDragLeave}
                onDragOver={handleDragOver}
                onDrop={(e) => handleDrop(e, idx)}
              >
                {/* Compact row */}
                <div className="block-row" onClick={() => setExpandedRole(isExpanded ? null : role)}>
                  <div className="block-grip">{"\u2261"}</div>
                  <div className="block-icon">{roleMeta.icon}</div>
                  <div className="block-body">
                    <div className="block-role-row">
                      <span className="block-role">{roleMeta.label[loc]}</span>
                      <span className="block-title-preview">{displayTitle}</span>
                      {isActive && (
                        <span className="block-status-badge block-status-active">
                          {t("running")}
                        </span>
                      )}
                    </div>
                    <div className="block-model-row">
                      <span className="block-model-name">{model}</span>
                      <span className="block-provider">{PROVIDER_BADGE[provider] || provider}</span>
                    </div>
                  </div>
                  <div className="block-order">{idx + 1}</div>
                  <div className="block-expand-label">
                    {isExpanded
                      ? (loc === "ja" ? "\u683C\u7D0D" : "Close")
                      : (loc === "ja" ? "\u5C55\u958B" : "Open")
                    }
                  </div>
                  <div className="block-chevron">{isExpanded ? "\u25B2" : "\u25BC"}</div>
                </div>

                {/* Expanded detail */}
                {isExpanded && (
                  <div className="block-detail-expanded">
                    <div className="block-detail-section">
                      <label className="block-detail-label">
                        {loc === "ja" ? "\u808C\u66F8\u304D" : "Title"}
                      </label>
                      <input
                        className="block-detail-input"
                        placeholder={roleMeta.defaultTitle[loc]}
                        value={profile.title}
                        onChange={(e) => updateProfile(role, "title", e.target.value)}
                      />
                    </div>

                    <div className="block-detail-section">
                      <label className="block-detail-label">
                        {loc === "ja" ? "\u6027\u683C\u30FB\u7279\u6280" : "Personality"}
                      </label>
                      <textarea
                        className="block-detail-textarea"
                        rows={3}
                        placeholder={roleMeta.shortDesc[loc]}
                        value={profile.personality}
                        onChange={(e) => updateProfile(role, "personality", e.target.value)}
                      />
                    </div>

                    <div className="block-detail-section">
                      <label className="block-detail-label">
                        {loc === "ja" ? "\u4F7F\u7528\u30E2\u30C7\u30EB" : "Model"}
                      </label>
                      <select
                        className="block-detail-select"
                        value={model}
                        onChange={(e) => handleSwitch(role, e.target.value)}
                      >
                        {modelNames.length > 0 ? (
                          modelNames.map((m) => (
                            <option key={m} value={m}>
                              {m} ({PROVIDER_BADGE[models[m]?.provider] || models[m]?.provider || "?"})
                            </option>
                          ))
                        ) : (
                          <option value={model}>{model}</option>
                        )}
                      </select>
                    </div>

                    {isActive && runtime && (
                      <div className="block-detail-section block-detail-runtime">
                        <label className="block-detail-label">
                          {loc === "ja" ? "\u5B9F\u884C\u72B6\u614B" : "Runtime"}
                        </label>
                        <div className="block-runtime-info">
                          <span className="block-runtime-stat">
                            {loc === "ja" ? "\u5B8C\u4E86" : "Done"}: {runtime.tasks_completed ?? 0}
                          </span>
                          <span className="block-runtime-stat">
                            {loc === "ja" ? "\u5931\u6557" : "Failed"}: {runtime.tasks_failed ?? 0}
                          </span>
                          {runtime.current_task && (
                            <span className="block-runtime-task">
                              {runtime.current_task}
                            </span>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
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
            + {loc === "ja" ? "\u30A8\u30FC\u30B8\u30A7\u30F3\u30C8\u8FFD\u52A0" : "Add Agent"}
          </button>
          {showAddMenu && (
            <div className="agents-tab-add-menu">
              {addableRoles.map((role) => {
                const meta = AGENT_ROLES.find(r => r.key === role) || {
                  key: role, icon: "\uD83E\uDD16", label: { en: role, ja: role },
                  defaultTitle: { en: role, ja: role }, shortDesc: { en: "", ja: "" },
                };
                return (
                  <button
                    key={role}
                    className="agents-tab-add-item"
                    onClick={() => handleAddRole(role)}
                  >
                    <span>{meta.icon}</span>
                    <span>{meta.label[loc]}</span>
                    <span className="agents-tab-add-desc">{meta.shortDesc[loc]}</span>
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
