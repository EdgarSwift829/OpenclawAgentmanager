"use client";

import { useRef, useEffect, useState, useMemo } from "react";
import { useI18n, type Locale } from "@/lib/i18n";
import { ROLE_META, TASK_STATE_META } from "@/lib/constants";
import type { OrchestratorEvent, AgentProfileAssignment } from "@/lib/types";

/* ─── Types ────────────────────────────────────────────── */

interface Props {
  events: OrchestratorEvent[];
  agentProfiles?: Record<string, AgentProfileAssignment>;
  activeProject?: string | null;
  onSendOrder?: (order: string) => Promise<void>;
}

/* ─── Chat message ─────────────────────────────────────── */
interface ChatMessage {
  id: number;
  role: string;           // agent role or "_system"
  roleName: string;       // display name
  icon: string;
  color: string;
  text: string;
  timestamp?: string;
  isProgress?: boolean;   // if true, show blinking dots
}

/* Helper: role display name */
function roleName(role: string, loc: Locale): string {
  const meta = ROLE_META[role];
  if (meta) return meta.label[loc];
  if (role === "_system") return loc === "ja" ? "システム" : "System";
  return role;
}

function roleIcon(role: string): string {
  return ROLE_META[role]?.icon || "\u2699\uFE0F";
}

function roleColor(role: string): string {
  return ROLE_META[role]?.color || "#888";
}

/* ─── Build chat messages from events ──────────────────── */
function buildChatMessages(events: OrchestratorEvent[], loc: Locale): ChatMessage[] {
  const msgs: ChatMessage[] = [];
  let id = 0;

  // Track which tasks are assigned to which role (for natural delegation messages)
  const taskAssignments: Record<string, { role: string; desc: string }> = {};

  for (const ev of events) {
    const type = ev.type || "";
    const role = ev.role || ev.sender || "";
    const ts = ev.timestamp || "";

    const push = (r: string, text: string, isProgress = false) => {
      msgs.push({
        id: id++,
        role: r,
        roleName: roleName(r, loc),
        icon: roleIcon(r),
        color: roleColor(r),
        text,
        timestamp: ts,
        isProgress,
      });
    };

    switch (type) {
      case "run_started": {
        const agentCount = ev.agents?.length || 0;
        push("_system", loc === "ja"
          ? `プロジェクトの実行を開始します（${agentCount}体のエージェントが参加）`
          : `Starting project run with ${agentCount} agents`);
        break;
      }

      case "run_complete": {
        const elapsed = ev.elapsed_seconds
          ? (loc === "ja" ? `（${Math.round(ev.elapsed_seconds)}秒）` : ` (${Math.round(ev.elapsed_seconds)}s)`)
          : "";
        push("_system", loc === "ja"
          ? `全工程が完了しました${elapsed}`
          : `All phases completed${elapsed}`);
        break;
      }

      case "run_error":
        push("_system", loc === "ja"
          ? `エラーが発生しました: ${ev.error || ev.message || "不明"}`
          : `Error occurred: ${ev.error || ev.message || "unknown"}`);
        break;

      case "run_cancelled":
        push("_system", loc === "ja" ? "実行がキャンセルされました" : "Run cancelled");
        break;

      case "iteration_started":
        push("_system", loc === "ja"
          ? `── イテレーション ${ev.iteration} を開始します ──`
          : `── Starting iteration ${ev.iteration} ──`);
        break;

      case "plan_created": {
        const summary = ev.plan_summary || ev.message || "";
        push("cto", loc === "ja"
          ? `プランを策定しました。各担当に作業を割り当てます`
          : `Plan created. Assigning work to team members`);
        if (summary) {
          push("cto", summary);
        }
        break;
      }

      case "tasks_decomposed": {
        const count = ev.task_count || ev.tasks?.length || 0;
        push("manager", loc === "ja"
          ? `プランを${count}件のタスクに分解しました`
          : `Decomposed plan into ${count} tasks`);
        if (ev.tasks) {
          for (const t of ev.tasks) {
            taskAssignments[t.id] = { role: t.role, desc: t.desc };
            const targetName = roleName(t.role, loc);
            push("manager", loc === "ja"
              ? `${targetName}に「${t.desc}」を発注しました`
              : `Assigned "${t.desc}" to ${targetName}`);
          }
        }
        break;
      }

      case "task_started": {
        const taskDesc = ev.task || ev.message || "";
        if (role) {
          push(role, loc === "ja"
            ? `「${taskDesc}」の作業を開始しました`
            : `Started working on "${taskDesc}"`);
          // Add a progress message
          push(role, loc === "ja"
            ? "作業中"
            : "Working", true);
        }
        break;
      }

      case "agent_activity": {
        const activityText = ev.message || ev.activity || "";
        if (role && activityText) {
          push(role, activityText);
        }
        break;
      }

      case "task_complete": {
        const summary = ev.summary || ev.message || "";
        if (role) {
          push(role, loc === "ja"
            ? `作業が完了しました${summary ? `：${summary}` : ""}`
            : `Work completed${summary ? `: ${summary}` : ""}`);
          // Check if files were modified
          if (ev.files_modified && ev.files_modified.length > 0) {
            push(role, loc === "ja"
              ? `変更ファイル: ${ev.files_modified.join(", ")}`
              : `Modified: ${ev.files_modified.join(", ")}`);
          }
          push(role, loc === "ja"
            ? "次の担当に引き継ぎます"
            : "Handing off to next role");
        }
        break;
      }

      case "task_error": {
        const errMsg = ev.error || ev.message || "";
        if (role) {
          push(role, loc === "ja"
            ? `作業中にエラーが発生しました: ${errMsg}`
            : `Error during work: ${errMsg}`);
        }
        break;
      }

      case "task_timeout":
        if (role) {
          push(role, loc === "ja"
            ? `タイムアウトしました（${ev.timeout}秒）`
            : `Timed out (${ev.timeout}s)`);
        }
        break;

      case "review_complete": {
        const approved = ev.approved;
        const score = ev.score || "?";
        const feedback = ev.feedback || "";
        if (approved) {
          push("reviewer", loc === "ja"
            ? `レビュー完了：承認しました（スコア: ${score}/10）`
            : `Review complete: Approved (score: ${score}/10)`);
        } else {
          push("reviewer", loc === "ja"
            ? `レビュー完了：差し戻しました（スコア: ${score}/10）`
            : `Review complete: Rejected (score: ${score}/10)`);
          if (feedback) {
            push("reviewer", loc === "ja"
              ? `修正事項: ${feedback}`
              : `Feedback: ${feedback}`);
          }
        }
        // Show issues if any
        if (ev.issues && ev.issues.length > 0) {
          for (const issue of ev.issues) {
            push("reviewer", `[${issue.severity}] ${issue.description}`);
          }
        }
        break;
      }

      case "task_rejected": {
        const reason = ev.reason || "";
        if (role) {
          push(role, loc === "ja"
            ? `差し戻しを受けました${reason ? `：${reason}` : ""}。修正に取り掛かります`
            : `Received rejection${reason ? `: ${reason}` : ""}. Starting corrections`);
        }
        break;
      }

      case "dag_execution":
        push("_system", loc === "ja"
          ? `DAG実行：${ev.total_tasks}件のタスクを並列処理します`
          : `DAG execution: processing ${ev.total_tasks} tasks in parallel`);
        break;

      case "dag_layer_start":
        push("_system", loc === "ja"
          ? `レイヤー${ev.layer}のタスクを実行中`
          : `Executing layer ${ev.layer} tasks`);
        break;

      default:
        if (ev.message && role) {
          push(role, ev.message);
        }
    }
  }

  return msgs;
}

/* ─── Derive which roles are currently "running" ──────── */
function deriveRunningRoles(events: OrchestratorEvent[]): Set<string> {
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
      case "task_error":
      case "task_timeout":
      case "task_rejected":
        states[role] = "done";
        break;
    }
  }
  const running = new Set<string>();
  for (const [role, state] of Object.entries(states)) {
    if (state === "running") running.add(role);
  }
  return running;
}

/* ─── Blinking dots component ─────────────────────────── */
function BlinkingDots() {
  return (
    <span className="blinking-dots">
      <span className="dot dot-1">.</span>
      <span className="dot dot-2">.</span>
      <span className="dot dot-3">.</span>
    </span>
  );
}

/* ─── Task Flow Bar ────────────────────────────────────── */
function TaskFlowBar({ events, loc }: { events: OrchestratorEvent[]; loc: Locale }) {
  // Build active roles status bar
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

  const runningRoles = useMemo(() => deriveRunningRoles(events), [events]);

  if (activeRoles.length === 0) return null;

  return (
    <div className="chat-flow-bar">
      {activeRoles.map((role) => {
        const meta = ROLE_META[role];
        const isRunning = runningRoles.has(role);
        return (
          <div key={role} className={`chat-flow-agent ${isRunning ? "chat-flow-agent-active" : ""}`}>
            <span className="chat-flow-icon">{meta.icon}</span>
            <span className="chat-flow-name" style={{ color: meta.color }}>{meta.label[loc]}</span>
            {isRunning && <BlinkingDots />}
          </div>
        );
      })}
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
  const scrollRef = useRef<HTMLDivElement>(null);
  const autoScrollRef = useRef(true);

  const chatMessages = useMemo(() => buildChatMessages(events, loc), [events, loc]);
  const runningRoles = useMemo(() => deriveRunningRoles(events), [events]);

  // Filter out "progress" messages for non-running roles (they finished)
  const visibleMessages = useMemo(() => {
    return chatMessages.filter((msg) => {
      if (msg.isProgress && !runningRoles.has(msg.role)) return false;
      return true;
    });
  }, [chatMessages, runningRoles]);

  // Auto-scroll
  useEffect(() => {
    const el = scrollRef.current;
    if (el && autoScrollRef.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [visibleMessages.length]);

  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    autoScrollRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
  };

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

  return (
    <div className="terminal-grid-container">
      {/* Active agents status bar */}
      <TaskFlowBar events={events} loc={loc} />

      {/* Chat log */}
      <div className="chat-log" ref={scrollRef} onScroll={handleScroll}>
        {visibleMessages.map((msg) => (
          <div key={msg.id} className={`chat-message ${msg.role === "_system" ? "chat-message-system" : ""}`}>
            {msg.role !== "_system" && (
              <div className="chat-avatar" style={{ borderColor: msg.color }}>
                <span>{msg.icon}</span>
              </div>
            )}
            <div className={`chat-bubble ${msg.role === "_system" ? "chat-bubble-system" : ""}`}>
              {msg.role !== "_system" && (
                <div className="chat-sender" style={{ color: msg.color }}>
                  {msg.roleName}
                  {msg.timestamp && (
                    <span className="chat-time">
                      {new Date(msg.timestamp).toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                    </span>
                  )}
                </div>
              )}
              <div className="chat-text">
                {msg.text}
                {msg.isProgress && <BlinkingDots />}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Command input bar */}
      <CommandBar loc={loc} onSend={onSendOrder} activeProject={activeProject} />
    </div>
  );
}
