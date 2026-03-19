"use client";

import { useState, useEffect, useCallback } from "react";
import * as api from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { AppTaskDef, AppTaskExecution } from "@/lib/types";

interface Props {
  projectId: string;
}

export function AppModeView({ projectId }: Props) {
  const { t } = useI18n();
  const [tasks, setTasks] = useState<AppTaskDef[]>([]);
  const [activeTasks, setActiveTasks] = useState<string[]>([]);
  const [history, setHistory] = useState<AppTaskExecution[]>([]);
  const [schedulerActive, setSchedulerActive] = useState(false);

  // New task form
  const [showForm, setShowForm] = useState(false);
  const [formTitle, setFormTitle] = useState("");
  const [formPrompt, setFormPrompt] = useState("");
  const [formSchedule, setFormSchedule] = useState<"manual" | "interval" | "cron">("manual");
  const [formInterval, setFormInterval] = useState(60);
  const [formCron, setFormCron] = useState("");
  const [formDeadline, setFormDeadline] = useState("");
  const [formEnabled, setFormEnabled] = useState(true);

  // Edit mode
  const [editingId, setEditingId] = useState<string | null>(null);

  // Status message
  const [statusMsg, setStatusMsg] = useState<{ text: string; type: "info" | "success" | "error" } | null>(null);

  const showStatus = (text: string, type: "info" | "success" | "error") => {
    setStatusMsg({ text, type });
    setTimeout(() => setStatusMsg(null), 3000);
  };

  const loadTasks = useCallback(async () => {
    try {
      const data = await api.listAppTasks(projectId);
      setTasks(data.tasks || []);
      setActiveTasks(data.active_task_ids || []);
    } catch {
      // project might not be app mode yet
    }
  }, [projectId]);

  const loadHistory = useCallback(async () => {
    try {
      const data = await api.getAppHistory(projectId, 30);
      setHistory(data.history || []);
    } catch { /* ignore */ }
  }, [projectId]);

  useEffect(() => {
    loadTasks();
    loadHistory();
    const interval = setInterval(() => {
      loadTasks();
      loadHistory();
    }, 5000);
    return () => clearInterval(interval);
  }, [loadTasks, loadHistory]);

  const resetForm = () => {
    setFormTitle("");
    setFormPrompt("");
    setFormSchedule("manual");
    setFormInterval(60);
    setFormCron("");
    setFormDeadline("");
    setFormEnabled(true);
    setEditingId(null);
    setShowForm(false);
  };

  const handleSave = async () => {
    if (!formTitle.trim() || !formPrompt.trim()) {
      showStatus("タスク名と指示は必須です", "error");
      return;
    }

    const taskData = {
      title: formTitle.trim(),
      prompt: formPrompt.trim(),
      schedule_type: formSchedule,
      interval_minutes: formSchedule === "interval" ? formInterval : 0,
      cron_expr: formSchedule === "cron" ? formCron : "",
      deadline: formDeadline || null,
      enabled: formEnabled,
    };

    try {
      if (editingId) {
        await api.updateAppTask(projectId, editingId, taskData);
        showStatus("タスクを更新しました", "success");
      } else {
        await api.createAppTask(projectId, taskData);
        showStatus("タスクを追加しました", "success");
      }
      resetForm();
      loadTasks();
    } catch (e: any) {
      showStatus(`エラー: ${e?.message || "不明なエラー"}`, "error");
    }
  };

  const handleEdit = (task: AppTaskDef) => {
    setEditingId(task.task_id);
    setFormTitle(task.title);
    setFormPrompt(task.prompt);
    setFormSchedule(task.schedule_type);
    setFormInterval(task.interval_minutes || 60);
    setFormCron(task.cron_expr || "");
    setFormDeadline(task.deadline || "");
    setFormEnabled(task.enabled);
    setShowForm(true);
  };

  const handleDelete = async (taskId: string) => {
    try {
      await api.deleteAppTask(projectId, taskId);
      showStatus("タスクを削除しました", "success");
      loadTasks();
    } catch (e: any) {
      showStatus(`削除エラー: ${e?.message || ""}`, "error");
    }
  };

  const handleRun = async (taskId: string) => {
    try {
      await api.runAppTask(projectId, taskId);
      showStatus("タスクを実行開始しました", "success");
      loadTasks();
    } catch (e: any) {
      showStatus(`実行エラー: ${e?.message || ""}`, "error");
    }
  };

  const handleToggleEnabled = async (task: AppTaskDef) => {
    try {
      await api.updateAppTask(projectId, task.task_id, { enabled: !task.enabled });
      loadTasks();
    } catch { /* ignore */ }
  };

  const handleSchedulerToggle = async () => {
    try {
      if (schedulerActive) {
        await api.stopAppScheduler(projectId);
        setSchedulerActive(false);
        showStatus("スケジューラを停止しました", "success");
      } else {
        await api.startAppScheduler(projectId);
        setSchedulerActive(true);
        showStatus("スケジューラを開始しました", "success");
      }
    } catch (e: any) {
      showStatus(`スケジューラエラー: ${e?.message || ""}`, "error");
    }
  };

  const formatTime = (iso: string | null) => {
    if (!iso) return "-";
    try {
      const d = new Date(iso);
      return d.toLocaleString("ja-JP", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
    } catch {
      return iso;
    }
  };

  const hasScheduledTasks = tasks.some((t) => t.schedule_type !== "manual");

  return (
    <div className="app-mode-view">
      {/* Status message */}
      {statusMsg && (
        <div className={`app-status app-status-${statusMsg.type}`}>
          {statusMsg.text}
        </div>
      )}

      {/* Header */}
      <div className="app-mode-header">
        <h3 className="app-mode-title">{t("appModeLabel")}</h3>
        {hasScheduledTasks && (
          <button
            className={`app-scheduler-btn ${schedulerActive ? "app-scheduler-active" : ""}`}
            onClick={handleSchedulerToggle}
          >
            {schedulerActive ? t("appSchedulerStop") : t("appSchedulerStart")}
          </button>
        )}
      </div>

      {schedulerActive && (
        <div className="app-scheduler-badge">{t("appSchedulerRunning")}</div>
      )}

      {/* Task list */}
      <div className="app-task-list">
        {tasks.length === 0 && !showForm && (
          <div className="app-empty">{t("appNoTasks")}</div>
        )}

        {tasks.map((task) => {
          const isRunning = activeTasks.includes(task.task_id);
          return (
            <div key={task.task_id} className={`app-task-card ${!task.enabled ? "app-task-disabled" : ""} ${isRunning ? "app-task-running" : ""}`}>
              <div className="app-task-header">
                <span className="app-task-title-text">{task.title}</span>
                <span className={`app-task-schedule-badge app-schedule-${task.schedule_type}`}>
                  {task.schedule_type === "manual" ? t("appScheduleManual") :
                   task.schedule_type === "interval" ? `${task.interval_minutes}${t("appIntervalMinutes").replace("Interval (min)", "min").replace("間隔（分）", "分")}` :
                   task.cron_expr || t("appScheduleCron")}
                </span>
              </div>

              <div className="app-task-prompt-preview">
                {task.prompt.length > 100 ? task.prompt.slice(0, 100) + "..." : task.prompt}
              </div>

              <div className="app-task-meta">
                {task.deadline && (
                  <span className="app-task-deadline">{t("appDeadline")}: {formatTime(task.deadline)}</span>
                )}
                {task.last_run && (
                  <span className="app-task-lastrun">{t("appLastRun")}: {formatTime(task.last_run)}</span>
                )}
                {task.next_run && (
                  <span className="app-task-nextrun">{t("appNextRun")}: {formatTime(task.next_run)}</span>
                )}
              </div>

              <div className="app-task-actions">
                <button
                  className="app-task-toggle"
                  onClick={() => handleToggleEnabled(task)}
                  title={task.enabled ? t("appTaskEnabled") : t("appTaskDisabled")}
                >
                  {task.enabled ? "\u2705" : "\u26AA"}
                </button>
                {isRunning ? (
                  <span className="app-task-running-indicator">{t("appTaskRunning")}</span>
                ) : (
                  <button
                    className="app-task-run-btn"
                    onClick={() => handleRun(task.task_id)}
                    disabled={!task.enabled}
                    title={t("appRunTask")}
                  >
                    {"\u25B6"}
                  </button>
                )}
                <button
                  className="app-task-edit-btn"
                  onClick={() => handleEdit(task)}
                  title="Edit"
                >
                  {"\u270E"}
                </button>
                <button
                  className="app-task-delete-btn"
                  onClick={() => handleDelete(task.task_id)}
                  title={t("appDeleteTask")}
                >
                  {"\u2716"}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Add/Edit task form */}
      {showForm ? (
        <div className="app-task-form">
          <div className="app-form-group">
            <label>{t("appTaskTitle")}</label>
            <input
              value={formTitle}
              onChange={(e) => setFormTitle(e.target.value)}
              placeholder={t("appNewTaskPlaceholder")}
              className="app-form-input"
            />
          </div>

          <div className="app-form-group">
            <label>{t("appTaskPrompt")}</label>
            <textarea
              value={formPrompt}
              onChange={(e) => setFormPrompt(e.target.value)}
              placeholder={t("appTaskPromptPlaceholder")}
              className="app-form-textarea"
              rows={4}
            />
          </div>

          <div className="app-form-group">
            <label>{t("modeSelect")}</label>
            <div className="app-schedule-options">
              <button
                className={`app-schedule-opt ${formSchedule === "manual" ? "active" : ""}`}
                onClick={() => setFormSchedule("manual")}
              >
                {t("appScheduleManual")}
              </button>
              <button
                className={`app-schedule-opt ${formSchedule === "interval" ? "active" : ""}`}
                onClick={() => setFormSchedule("interval")}
              >
                {t("appScheduleInterval")}
              </button>
              <button
                className={`app-schedule-opt ${formSchedule === "cron" ? "active" : ""}`}
                onClick={() => setFormSchedule("cron")}
              >
                {t("appScheduleCron")}
              </button>
            </div>
          </div>

          {formSchedule === "interval" && (
            <div className="app-form-group">
              <label>{t("appIntervalMinutes")}</label>
              <input
                type="number"
                value={formInterval}
                onChange={(e) => setFormInterval(Number(e.target.value))}
                min={1}
                className="app-form-input app-form-number"
              />
            </div>
          )}

          {formSchedule === "cron" && (
            <div className="app-form-group">
              <label>{t("appCronExpr")}</label>
              <input
                value={formCron}
                onChange={(e) => setFormCron(e.target.value)}
                placeholder="0 */6 * * *"
                className="app-form-input"
              />
            </div>
          )}

          <div className="app-form-group">
            <label>{t("appDeadline")}</label>
            <input
              type="datetime-local"
              value={formDeadline}
              onChange={(e) => setFormDeadline(e.target.value)}
              className="app-form-input"
            />
            <span className="app-form-hint">{t("appNoDeadline")}</span>
          </div>

          <div className="app-form-actions">
            <button className="app-form-save" onClick={handleSave}>
              {editingId ? t("appSaveTask") : t("appAddTask")}
            </button>
            <button className="app-form-cancel" onClick={resetForm}>
              {t("cancel")}
            </button>
          </div>
        </div>
      ) : (
        <button className="app-add-task-btn" onClick={() => setShowForm(true)}>
          + {t("appAddTask")}
        </button>
      )}

      {/* Execution history */}
      <div className="app-history">
        <h4 className="app-history-title">{t("appHistory")}</h4>
        {history.length === 0 ? (
          <div className="app-empty">{t("appNoHistory")}</div>
        ) : (
          <div className="app-history-list">
            {history.slice().reverse().map((exec) => {
              const taskDef = tasks.find((t) => t.task_id === exec.task_id);
              return (
                <div key={exec.execution_id} className={`app-history-item app-history-${exec.status}`}>
                  <span className="app-history-title">{taskDef?.title || exec.task_id}</span>
                  <span className={`app-history-status app-status-${exec.status}`}>
                    {exec.status === "running" ? t("appTaskRunning") :
                     exec.status === "completed" ? t("appTaskCompleted") :
                     t("appTaskError")}
                  </span>
                  <span className="app-history-time">{formatTime(exec.started_at)}</span>
                  {exec.error && <span className="app-history-error">{exec.error}</span>}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
