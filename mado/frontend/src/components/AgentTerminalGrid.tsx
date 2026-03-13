"use client";

import { useRef, useEffect, useState, useMemo } from "react";
import { useI18n, type Locale } from "@/lib/i18n";
import { ROLE_META, TASK_STATE_META } from "@/lib/constants";

/* ─── Types ────────────────────────────────────────────── */
interface AgentProfile {
  title: string;
  personality: string;
}

interface Props {
  events: any[];
  agentProfiles?: Record<string, AgentProfile>;
  activeProject?: string | null;
  onSendOrder?: (order: string) => Promise<void>;
}

/* ─── Flow indicator ───────────────────────────────────── */
interface TaskFlowItem {
  task_id: string;
  from_role: string;
  to_role: string;
  state: string;
  description: string;
  timestamp: string;
}

/* ─── Extract per-agent log lines from events ──────────── */
interface LogLine {
  text: string;
  type: "system" | "task" | "complete" | "error" | "review" | "plan" | "activity" | "info" | "rejected";
  timestamp?: string;
  task_id?: string;
  state?: string;
}

function buildAgentLogs(events: any[], loc: Locale): Record<string, LogLine[]> {
  const logs: Record<string, LogLine[]> = {};
  const push = (role: string, line: LogLine) => {
    if (!logs[role]) logs[role] = [];
    logs[role].push(line);
  };

  for (const ev of events) {
    const type = ev.type || "";
    const role = ev.role || ev.sender || "";
    const ts = ev.timestamp || "";

    switch (type) {
      case "run_started":
        push("_system", { text: loc === "ja" ? `${ev.agents?.length || 0}体のエージェントで開始` : ev.message || "Run started", type: "system", timestamp: ts });
        break;
      case "run_complete":
        push("_system", { text: loc === "ja" ? "実行完了" : "Run complete", type: "complete", timestamp: ts });
        break;
      case "run_error":
        push("_system", { text: `ERROR: ${ev.error || ev.message || "unknown"}`, type: "error", timestamp: ts });
        break;
      case "run_cancelled":
        push("_system", { text: loc === "ja" ? "キャンセル" : "Cancelled", type: "error", timestamp: ts });
        break;
      case "iteration_started":
        push("_system", { text: loc === "ja" ? `── イテレーション ${ev.iteration} 開始 ──` : `── Iteration ${ev.iteration} ──`, type: "system", timestamp: ts });
        // Also push to all roles
        for (const r of Object.keys(ROLE_META)) {
          push(r, { text: loc === "ja" ? `── イテレーション ${ev.iteration} ──` : `── Iteration ${ev.iteration} ──`, type: "system", timestamp: ts });
        }
        break;
      case "plan_created":
        push("cto", { text: ev.plan_summary || ev.message || "Plan created", type: "plan", timestamp: ts });
        break;
      case "tasks_decomposed":
        push("manager", { text: ev.message || `${ev.task_count} tasks decomposed`, type: "plan", timestamp: ts });
        if (ev.tasks) {
          for (const t of ev.tasks) {
            push("manager", { text: `  → [${t.role}] ${t.desc}`, type: "info", timestamp: ts, task_id: t.id });
          }
        }
        break;
      case "agent_activity":
        if (role) push(role, { text: ev.message || ev.activity || "", type: "activity", timestamp: ts });
        break;
      case "task_started":
        if (role) push(role, { text: `> ${ev.task || ev.message || "task started"}`, type: "task", timestamp: ts, task_id: ev.task_id, state: "running" });
        break;
      case "task_complete":
        if (role) push(role, { text: `✓ ${ev.summary || ev.message || "done"}`, type: "complete", timestamp: ts, task_id: ev.task_id, state: "completed" });
        break;
      case "task_error":
        if (role) push(role, { text: `✗ ${ev.error || ev.message || "error"}`, type: "error", timestamp: ts, task_id: ev.task_id, state: "failed" });
        break;
      case "task_timeout":
        if (role) push(role, { text: `⏱ TIMEOUT (${ev.timeout}s)`, type: "error", timestamp: ts, state: "failed" });
        break;
      case "review_complete": {
        const approved = ev.approved;
        const score = ev.score || "?";
        const feedback = ev.feedback || "";
        push("reviewer", {
          text: approved
            ? (loc === "ja" ? `✓ 承認 (スコア: ${score}/10)` : `✓ Approved (score: ${score}/10)`)
            : (loc === "ja" ? `✗ 差し戻し (スコア: ${score}/10)\n  ${feedback}` : `✗ Rejected (score: ${score}/10)\n  ${feedback}`),
          type: approved ? "complete" : "rejected",
          timestamp: ts,
          state: approved ? "completed" : "rejected",
        });
        break;
      }
      case "task_rejected":
        if (role) push(role, { text: loc === "ja" ? `← 差し戻し: ${ev.reason || ""}` : `← Rejected: ${ev.reason || ""}`, type: "rejected", timestamp: ts, state: "rejected" });
        break;
      case "dag_execution":
        push("_system", { text: ev.message || `DAG: ${ev.total_tasks} tasks`, type: "system", timestamp: ts });
        break;
      case "dag_layer_start":
        push("_system", { text: ev.message || `Layer ${ev.layer}`, type: "system", timestamp: ts });
        break;
      default:
        if (ev.message && role) {
          push(role, { text: ev.message, type: "activity", timestamp: ts });
        }
    }
  }
  return logs;
}

/* ─── Derive agent states from events ──────────────────── */
function deriveAgentStates(events: any[]): Record<string, string> {
  const states: Record<string, string> = {};
  for (const ev of events) {
    const role = ev.role || "";
    const type = ev.type || "";
    if (!role || role === "orchestrator") continue;
    switch (type) {
      case "agent_activity":
      case "task_started":
        states[role] = "running";
        break;
      case "task_complete":
        states[role] = "completed";
        break;
      case "task_error":
      case "task_timeout":
        states[role] = "failed";
        break;
      case "review_complete":
        states[role] = ev.approved ? "completed" : "rejected";
        break;
      case "task_rejected":
        states[role] = "rejected";
        break;
    }
  }
  return states;
}

/* ─── Derive task flow from events ─────────────────────── */
function deriveTaskFlow(events: any[]): TaskFlowItem[] {
  const flowMap = new Map<string, TaskFlowItem>();
  const flowList: TaskFlowItem[] = [];
  for (const ev of events) {
    const type = ev.type || "";
    if (type === "tasks_decomposed" && ev.tasks) {
      for (const t of ev.tasks) {
        const id = t.id || "";
        const item: TaskFlowItem = {
          task_id: id,
          from_role: "manager",
          to_role: t.role || "engineer",
          state: "queued",
          description: t.desc || "",
          timestamp: ev.timestamp || "",
        };
        flowMap.set(id, item);
        flowList.push(item);
      }
    }
    if (type === "task_started" && ev.task_id) {
      const existing = flowMap.get(ev.task_id);
      if (existing) existing.state = "running";
    }
    if (type === "task_complete" && ev.task_id) {
      const existing = flowMap.get(ev.task_id);
      if (existing) existing.state = "waiting_review";
    }
    if (type === "review_complete") {
      for (const f of flowList) {
        if (f.state === "waiting_review") {
          f.state = ev.approved ? "completed" : "rejected";
        }
      }
    }
  }
  return flowList;
}

/* ─── Terminal Pane ────────────────────────────────────── */
function TerminalPane({ role, logs, meta, profile, agentState, loc }: {
  role: string;
  logs: LogLine[];
  meta: typeof ROLE_META[string];
  profile?: AgentProfile;
  agentState: string;
  loc: Locale;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const autoScrollRef = useRef(true);

  useEffect(() => {
    const el = scrollRef.current;
    if (el && autoScrollRef.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [logs.length]);

  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    autoScrollRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
  };

  const stateInfo = TASK_STATE_META[agentState] || TASK_STATE_META.idle;
  const displayName = profile?.title || meta.label[loc];

  return (
    <div className="terminal-pane" style={{ "--pane-border": meta.border } as React.CSSProperties}>
      {/* Title bar */}
      <div className="terminal-titlebar">
        <span className="terminal-titlebar-icon">{meta.icon}</span>
        <span className="terminal-titlebar-name" style={{ color: meta.color }}>{displayName}</span>
        <span className="terminal-titlebar-state" style={{ color: stateInfo.color }}>
          {stateInfo.label[loc]}
        </span>
      </div>
      {/* Terminal body */}
      <div className="terminal-body" ref={scrollRef} onScroll={handleScroll}>
        {logs.length === 0 ? (
          <div className="terminal-empty">
            <span className="terminal-cursor">_</span>
            <span className="terminal-empty-text">{loc === "ja" ? "待機中..." : "Standby..."}</span>
          </div>
        ) : (
          logs.map((line, i) => (
            <div key={i} className={`terminal-line terminal-line-${line.type}`}>
              {line.timestamp && (
                <span className="terminal-ts">{new Date(line.timestamp).toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</span>
              )}
              <span className="terminal-text">{line.text}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

/* ─── Task Flow Bar ────────────────────────────────────── */
function TaskFlowBar({ flow, loc }: { flow: TaskFlowItem[]; loc: Locale }) {
  if (flow.length === 0) return null;
  return (
    <div className="task-flow-bar">
      <div className="task-flow-label">{loc === "ja" ? "タスクフロー" : "Task Flow"}:</div>
      <div className="task-flow-items">
        {flow.slice(-8).map((item, i) => {
          const stateInfo = TASK_STATE_META[item.state] || TASK_STATE_META.idle;
          const fromMeta = ROLE_META[item.from_role] || ROLE_META.manager;
          const toMeta = ROLE_META[item.to_role] || ROLE_META.engineer;
          return (
            <div key={i} className="task-flow-item" title={item.description}>
              <span className="task-flow-from" style={{ color: fromMeta.color }}>{fromMeta.icon}</span>
              <span className="task-flow-arrow">→</span>
              <span className="task-flow-to" style={{ color: toMeta.color }}>{toMeta.icon}</span>
              <span className="task-flow-state" style={{ color: stateInfo.color }}>{stateInfo.label[loc]}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ─── Command Input Bar ────────────────────────────────── */
function CommandBar({ loc, onSend, activeProject }: {
  loc: Locale;
  onSend?: (order: string) => Promise<void>;
  activeProject?: string | null;
}) {
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  const handleSubmit = async () => {
    if (!input.trim() || !onSend || sending) return;
    setSending(true);
    try {
      await onSend(input.trim());
      setInput("");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="terminal-command-bar">
      <span className="terminal-command-prompt">
        {activeProject ? `${activeProject}` : "mado"} $
      </span>
      <input
        className="terminal-command-input"
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") handleSubmit(); }}
        placeholder={loc === "ja" ? "追加指示を入力..." : "Enter additional instruction..."}
        disabled={sending || !activeProject}
      />
      <button
        className="terminal-command-send"
        onClick={handleSubmit}
        disabled={!input.trim() || sending || !activeProject}
      >
        {sending ? "..." : (loc === "ja" ? "送信" : "Send")}
      </button>
    </div>
  );
}

/* ─── Main Component ───────────────────────────────────── */
export function AgentTerminalGrid({ events, agentProfiles = {}, activeProject, onSendOrder }: Props) {
  const { t, locale } = useI18n();
  const loc = locale as Locale;

  const agentLogs = useMemo(() => buildAgentLogs(events, loc), [events, loc]);
  const agentStates = useMemo(() => deriveAgentStates(events), [events]);
  const taskFlow = useMemo(() => deriveTaskFlow(events), [events]);

  // Determine active roles from events (preserve display order)
  const ROLE_ORDER = ["cto", "manager", "researcher", "engineer", "reviewer", "tester", "optimizer", "documenter", "marketer"];
  const activeRoles = useMemo(() => {
    const roles = new Set<string>();
    for (const ev of events) {
      const role = ev.role || ev.sender || "";
      if (role && role !== "orchestrator" && ROLE_META[role]) {
        roles.add(role);
      }
    }
    return ROLE_ORDER.filter((r) => roles.has(r));
  }, [events]);

  if (events.length === 0) {
    return (
      <div className="terminal-grid-container">
        <div className="terminal-grid-empty">
          <div className="terminal-grid-empty-icon">{"\uD83D\uDCAC"}</div>
          <div>{t("waitingForAgents")}</div>
          <div className="terminal-grid-empty-sub">{t("startRunToSpawn")}</div>
        </div>
        <CommandBar loc={loc} onSend={onSendOrder} activeProject={activeProject} />
      </div>
    );
  }

  // Calculate grid layout based on active role count
  const paneCount = activeRoles.length;
  let gridClass = "terminal-grid-2x2";
  if (paneCount <= 1) gridClass = "terminal-grid-1x1";
  else if (paneCount === 2) gridClass = "terminal-grid-1x2";
  else if (paneCount === 3) gridClass = "terminal-grid-1-2";
  else if (paneCount <= 4) gridClass = "terminal-grid-2x2";
  else if (paneCount <= 6) gridClass = "terminal-grid-2x3";
  else gridClass = "terminal-grid-3x3";

  return (
    <div className="terminal-grid-container">
      {/* Task flow indicator */}
      <TaskFlowBar flow={taskFlow} loc={loc} />

      {/* Terminal panes */}
      <div className={`terminal-grid ${gridClass}`}>
        {activeRoles.map((role) => {
          const meta = ROLE_META[role];
          const logs = agentLogs[role] || [];
          const profile = agentProfiles[role];
          const state = agentStates[role] || "idle";
          return (
            <TerminalPane
              key={role}
              role={role}
              logs={logs}
              meta={meta}
              profile={profile}
              agentState={state}
              loc={loc}
            />
          );
        })}
      </div>

      {/* Command input bar */}
      <CommandBar loc={loc} onSend={onSendOrder} activeProject={activeProject} />
    </div>
  );
}
