"use client";

import { useRef, useEffect, useState, useMemo, useCallback } from "react";
import { useI18n, type Locale } from "@/lib/i18n";
import { ROLE_META, TASK_STATE_META } from "@/lib/constants";
import type { OrchestratorEvent, AgentProfileAssignment } from "@/lib/types";
import * as api from "@/lib/api";

/* ─── Types ────────────────────────────────────────────── */

interface Props {
  events: OrchestratorEvent[];
  agentProfiles?: Record<string, AgentProfileAssignment>;
  activeProject?: string | null;
  onSendOrder?: (order: string) => Promise<void>;
}

/* ─── Per-pane log line ────────────────────────────────── */
interface LogLine {
  text: string;
  type: "system" | "task" | "complete" | "error" | "review" | "plan" | "activity" | "info" | "rejected" | "progress";
  timestamp?: string;
}

/* Helper: role display name */
function roleName(role: string, loc: Locale): string {
  const meta = ROLE_META[role];
  if (meta) return meta.label[loc];
  return role;
}

/* ─── Build natural-language per-agent logs from events ── */
function buildAgentLogs(events: OrchestratorEvent[], loc: Locale): Record<string, LogLine[]> {
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
        push("_system", {
          text: loc === "ja"
            ? `${ev.agents?.length || 0}体のエージェントで実行を開始します`
            : `Starting run with ${ev.agents?.length || 0} agents`,
          type: "system", timestamp: ts,
        });
        break;

      case "run_complete": {
        const elapsed = ev.elapsed_seconds ? `（${Math.round(ev.elapsed_seconds)}秒）` : "";
        push("_system", {
          text: loc === "ja" ? `全工程が完了しました${elapsed}` : "Run complete",
          type: "complete", timestamp: ts,
        });
        break;
      }

      case "run_error":
        push("_system", {
          text: loc === "ja"
            ? `エラーが発生しました: ${ev.error || ev.message || "不明"}`
            : `Error: ${ev.error || ev.message || "unknown"}`,
          type: "error", timestamp: ts,
        });
        break;

      case "run_cancelled":
        push("_system", {
          text: loc === "ja" ? "実行がキャンセルされました" : "Cancelled",
          type: "error", timestamp: ts,
        });
        break;

      case "iteration_started":
        for (const r of Object.keys(ROLE_META)) {
          push(r, {
            text: loc === "ja"
              ? `── イテレーション ${ev.iteration} 開始 ──`
              : `── Iteration ${ev.iteration} ──`,
            type: "system", timestamp: ts,
          });
        }
        break;

      case "plan_created": {
        const summary = ev.plan_summary || ev.message || "";
        push("cto", {
          text: loc === "ja"
            ? `プランを策定しました。各担当に作業を割り当てます`
            : "Plan created. Assigning work to agents",
          type: "plan", timestamp: ts,
        });
        if (summary) {
          push("cto", { text: summary, type: "info", timestamp: ts });
        }
        break;
      }

      case "tasks_decomposed": {
        const count = ev.task_count || ev.tasks?.length || 0;
        push("manager", {
          text: loc === "ja"
            ? `プランを${count}件のタスクに分解しました`
            : `Decomposed into ${count} tasks`,
          type: "plan", timestamp: ts,
        });
        if (ev.tasks) {
          for (const t of ev.tasks) {
            const targetName = roleName(t.role, loc);
            push("manager", {
              text: loc === "ja"
                ? `${targetName}に「${t.desc}」を発注しました`
                : `Assigned "${t.desc}" to ${targetName}`,
              type: "info", timestamp: ts,
            });
          }
        }
        break;
      }

      case "task_started": {
        const taskDesc = ev.task || ev.message || "";
        if (role) {
          push(role, {
            text: loc === "ja"
              ? `「${taskDesc}」の作業を開始しました`
              : `Started: "${taskDesc}"`,
            type: "task", timestamp: ts,
          });
          push(role, {
            text: loc === "ja" ? "作業中" : "Working",
            type: "progress", timestamp: ts,
          });
        }
        break;
      }

      case "agent_activity": {
        const msg = ev.message || ev.activity || "";
        if (role && msg) {
          push(role, { text: msg, type: "activity", timestamp: ts });
        }
        break;
      }

      case "task_complete": {
        const summary = ev.summary || ev.message || "";
        if (role) {
          push(role, {
            text: loc === "ja"
              ? `作業が完了しました${summary ? `：${summary}` : ""}`
              : `Completed${summary ? `: ${summary}` : ""}`,
            type: "complete", timestamp: ts,
          });
          if (ev.files_modified && ev.files_modified.length > 0) {
            push(role, {
              text: loc === "ja"
                ? `変更ファイル: ${ev.files_modified.join(", ")}`
                : `Modified: ${ev.files_modified.join(", ")}`,
              type: "info", timestamp: ts,
            });
          }
          push(role, {
            text: loc === "ja" ? "次の担当に引き継ぎます" : "Handing off",
            type: "info", timestamp: ts,
          });
        }
        break;
      }

      case "task_error":
        if (role) {
          push(role, {
            text: loc === "ja"
              ? `エラーが発生しました: ${ev.error || ev.message || ""}`
              : `Error: ${ev.error || ev.message || ""}`,
            type: "error", timestamp: ts,
          });
        }
        break;

      case "task_timeout":
        if (role) {
          push(role, {
            text: loc === "ja"
              ? `タイムアウトしました（${ev.timeout}秒）`
              : `Timed out (${ev.timeout}s)`,
            type: "error", timestamp: ts,
          });
        }
        break;

      case "review_complete": {
        const approved = ev.approved;
        const score = ev.score || "?";
        const feedback = ev.feedback || "";
        push("reviewer", {
          text: approved
            ? (loc === "ja" ? `レビュー完了：承認しました（スコア: ${score}/10）` : `Approved (${score}/10)`)
            : (loc === "ja" ? `レビュー完了：差し戻しました（スコア: ${score}/10）` : `Rejected (${score}/10)`),
          type: approved ? "complete" : "rejected",
          timestamp: ts,
        });
        if (!approved && feedback) {
          push("reviewer", {
            text: loc === "ja" ? `修正事項: ${feedback}` : `Feedback: ${feedback}`,
            type: "rejected", timestamp: ts,
          });
        }
        if (ev.issues) {
          for (const issue of ev.issues) {
            push("reviewer", {
              text: `[${issue.severity}] ${issue.description}`,
              type: "rejected", timestamp: ts,
            });
          }
        }
        break;
      }

      case "task_rejected":
        if (role) {
          push(role, {
            text: loc === "ja"
              ? `差し戻しを受けました${ev.reason ? `：${ev.reason}` : ""}。修正に取り掛かります`
              : `Rejected${ev.reason ? `: ${ev.reason}` : ""}. Fixing...`,
            type: "rejected", timestamp: ts,
          });
        }
        break;

      case "dag_execution":
        push("_system", {
          text: loc === "ja"
            ? `${ev.total_tasks}件のタスクを並列処理します`
            : `Processing ${ev.total_tasks} tasks in parallel`,
          type: "system", timestamp: ts,
        });
        break;

      case "dag_layer_start":
        push("_system", {
          text: loc === "ja"
            ? `レイヤー${ev.layer}のタスクを実行中`
            : `Executing layer ${ev.layer}`,
          type: "system", timestamp: ts,
        });
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
function deriveAgentStates(events: OrchestratorEvent[]): Record<string, string> {
  const states: Record<string, string> = {};
  for (const ev of events) {
    const role = ev.role || "";
    if (!role || role === "orchestrator") continue;
    switch (ev.type) {
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

/* ─── Blinking dots ───────────────────────────────────── */
function BlinkingDots() {
  return (
    <span className="blinking-dots">
      <span className="dot dot-1">.</span>
      <span className="dot dot-2">.</span>
      <span className="dot dot-3">.</span>
    </span>
  );
}

/* ─── Terminal Pane ────────────────────────────────────── */
function TerminalPane({ role, logs, meta, agentState, loc, modelName, modelConnected }: {
  role: string;
  logs: LogLine[];
  meta: typeof ROLE_META[string];
  agentState: string;
  loc: Locale;
  modelName?: string;
  modelConnected?: boolean;
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
  const displayName = meta.label[loc];
  const isRunning = agentState === "running";

  return (
    <div className="terminal-pane" style={{ "--pane-border": meta.border } as React.CSSProperties}>
      {/* Title bar */}
      <div className="terminal-titlebar">
        <span className="terminal-titlebar-icon">{meta.icon}</span>
        <span className="terminal-titlebar-name" style={{ color: meta.color }}>{displayName}</span>
        {modelName && (
          <span
            className={`terminal-titlebar-model ${modelConnected === false ? "disconnected" : ""}`}
            title={modelName + (modelConnected === false ? (loc === "ja" ? " (未接続)" : " (disconnected)") : "")}
          >
            {modelName}
            {modelConnected === false && (loc === "ja" ? " (未接続)" : " (disconnected)")}
          </span>
        )}
        {isRunning && <BlinkingDots />}
        <span className="terminal-titlebar-state" style={{ color: stateInfo.color }}>
          {stateInfo.label[loc]}
        </span>
      </div>
      {/* Terminal body */}
      <div className="terminal-body" ref={scrollRef} onScroll={handleScroll}>
        {logs.length === 0 ? (
          <div className="terminal-empty">
            <span className="terminal-empty-text">{loc === "ja" ? "待機中" : "Standby"}</span>
            {meta.hint && <span className="terminal-empty-hint">{meta.hint[loc]}</span>}
            {modelName && <span className="terminal-empty-model">{modelName}</span>}
          </div>
        ) : (
          logs.map((line, i) => {
            // Skip progress lines for agents that are no longer running
            if (line.type === "progress" && !isRunning) return null;
            return (
              <div key={i} className={`terminal-line terminal-line-${line.type}`}>
                {line.timestamp && (
                  <span className="terminal-ts">{new Date(line.timestamp).toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</span>
                )}
                <span className="terminal-text">
                  {line.text}
                  {line.type === "progress" && isRunning && <BlinkingDots />}
                </span>
              </div>
            );
          })
        )}
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
        placeholder={loc === "ja" ? "例: 「エラーハンドリングを追加して」" : "e.g. \"Add error handling\""}
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

  // モデル割当と接続状態
  const [modelAssignments, setModelAssignments] = useState<Record<string, string>>({});
  const [modelConnected, setModelConnected] = useState<Record<string, boolean>>({});

  const checkModels = useCallback(async () => {
    try {
      const data = await api.getAssignments();
      const assignments: Record<string, string> = data.assignments || {};
      setModelAssignments(assignments);

      // 利用可能モデル一覧を取得して接続状態を判定
      try {
        const modelsData = await api.listModels();
        const available = new Set(Object.keys(modelsData.models || {}));
        const connected: Record<string, boolean> = {};
        for (const [role, model] of Object.entries(assignments)) {
          connected[role] = available.has(model);
        }
        setModelConnected(connected);
      } catch {
        // モデル一覧取得失敗 = 全て未接続扱い
        const connected: Record<string, boolean> = {};
        for (const role of Object.keys(assignments)) {
          connected[role] = false;
        }
        setModelConnected(connected);
      }
    } catch {
      // assignments取得失敗
    }
  }, []);

  useEffect(() => {
    checkModels();
    const interval = setInterval(checkModels, 30000);
    return () => clearInterval(interval);
  }, [checkModels]);

  // 全エージェントを常に表示（LLM接続に依存しない）
  const DEFAULT_ROLES = ["cto", "manager", "researcher", "engineer", "reviewer", "tester", "optimizer", "documenter"];
  const activeRoles = useMemo(() => {
    const roles = new Set<string>(DEFAULT_ROLES);
    // イベントやプロファイルに追加ロールがあれば含める
    for (const role of Object.keys(agentProfiles)) {
      if (ROLE_META[role]) roles.add(role);
    }
    for (const ev of events) {
      const role = ev.role || ev.sender || "";
      if (role && role !== "orchestrator" && ROLE_META[role]) {
        roles.add(role);
      }
    }
    const ORDER = ["cto", "manager", "researcher", "engineer", "reviewer", "tester", "optimizer", "documenter", "marketer"];
    return ORDER.filter((r) => roles.has(r));
  }, [events, agentProfiles]);

  if (!activeProject) {
    return (
      <div className="terminal-grid-container">
        <div className="terminal-grid-empty">
          <div className="terminal-grid-empty-icon">{"\uD83D\uDCC2"}</div>
          <div>{t("selectProject")}</div>
        </div>
      </div>
    );
  }

  // Grid layout based on active role count（エージェント増加にも対応）
  const paneCount = activeRoles.length;
  let gridClass = "terminal-grid-2x2";
  if (paneCount <= 1) gridClass = "terminal-grid-1x1";
  else if (paneCount === 2) gridClass = "terminal-grid-1x2";
  else if (paneCount === 3) gridClass = "terminal-grid-1-2";
  else if (paneCount <= 4) gridClass = "terminal-grid-2x2";
  else if (paneCount <= 6) gridClass = "terminal-grid-2x3";
  else if (paneCount <= 8) gridClass = "terminal-grid-2x4";
  else if (paneCount <= 9) gridClass = "terminal-grid-3x3";
  else if (paneCount <= 12) gridClass = "terminal-grid-3x4";
  else gridClass = "terminal-grid-4x4";

  return (
    <div className="terminal-grid-container">
      {/* Terminal panes */}
      <div className={`terminal-grid ${gridClass}`}>
        {activeRoles.map((role) => {
          const meta = ROLE_META[role];
          const logs = agentLogs[role] || [];
          const state = agentStates[role] || "idle";
          return (
            <TerminalPane
              key={role}
              role={role}
              logs={logs}
              meta={meta}
              agentState={state}
              loc={loc}
              modelName={modelAssignments[role]}
              modelConnected={modelAssignments[role] ? modelConnected[role] : undefined}
            />
          );
        })}
      </div>

      {/* Command input bar */}
      <CommandBar loc={loc} onSend={onSendOrder} activeProject={activeProject} />
    </div>
  );
}
