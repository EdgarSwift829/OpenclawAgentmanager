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
  activeProject?: string | null;
  agentProfiles?: Record<string, AgentProfile>;
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

const PROVIDER_BADGE: Record<string, string> = {
  lmstudio: "LM Studio",
  ollama: "Ollama",
  vllm: "vLLM",
};

export function ModelPanel({ activeProject, agentProfiles = {}, onProfilesChange }: Props) {
  const { t, locale } = useI18n();
  const loc = locale as Locale;
  const [models, setModels] = useState<Record<string, any>>({});
  const [roles, setRoles] = useState<string[]>([]);
  const [assignments, setAssignments] = useState<Record<string, string>>({});
  const [expandedRole, setExpandedRole] = useState<string | null>(null);
  const { status, showStatus } = useInlineStatus();

  // Drag state
  const [dragIdx, setDragIdx] = useState<number | null>(null);
  const [overIdx, setOverIdx] = useState<number | null>(null);
  const dragCounterRef = useRef(0);

  const load = useCallback(async () => {
    try {
      const m = await api.listModels();
      setModels(m.models || {});
      const a = await api.getAssignments();
      const asgn = a.assignments || {};
      setAssignments(asgn);
      setRoles(Object.keys(asgn));
    } catch (e: any) {
      console.error("AgentPanel load error:", e);
      showStatus(`読み込みエラー: ${e?.message || "API未接続"}`, "error");
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Drag & Drop
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

  // Model switch
  const handleSwitch = async (role: string, newModel: string) => {
    try {
      await api.switchModel(role, newModel);
      setAssignments((prev) => ({ ...prev, [role]: newModel }));
      showStatus(`${role}: ${newModel} に変更`, "success");
    } catch (e: any) {
      showStatus(`モデル切替エラー: ${e.message}`, "error");
    }
  };

  // Profile edit
  const updateProfile = (role: string, field: "title" | "personality", value: string) => {
    if (!onProfilesChange) return;
    const current = agentProfiles[role] || { title: "", personality: "" };
    onProfilesChange({
      ...agentProfiles,
      [role]: { ...current, [field]: value },
    });
  };

  const modelNames = Object.keys(models);

  return (
    <div className="model-panel">
      <div className="model-panel-header">
        <h2>{t("agentPipeline")}</h2>
        <span className="model-panel-hint">{t("dragToReorder")}</span>
      </div>

      {status && <StatusIndicator status={status} />}

      {roles.length === 0 && (
        <div className="model-panel-empty">
          <p>{t("noAgentConfig")}</p>
          <button
            className="tree-action-btn"
            onClick={load}
            style={{ marginTop: "0.5rem", padding: "0.25rem 0.75rem", border: "1px solid var(--border)", borderRadius: "4px" }}
          >
            {t("refresh")}
          </button>
        </div>
      )}

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
                  </div>
                  <div className="block-model-row">
                    <span className="block-model-name">{model}</span>
                    <span className="block-provider">{PROVIDER_BADGE[provider] || provider}</span>
                  </div>
                </div>
                <div className="block-order">{idx + 1}</div>
                <div className="block-chevron">{isExpanded ? "\u25B2" : "\u25BC"}</div>
              </div>

              {/* Expanded detail */}
              {isExpanded && (
                <div className="block-detail">
                  <label className="block-detail-label">{loc === "ja" ? "肩書き" : "Title"}</label>
                  <input
                    className="block-detail-input"
                    placeholder={roleMeta.defaultTitle[loc]}
                    value={profile.title}
                    onChange={(e) => updateProfile(role, "title", e.target.value)}
                  />
                  <label className="block-detail-label">{loc === "ja" ? "性格・特技" : "Personality"}</label>
                  <textarea
                    className="block-detail-textarea"
                    rows={2}
                    placeholder={roleMeta.shortDesc[loc]}
                    value={profile.personality}
                    onChange={(e) => updateProfile(role, "personality", e.target.value)}
                  />
                  <label className="block-detail-label">{loc === "ja" ? "使用モデル" : "Model"}</label>
                  <select
                    className="block-detail-select"
                    value={model}
                    onChange={(e) => handleSwitch(role, e.target.value)}
                  >
                    {modelNames.map((m) => (
                      <option key={m} value={m}>{m} ({PROVIDER_BADGE[models[m]?.provider] || models[m]?.provider || "?"})</option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
