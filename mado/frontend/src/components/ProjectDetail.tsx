"use client";

import { useState, useEffect, useCallback } from "react";
import * as api from "@/lib/api";
import { useI18n, type Locale } from "@/lib/i18n";
import { useInlineStatus, StatusIndicator } from "@/components/Toast";
import type { TaskItem, ProjectNode, AgentProfileAssignment } from "@/lib/types";

interface Props {
  activeProject: string | null;
  projectTree: ProjectNode[];
  onRefresh: () => void;
  allRunStatuses?: Record<string, string>;
  onDispatchChild?: (parentId: string, childId: string, instruction?: string) => Promise<void>;
  onStopChild?: (childId: string) => Promise<void>;
  onDispatchAll?: (parentId: string) => Promise<void>;
}

export function ProjectDetail({ activeProject, projectTree, onRefresh, allRunStatuses, onDispatchChild, onStopChild, onDispatchAll }: Props) {
  const { t, locale } = useI18n();
  const { status, showStatus } = useInlineStatus();
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  // Expandable sections
  const [goalEditing, setGoalEditing] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);

  // Close overlay on ESC key
  useEffect(() => {
    if (!detailsOpen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setDetailsOpen(false);
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [detailsOpen]);

  // Editable fields
  const [goal, setGoal] = useState("");
  const [overview, setOverview] = useState("");
  const [policy, setPolicy] = useState("");
  const [roadmap, setRoadmap] = useState("");
  const [description, setDescription] = useState("");
  const [deadline, setDeadline] = useState("");
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [rulesMust, setRulesMust] = useState("");
  const [rulesForbidden, setRulesForbidden] = useState("");
  const [agentProfiles, setAgentProfiles] = useState<Record<string, AgentProfileAssignment>>({});
  const [childInstructions, setChildInstructions] = useState<Record<string, string>>({});
  const [dispatchingChild, setDispatchingChild] = useState<string | null>(null);
  const [additionalOrder, setAdditionalOrder] = useState("");

  const node = projectTree.find((n) => n.project_id === activeProject);
  const isParent = node ? node.children.length > 0 || !node.parent_id : false;

  // Load data when project changes
  useEffect(() => {
    if (!node) return;
    setGoal(node.goal || "");
    setOverview(node.overview || "");
    setPolicy(node.policy || "");
    setRoadmap(node.roadmap || "");
    setDescription(node.description || "");
    setDeadline(node.deadline || "");
    setTasks(node.tasks || []);
    setRulesMust(node.rules_must || "");
    setRulesForbidden(node.rules_forbidden || "");
    setAgentProfiles(node.agent_profiles || {});
    setDirty(false);
    setGoalEditing(false);
    setDetailsOpen(false);
  }, [activeProject, node?.project_id]);

  const markDirty = useCallback(() => {
    setDirty(true);
  }, []);

  const handleSave = async () => {
    if (!activeProject) return;
    setSaving(true);
    try {
      const updates: Record<string, any> = {
        goal,
        rules_must: rulesMust,
        rules_forbidden: rulesForbidden,
        agent_profiles: agentProfiles,
      };
      if (isParent || !node?.parent_id) {
        updates.overview = overview;
        updates.policy = policy;
        updates.roadmap = roadmap;
      }
      if (node?.parent_id) {
        updates.description = description;
        updates.deadline = deadline || null;
        updates.tasks = tasks;
      }
      await api.updateProjectConfig(activeProject, updates);
      setDirty(false);
      setGoalEditing(false);  // collapse goal on save
      onRefresh();
      showStatus("保存完了", "success");
    } catch (e: any) {
      showStatus(`保存エラー: ${e.message}`, "error");
    } finally {
      setSaving(false);
    }
  };

  const handleSendOrder = async () => {
    if (!activeProject || !additionalOrder.trim()) return;
    try {
      // Send additional order as a new run with the combined goal
      const combinedGoal = goal
        ? `${goal}\n\n追加オーダー: ${additionalOrder.trim()}`
        : additionalOrder.trim();
      await api.startRun(activeProject, combinedGoal);
      showStatus("追加オーダーを送信", "success");
      setAdditionalOrder("");
    } catch (e: any) {
      showStatus(`送信エラー: ${e.message}`, "error");
    }
  };

  const addTask = () => {
    const newTask: TaskItem = {
      id: `task-${Date.now()}`,
      title: "",
      description: "",
      status: "pending",
      deadline: "",
      priority: "medium",
    };
    setTasks([...tasks, newTask]);
    markDirty();
  };

  const updateTask = (idx: number, field: string, value: string) => {
    const updated = [...tasks];
    (updated[idx] as any)[field] = value;
    setTasks(updated);
    markDirty();
  };

  const removeTask = (idx: number) => {
    setTasks(tasks.filter((_, i) => i !== idx));
    markDirty();
  };

  if (!activeProject || !node) {
    return (
      <div className="project-detail-empty">
        <p>{t("noProjectSelected")}</p>
      </div>
    );
  }

  // Task status summary
  const taskCounts = tasks.reduce(
    (acc, t) => {
      acc[t.status] = (acc[t.status] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>,
  );

  return (
    <>
    {/* ── Compact bar (always visible) ── */}
    <div className="detail-compact-bar">
      <h3 className="detail-title">{node?.display_name || activeProject}</h3>
      <span className="detail-goal-preview" title={goal || ""}>
        {goal ? goal.slice(0, 60) + (goal.length > 60 ? "..." : "") : ""}
      </span>
      <div className="detail-compact-actions">
        <StatusIndicator status={status} />
        <button
          className="btn btn-sm detail-manage-btn"
          onClick={() => setDetailsOpen(!detailsOpen)}
        >
          {locale === "ja" ? "目標管理" : "Settings"}
        </button>
      </div>
    </div>

    {/* ── Full overlay (shown when detailsOpen) ── */}
    {detailsOpen && (
      <div className="detail-overlay">
        <div className="detail-overlay-header">
          <h3 className="detail-title">{node?.display_name || activeProject}</h3>
          <div className="detail-overlay-actions">
            <StatusIndicator status={status} />
            {dirty && (
              <button className="btn btn-primary btn-sm" onClick={handleSave} disabled={saving}>
                {saving ? t("saving") : t("save")}
              </button>
            )}
            <button className="btn btn-sm btn-ghost" onClick={() => setDetailsOpen(false)}>
              {locale === "ja" ? "閉じる" : "Close"}
            </button>
          </div>
        </div>

        <div className="detail-overlay-body">
          {/* Goal */}
          <div className="detail-field">
            <label className="detail-label">{t("goalPlaceholder").replace("...", "")}</label>
            <textarea
              className="detail-textarea detail-goal-textarea"
              rows={4}
              placeholder={t("goalPlaceholder")}
              value={goal}
              onChange={(e) => { setGoal(e.target.value); markDirty(); }}
            />
          </div>

          {/* Task Status Summary */}
          {tasks.length > 0 && (
            <div className="detail-task-summary">
              <span className="detail-task-summary-label">{t("taskStatusSummary")}</span>
              <div className="detail-task-badges">
                {(taskCounts["done"] || 0) > 0 && <span className="task-badge task-badge-done">{t("done")} {taskCounts["done"]}</span>}
                {(taskCounts["in_progress"] || 0) > 0 && <span className="task-badge task-badge-progress">{t("inProgress")} {taskCounts["in_progress"]}</span>}
                {(taskCounts["pending"] || 0) > 0 && <span className="task-badge task-badge-pending">{t("pending")} {taskCounts["pending"]}</span>}
                <span className="task-badge-total">{tasks.length}{locale === "ja" ? "件" : " total"}</span>
              </div>
            </div>
          )}

          {/* Additional Order Input */}
          <div className="detail-order-section">
            <div className="detail-order-row">
              <input
                className="detail-order-input"
                placeholder={t("additionalOrderPlaceholder")}
                value={additionalOrder}
                onChange={(e) => setAdditionalOrder(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSendOrder(); }
                }}
              />
              <button className="btn btn-primary btn-sm" onClick={handleSendOrder} disabled={!additionalOrder.trim()}>
                {t("sendOrder")}
              </button>
            </div>
          </div>

          {/* Child Project Management */}
          {node.children.length > 0 && (
            <div className="detail-field child-management">
              <div className="child-management-header">
                <label className="detail-label">{t("childProjectManagement")}</label>
                {onDispatchAll && (
                  <div className="child-management-actions">
                    <button className="btn btn-sm btn-primary" onClick={async () => {
                      if (!activeProject) return;
                      try { await onDispatchAll(activeProject); showStatus("全子プロジェクトを開始", "success"); }
                      catch (e: any) { showStatus(`一括開始エラー: ${e.message}`, "error"); }
                    }}>{t("dispatchAll")}</button>
                  </div>
                )}
              </div>
              <div className="child-management-hint">
                <span className="hint-badge hint-inherit">{t("inheritingProfiles")}</span>
                <span className="hint-badge hint-memory">{t("inheritingMemory")}</span>
              </div>
              <div className="child-cards">
                {node.children.map((childId) => {
                  const childNode = projectTree.find((n) => n.project_id === childId);
                  const childStatus = allRunStatuses?.[childId] || "idle";
                  const isRunning = childStatus === "running";
                  const instruction = childInstructions[childId] || "";
                  const isDispatching = dispatchingChild === childId;
                  return (
                    <div key={childId} className={`child-card ${isRunning ? "child-running" : ""}`}>
                      <div className="child-card-top">
                        <div className="child-card-info">
                          <span className="child-card-name">{childNode?.display_name || childId}</span>
                          <span className={`child-status-badge child-status-${childStatus}`}>
                            {childStatus === "running" ? t("running") : childStatus === "completed" ? t("completed") : childStatus === "error" ? t("error") : childStatus === "paused" ? t("paused") : childStatus === "stopped" ? t("stopped") : t("initialized")}
                          </span>
                        </div>
                        <div className="child-card-goal">{childNode?.goal ? childNode.goal.slice(0, 80) : "\u2014"}</div>
                      </div>
                      <div className="child-card-bottom">
                        <input className="child-instruction-input" placeholder={t("childInstruction")} value={instruction}
                          onChange={(e) => setChildInstructions({ ...childInstructions, [childId]: e.target.value })} disabled={isRunning || isDispatching} />
                        <div className="child-card-buttons">
                          {!isRunning ? (
                            <button className="btn btn-sm btn-primary" disabled={isDispatching} onClick={async () => {
                              if (!activeProject || !onDispatchChild) return;
                              setDispatchingChild(childId);
                              try { await onDispatchChild(activeProject, childId, instruction || undefined); showStatus(`「${childNode?.display_name || childId}」を開始`, "success"); setChildInstructions({ ...childInstructions, [childId]: "" }); }
                              catch (e: any) { showStatus(`開始エラー: ${e.message}`, "error"); }
                              finally { setDispatchingChild(null); }
                            }}>{isDispatching ? "..." : t("dispatchChild")}</button>
                          ) : (
                            <button className="btn btn-sm btn-danger" onClick={async () => {
                              if (!onStopChild) return;
                              try { await onStopChild(childId); showStatus(`「${childNode?.display_name || childId}」を停止`, "success"); }
                              catch (e: any) { showStatus(`停止エラー: ${e.message}`, "error"); }
                            }}>{t("stopChild")}</button>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Project Rules */}
          <div className="detail-rules-group">
            <div className="detail-field detail-rules-must">
              <label className="detail-label">{t("rulesMust")}</label>
              <textarea className="detail-textarea" rows={3} placeholder={t("rulesMustPlaceholder")} value={rulesMust}
                onChange={(e) => { setRulesMust(e.target.value); markDirty(); }} />
            </div>
            <div className="detail-field detail-rules-forbidden">
              <label className="detail-label">{t("rulesForbidden")}</label>
              <textarea className="detail-textarea" rows={3} placeholder={t("rulesForbiddenPlaceholder")} value={rulesForbidden}
                onChange={(e) => { setRulesForbidden(e.target.value); markDirty(); }} />
            </div>
          </div>

          {/* Parent project fields */}
          {(isParent || !node.parent_id) && (
            <>
              <div className="detail-field">
                <label className="detail-label">{t("overview")}</label>
                <textarea className="detail-textarea" rows={3} placeholder={t("overviewPlaceholder")} value={overview}
                  onChange={(e) => { setOverview(e.target.value); markDirty(); }} />
              </div>
              <div className="detail-field">
                <label className="detail-label">{t("policyLabel")}</label>
                <textarea className="detail-textarea" rows={3} placeholder={t("policyPlaceholder")} value={policy}
                  onChange={(e) => { setPolicy(e.target.value); markDirty(); }} />
              </div>
              <div className="detail-field">
                <label className="detail-label">{t("roadmap")}</label>
                <textarea className="detail-textarea" rows={4} placeholder={t("roadmapPlaceholder")} value={roadmap}
                  onChange={(e) => { setRoadmap(e.target.value); markDirty(); }} />
              </div>
            </>
          )}

          {/* Child project fields */}
          {node.parent_id && (
            <>
              <div className="detail-field">
                <label className="detail-label">{t("descriptionLabel")}</label>
                <textarea className="detail-textarea" rows={3} placeholder={t("descriptionPlaceholder")} value={description}
                  onChange={(e) => { setDescription(e.target.value); markDirty(); }} />
              </div>
              <div className="detail-field">
                <label className="detail-label">{t("deadline")}</label>
                <input type="date" className="detail-input" value={deadline}
                  onChange={(e) => { setDeadline(e.target.value); markDirty(); }} />
              </div>
              <div className="detail-field">
                <div className="detail-task-header">
                  <label className="detail-label">{t("taskList")}</label>
                  <button className="tree-action-btn" onClick={addTask}>+ {t("addTask")}</button>
                </div>
                <div className="detail-task-list">
                  {tasks.map((task, idx) => (
                    <div key={task.id} className="detail-task-item">
                      <div className="detail-task-row">
                        <select className="detail-task-status" value={task.status} onChange={(e) => updateTask(idx, "status", e.target.value)}>
                          <option value="pending">{t("pending")}</option>
                          <option value="in_progress">{t("inProgress")}</option>
                          <option value="done">{t("done")}</option>
                        </select>
                        <select className="detail-task-priority" value={task.priority} onChange={(e) => updateTask(idx, "priority", e.target.value)}>
                          <option value="high">{t("priorityHigh")}</option>
                          <option value="medium">{t("priorityMedium")}</option>
                          <option value="low">{t("priorityLow")}</option>
                        </select>
                        <input className="detail-task-title" placeholder={t("taskTitle")} value={task.title} onChange={(e) => updateTask(idx, "title", e.target.value)} />
                        <input type="date" className="detail-task-deadline" value={task.deadline} onChange={(e) => updateTask(idx, "deadline", e.target.value)} />
                        <button className="detail-task-remove" onClick={() => removeTask(idx)}>{"\u2716"}</button>
                      </div>
                      <textarea className="detail-task-desc" rows={1} placeholder={t("descriptionPlaceholder")} value={task.description} onChange={(e) => updateTask(idx, "description", e.target.value)} />
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {dirty && (
            <div className="detail-settings-save">
              <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
                {saving ? t("saving") : t("save")}
              </button>
            </div>
          )}
        </div>
      </div>
    )}
    </>
  );
}
