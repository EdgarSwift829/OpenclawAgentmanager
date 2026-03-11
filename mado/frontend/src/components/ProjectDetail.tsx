"use client";

import { useState, useEffect, useCallback } from "react";
import * as api from "@/lib/api";
import { useI18n } from "@/lib/i18n";

interface TaskItem {
  id: string;
  title: string;
  description: string;
  status: string;
  deadline: string;
  priority: string;
}

interface ProjectNode {
  project_id: string;
  display_name?: string;
  parent_id: string | null;
  children: string[];
  status: string;
  goal: string;
  overview: string;
  policy: string;
  roadmap: string;
  description: string;
  deadline: string | null;
  tasks: TaskItem[];
}

interface Props {
  activeProject: string | null;
  projectTree: ProjectNode[];
  onRefresh: () => void;
}

export function ProjectDetail({ activeProject, projectTree, onRefresh }: Props) {
  const { t } = useI18n();
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [dirty, setDirty] = useState(false);

  // Editable fields
  const [goal, setGoal] = useState("");
  const [overview, setOverview] = useState("");
  const [policy, setPolicy] = useState("");
  const [roadmap, setRoadmap] = useState("");
  const [description, setDescription] = useState("");
  const [deadline, setDeadline] = useState("");
  const [tasks, setTasks] = useState<TaskItem[]>([]);

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
    setDirty(false);
    setSaved(false);
  }, [activeProject, node?.project_id]);

  const markDirty = useCallback(() => {
    setDirty(true);
    setSaved(false);
  }, []);

  const handleSave = async () => {
    if (!activeProject) return;
    setSaving(true);
    try {
      const updates: Record<string, any> = { goal };
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
      setSaved(true);
      setDirty(false);
      onRefresh();
    } catch (e: any) {
      alert(e.message);
    } finally {
      setSaving(false);
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

  return (
    <div className="project-detail">
      <div className="detail-header">
        <h3 className="detail-title">{node?.display_name || activeProject}</h3>
        <div className="detail-save-area">
          {saved && <span className="detail-saved">{t("saved")}</span>}
          <button
            className="btn btn-primary detail-save-btn"
            onClick={handleSave}
            disabled={saving || !dirty}
          >
            {saving ? t("saving") : t("save")}
          </button>
        </div>
      </div>

      {/* Goal - common to all */}
      <div className="detail-field">
        <label className="detail-label">{t("goalPlaceholder").replace("...", "")}</label>
        <textarea
          className="detail-textarea"
          rows={2}
          placeholder={t("goalPlaceholder")}
          value={goal}
          onChange={(e) => { setGoal(e.target.value); markDirty(); }}
        />
      </div>

      {/* Parent project: overview, policy, roadmap */}
      {(isParent || !node.parent_id) && (
        <>
          <div className="detail-field">
            <label className="detail-label">{t("overview")}</label>
            <textarea
              className="detail-textarea"
              rows={3}
              placeholder={t("overviewPlaceholder")}
              value={overview}
              onChange={(e) => { setOverview(e.target.value); markDirty(); }}
            />
          </div>
          <div className="detail-field">
            <label className="detail-label">{t("policyLabel")}</label>
            <textarea
              className="detail-textarea"
              rows={3}
              placeholder={t("policyPlaceholder")}
              value={policy}
              onChange={(e) => { setPolicy(e.target.value); markDirty(); }}
            />
          </div>
          <div className="detail-field">
            <label className="detail-label">{t("roadmap")}</label>
            <textarea
              className="detail-textarea"
              rows={4}
              placeholder={t("roadmapPlaceholder")}
              value={roadmap}
              onChange={(e) => { setRoadmap(e.target.value); markDirty(); }}
            />
          </div>
        </>
      )}

      {/* Child project: description, deadline, tasks */}
      {node.parent_id && (
        <>
          <div className="detail-field">
            <label className="detail-label">{t("descriptionLabel")}</label>
            <textarea
              className="detail-textarea"
              rows={3}
              placeholder={t("descriptionPlaceholder")}
              value={description}
              onChange={(e) => { setDescription(e.target.value); markDirty(); }}
            />
          </div>
          <div className="detail-field">
            <label className="detail-label">{t("deadline")}</label>
            <input
              type="date"
              className="detail-input"
              value={deadline}
              onChange={(e) => { setDeadline(e.target.value); markDirty(); }}
            />
          </div>

          {/* Task list */}
          <div className="detail-field">
            <div className="detail-task-header">
              <label className="detail-label">{t("taskList")}</label>
              <button className="tree-action-btn" onClick={addTask}>+ {t("addTask")}</button>
            </div>
            <div className="detail-task-list">
              {tasks.map((task, idx) => (
                <div key={task.id} className="detail-task-item">
                  <div className="detail-task-row">
                    <select
                      className="detail-task-status"
                      value={task.status}
                      onChange={(e) => updateTask(idx, "status", e.target.value)}
                    >
                      <option value="pending">{t("pending")}</option>
                      <option value="in_progress">{t("inProgress")}</option>
                      <option value="done">{t("done")}</option>
                    </select>
                    <select
                      className="detail-task-priority"
                      value={task.priority}
                      onChange={(e) => updateTask(idx, "priority", e.target.value)}
                    >
                      <option value="high">{t("priorityHigh")}</option>
                      <option value="medium">{t("priorityMedium")}</option>
                      <option value="low">{t("priorityLow")}</option>
                    </select>
                    <input
                      className="detail-task-title"
                      placeholder={t("taskTitle")}
                      value={task.title}
                      onChange={(e) => updateTask(idx, "title", e.target.value)}
                    />
                    <input
                      type="date"
                      className="detail-task-deadline"
                      value={task.deadline}
                      onChange={(e) => updateTask(idx, "deadline", e.target.value)}
                    />
                    <button className="detail-task-remove" onClick={() => removeTask(idx)}>
                      {"\u2716"}
                    </button>
                  </div>
                  <textarea
                    className="detail-task-desc"
                    rows={1}
                    placeholder={t("descriptionPlaceholder")}
                    value={task.description}
                    onChange={(e) => updateTask(idx, "description", e.target.value)}
                  />
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
