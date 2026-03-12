"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import * as api from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useInlineStatus, StatusIndicator } from "@/components/Toast";

const ROLE_META: Record<string, { icon: string; label: string; tier: string }> = {
  cto:        { icon: "\u{1F3D7}", label: "CTO",        tier: "high" },
  manager:    { icon: "\u{1F4CB}", label: "Manager",    tier: "high" },
  researcher: { icon: "\u{1F50D}", label: "Researcher", tier: "high" },
  reviewer:   { icon: "\u{1F50E}", label: "Reviewer",   tier: "high" },
  engineer:   { icon: "\u{1F528}", label: "Engineer",   tier: "standard" },
  tester:     { icon: "\u{1F9EA}", label: "Tester",     tier: "standard" },
  optimizer:  { icon: "\u26A1",    label: "Optimizer",  tier: "standard" },
  documenter: { icon: "\u{1F4DD}", label: "Documenter", tier: "standard" },
  marketer:   { icon: "\u{1F4E2}", label: "Marketer",   tier: "standard" },
};

const PROVIDER_BADGE: Record<string, string> = {
  lmstudio: "LM Studio",
  ollama:   "Ollama",
  vllm:     "vLLM",
};

export function ModelPanel() {
  const { t } = useI18n();
  const [models, setModels] = useState<Record<string, any>>({});
  const [roles, setRoles] = useState<string[]>([]);
  const [assignments, setAssignments] = useState<Record<string, string>>({});
  const [editingRole, setEditingRole] = useState<string | null>(null);
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
    } catch { /* API not available */ }
  }, []);

  useEffect(() => { load(); }, [load]);

  // ── Drag & Drop handlers ──
  const handleDragStart = (e: React.DragEvent, idx: number) => {
    setDragIdx(idx);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", String(idx));
    // Style the dragged element
    const el = e.currentTarget as HTMLElement;
    requestAnimationFrame(() => el.classList.add("block-dragging"));
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
    if (dragCounterRef.current <= 0) {
      setOverIdx(null);
      dragCounterRef.current = 0;
    }
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

    try {
      await api.reorderRoles(newRoles);
    } catch { /* best effort */ }
  };

  // ── Model switch ──
  const handleSwitch = async (role: string, newModel: string) => {
    try {
      await api.switchModel(role, newModel);
      setAssignments((prev) => ({ ...prev, [role]: newModel }));
      setEditingRole(null);
    } catch (e: any) {
      showStatus(`モデル切替エラー: ${e.message}`, "error");
    }
  };

  const modelNames = Object.keys(models);

  return (
    <div className="model-panel">
      <div className="model-panel-header">
        <h2>{t("agentPipeline")}</h2>
        <span className="model-panel-hint">{t("dragToReorder")}</span>
      </div>

      {status && (
        <StatusIndicator status={status} />
      )}

      {roles.length === 0 && (
        <div className="model-panel-empty">{t("noAgentConfig")}</div>
      )}

      <div className="block-list">
        {roles.map((role, idx) => {
          const meta = ROLE_META[role] || { icon: "\u{1F916}", label: role, tier: "standard" };
          const model = assignments[role] || "—";
          const modelConfig = models[model] || {};
          const provider = modelConfig.provider || "lmstudio";
          const isOver = overIdx === idx && dragIdx !== idx;
          const isDragged = dragIdx === idx;

          return (
            <div
              key={role}
              className={`block-item ${isDragged ? "block-dragging" : ""} ${isOver ? "block-over" : ""}`}
              draggable
              onDragStart={(e) => handleDragStart(e, idx)}
              onDragEnd={handleDragEnd}
              onDragEnter={(e) => handleDragEnter(e, idx)}
              onDragLeave={handleDragLeave}
              onDragOver={handleDragOver}
              onDrop={(e) => handleDrop(e, idx)}
            >
              <div className="block-grip">{"\u2261"}</div>
              <div className="block-icon">{meta.icon}</div>
              <div className="block-body">
                <div className="block-role-row">
                  <span className="block-role">{meta.label}</span>
                  <span className={`block-tier block-tier-${meta.tier}`}>{meta.tier}</span>
                </div>
                {editingRole === role ? (
                  <select
                    className="block-select"
                    value={model}
                    autoFocus
                    onChange={(e) => handleSwitch(role, e.target.value)}
                    onBlur={() => setEditingRole(null)}
                  >
                    {modelNames.map((m) => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                ) : (
                  <button className="block-model" onClick={() => setEditingRole(role)}>
                    <span className="block-model-name">{model}</span>
                    <span className="block-provider">{PROVIDER_BADGE[provider] || provider}</span>
                  </button>
                )}
              </div>
              <div className="block-order">{idx + 1}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
