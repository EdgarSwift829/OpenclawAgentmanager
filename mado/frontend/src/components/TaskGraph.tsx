"use client";

import { useMemo } from "react";
import { useI18n, type Locale } from "@/lib/i18n";
import { ROLE_META, TASK_STATE_META } from "@/lib/constants";

interface Props {
  runStatus: any;
  events?: any[];
}

/* ─── Derive task info from events ─────────────────────── */
interface TaskInfo {
  task_id: string;
  description: string;
  assigned_to: string;
  from_role: string;
  state: string;
  review_approved?: boolean;
  review_feedback?: string;
}

function deriveTasksFromEvents(events: any[]): TaskInfo[] {
  const tasks: Map<string, TaskInfo> = new Map();
  const decomposedTasks: TaskInfo[] = [];

  for (const ev of events) {
    const type = ev.type || "";

    if (type === "tasks_decomposed" && ev.tasks) {
      for (const t of ev.tasks) {
        const id = t.id || `task_${decomposedTasks.length}`;
        const info: TaskInfo = {
          task_id: id,
          description: t.desc || "",
          assigned_to: t.role || "engineer",
          from_role: "manager",
          state: "queued",
        };
        tasks.set(id, info);
        decomposedTasks.push(info);
      }
    }
    if (type === "task_started" && ev.task_id) {
      const t = tasks.get(ev.task_id);
      if (t) t.state = "running";
    }
    if (type === "task_complete" && ev.task_id) {
      const t = tasks.get(ev.task_id);
      if (t) t.state = "waiting_review";
    }
    if (type === "task_error" && ev.task_id) {
      const t = tasks.get(ev.task_id);
      if (t) t.state = "failed";
    }
    if (type === "review_complete") {
      for (const t of tasks.values()) {
        if (t.state === "waiting_review") {
          t.state = ev.approved ? "completed" : "rejected";
          t.review_approved = ev.approved;
          t.review_feedback = ev.feedback;
        }
      }
    }
    if (type === "task_rejected") {
      for (const t of tasks.values()) {
        if (t.assigned_to === ev.role && t.state === "waiting_review") {
          t.state = "rejected";
        }
      }
    }
  }

  return decomposedTasks;
}

/* ─── Pipeline Flow Diagram ────────────────────────────── */
function PipelineFlow({ loc, events }: { loc: Locale; events: any[] }) {
  // Determine current phase from events
  const currentPhase = useMemo(() => {
    let phase = "idle";
    for (const ev of events) {
      switch (ev.type) {
        case "run_started": phase = "cto_planning"; break;
        case "agent_activity":
          if (ev.role === "cto") phase = "cto_planning";
          if (ev.role === "manager") phase = "task_decomposition";
          if (ev.role === "reviewer") phase = "review";
          break;
        case "plan_created": phase = "task_decomposition"; break;
        case "tasks_decomposed": phase = "execution"; break;
        case "task_started": phase = "execution"; break;
        case "review_complete":
          phase = ev.approved ? "completed" : "rejected";
          break;
        case "iteration_approved": phase = "completed"; break;
        case "run_complete": phase = "completed"; break;
        case "run_error": phase = "error"; break;
      }
    }
    return phase;
  }, [events]);

  const steps = [
    { id: "user", icon: "\uD83D\uDC64", label: loc === "ja" ? "ユーザー" : "User" },
    { id: "cto_planning", icon: "\uD83D\uDCCB", label: "CTO" },
    { id: "task_decomposition", icon: "\uD83D\uDCC1", label: "PM" },
    { id: "execution", icon: "\u2699\uFE0F", label: loc === "ja" ? "実行" : "Execute" },
    { id: "review", icon: "\uD83D\uDCDD", label: loc === "ja" ? "レビュー" : "Review" },
    { id: "completed", icon: "\u2714", label: loc === "ja" ? "完了" : "Done" },
  ];

  const phaseOrder = ["idle", "user", "cto_planning", "task_decomposition", "execution", "review", "completed"];
  const currentIdx = phaseOrder.indexOf(currentPhase);

  return (
    <div className="pipeline-flow">
      <div className="pipeline-flow-label">{loc === "ja" ? "連携フロー" : "Agent Flow"}</div>
      <div className="pipeline-steps">
        {steps.map((step, i) => {
          const stepIdx = phaseOrder.indexOf(step.id);
          let stepState = "pending";
          if (currentPhase === "error") {
            stepState = stepIdx <= currentIdx ? "error" : "pending";
          } else if (currentPhase === "rejected") {
            stepState = step.id === "review" ? "rejected" : (stepIdx < currentIdx ? "completed" : "pending");
          } else if (stepIdx < currentIdx) {
            stepState = "completed";
          } else if (stepIdx === currentIdx) {
            stepState = "running";
          }
          return (
            <div key={step.id} className="pipeline-step-wrap">
              <div className={`pipeline-step pipeline-step-${stepState}`}>
                <span className="pipeline-step-icon">{step.icon}</span>
                <span className="pipeline-step-label">{step.label}</span>
              </div>
              {i < steps.length - 1 && (
                <div className={`pipeline-arrow ${stepIdx < currentIdx ? "pipeline-arrow-active" : ""}`}>
                  {currentPhase === "rejected" && step.id === "review" ? "\u21A9" : "\u2192"}
                </div>
              )}
            </div>
          );
        })}
      </div>
      {currentPhase === "rejected" && (
        <div className="pipeline-rejection-note">
          {loc === "ja" ? "\u21A9 Reviewer \u2192 Engineer \u5DEE\u3057\u623B\u3057\u4E2D" : "\u21A9 Reviewer \u2192 Engineer rejection"}
        </div>
      )}
    </div>
  );
}

/* ─── Main Component ───────────────────────────────────── */
export function TaskGraph({ runStatus, events = [] }: Props) {
  const { t, locale } = useI18n();
  const loc = locale as Locale;

  const tasks = useMemo(() => deriveTasksFromEvents(events), [events]);

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const task of tasks) {
      counts[task.state] = (counts[task.state] || 0) + 1;
    }
    return counts;
  }, [tasks]);

  return (
    <div className="task-flow-panel">
      {/* Pipeline flow diagram */}
      <PipelineFlow loc={loc} events={events} />

      {/* Status summary */}
      {tasks.length > 0 && (
        <div className="task-flow-summary">
          {Object.entries(statusCounts).map(([state, count]) => {
            const info = TASK_STATE_META[state] || TASK_STATE_META.idle;
            return (
              <span key={state} className="task-flow-badge" style={{ color: info.color }}>
                {info.dot} {info.label[loc]}: {count}
              </span>
            );
          })}
        </div>
      )}

      {/* Task list */}
      <div className="task-flow-list">
        {tasks.length === 0 ? (
          <div className="task-flow-empty">
            {t("noActiveTasks")}
          </div>
        ) : (
          tasks.map((task, i) => {
            const roleMeta = ROLE_META[task.assigned_to] || ROLE_META.engineer;
            const fromMeta = ROLE_META[task.from_role] || ROLE_META.manager;
            const stateInfo = TASK_STATE_META[task.state] || TASK_STATE_META.idle;
            return (
              <div key={task.task_id || i} className={`task-flow-card task-flow-card-${task.state}`}>
                <div className="task-flow-card-header">
                  <span className="task-flow-card-route">
                    <span style={{ color: fromMeta.color }}>{fromMeta.icon}</span>
                    <span className="task-flow-card-arrow">{"\u2192"}</span>
                    <span style={{ color: roleMeta.color }}>{roleMeta.icon} {roleMeta.label[loc]}</span>
                  </span>
                  <span className="task-flow-card-state" style={{ color: stateInfo.color }}>
                    {stateInfo.dot} {stateInfo.label[loc]}
                  </span>
                </div>
                <div className="task-flow-card-desc">{task.description}</div>
                {task.state === "rejected" && task.review_feedback && (
                  <div className="task-flow-card-feedback">
                    {"\u21A9"} {task.review_feedback}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
