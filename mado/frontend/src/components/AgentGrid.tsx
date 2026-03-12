"use client";

import { useRef, useEffect } from "react";
import { useI18n, type Locale } from "@/lib/i18n";

interface AgentProfile {
  title: string;
  personality: string;
}

interface Props {
  agents: any[];
  events: any[];
  agentProfiles?: Record<string, AgentProfile>;
  assignments?: Record<string, string>;
}

const ROLE_META: Record<string, { icon: string; label: { en: string; ja: string }; color: string }> = {
  cto: { icon: "\uD83D\uDCCB", label: { en: "CTO", ja: "CTO" }, color: "#f59e0b" },
  manager: { icon: "\uD83D\uDCC1", label: { en: "PM", ja: "PM" }, color: "#3b82f6" },
  researcher: { icon: "\uD83D\uDD0D", label: { en: "Researcher", ja: "リサーチャー" }, color: "#8b5cf6" },
  engineer: { icon: "\u2699\uFE0F", label: { en: "Engineer", ja: "エンジニア" }, color: "#22c55e" },
  reviewer: { icon: "\uD83D\uDCDD", label: { en: "Reviewer", ja: "レビュアー" }, color: "#ec4899" },
  tester: { icon: "\uD83E\uDDEA", label: { en: "Tester", ja: "テスター" }, color: "#06b6d4" },
  optimizer: { icon: "\u26A1", label: { en: "Optimizer", ja: "オプティマイザー" }, color: "#f97316" },
  documenter: { icon: "\uD83D\uDCD6", label: { en: "Documenter", ja: "ドキュメンター" }, color: "#64748b" },
  marketer: { icon: "\uD83D\uDCE2", label: { en: "Marketer", ja: "マーケター" }, color: "#e11d48" },
  orchestrator: { icon: "\uD83C\uDFAF", label: { en: "System", ja: "システム" }, color: "#94a3b8" },
};

function formatEventMessage(ev: any, loc: Locale): { role: string; text: string; type: string } {
  const role = ev.role || ev.sender || "orchestrator";
  const type = ev.type || "";

  switch (type) {
    case "run_started":
      return { role: "orchestrator", text: ev.message || `Run started with ${ev.agents?.length || 0} agents`, type: "system" };
    case "run_complete":
      return { role: "orchestrator", text: ev.message || "Run completed", type: "system" };
    case "run_cancelled":
      return { role: "orchestrator", text: ev.message || "Run cancelled", type: "system" };
    case "run_error":
      return { role: "orchestrator", text: ev.message || `Error: ${ev.error}`, type: "error" };
    case "iteration_started":
      return { role: "orchestrator", text: ev.message || `Iteration ${ev.iteration} started`, type: "system" };
    case "iteration_complete":
      return { role: "orchestrator", text: ev.message || `Iteration ${ev.iteration} complete`, type: "system" };
    case "iteration_approved":
      return { role: "orchestrator", text: ev.message || "Iteration approved!", type: "success" };
    case "plan_created":
      return { role: "cto", text: ev.message || ev.plan_summary || "Plan created", type: "plan" };
    case "tasks_decomposed":
      return { role: "manager", text: ev.message || `Decomposed into ${ev.task_count} tasks`, type: "plan" };
    case "agent_activity":
      return { role, text: ev.message || `${role}: ${ev.activity}`, type: "activity" };
    case "task_started":
      return { role, text: ev.message || `Started: ${ev.task?.slice(0, 150)}`, type: "task" };
    case "task_complete":
      return { role, text: ev.message || `Completed: ${ev.summary?.slice(0, 150)}`, type: "complete" };
    case "task_error":
      return { role, text: ev.message || `Error: ${ev.error}`, type: "error" };
    case "task_timeout":
      return { role, text: ev.message || `Timeout (${ev.timeout}s)`, type: "error" };
    case "review_complete":
      return { role: "reviewer", text: ev.message || `Review: ${ev.approved ? "Approved" : "Rejected"}`, type: ev.approved ? "success" : "activity" };
    case "dag_execution":
      return { role: "orchestrator", text: ev.message || `DAG: ${ev.total_tasks} tasks, ${ev.layers} layers`, type: "system" };
    case "dag_layer_start":
      return { role: "orchestrator", text: ev.message || `Layer ${ev.layer}: ${ev.task_count} tasks`, type: "system" };
    case "parallel_start":
      return { role: "orchestrator", text: ev.message || `${ev.task_count} tasks in parallel`, type: "system" };
    default:
      if (ev.message) return { role, text: ev.message, type: "activity" };
      return { role, text: JSON.stringify(ev).slice(0, 120), type: "activity" };
  }
}

export function AgentGrid({ events, agentProfiles = {} }: Props) {
  const { t, locale } = useI18n();
  const loc = locale as Locale;
  const scrollRef = useRef<HTMLDivElement>(null);
  const autoScrollRef = useRef(true);

  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    const el = scrollRef.current;
    if (el && autoScrollRef.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [events.length]);

  // Detect if user scrolled up (disable auto-scroll)
  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    autoScrollRef.current = atBottom;
  };

  if (events.length === 0) {
    return (
      <div className="agent-chat-container">
        <div className="agent-chat-empty">
          <div className="agent-chat-empty-icon">{"\uD83D\uDCAC"}</div>
          <div>{t("waitingForAgents")}</div>
          <div className="agent-chat-empty-sub">{t("startRunToSpawn")}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="agent-chat-container">
      <div className="agent-chat-log" ref={scrollRef} onScroll={handleScroll}>
        {events.map((ev, idx) => {
          const { role, text, type } = formatEventMessage(ev, loc);
          const meta = ROLE_META[role] || { icon: "\uD83E\uDD16", label: { en: role, ja: role }, color: "var(--accent)" };
          const profile = agentProfiles[role];
          const displayName = profile?.title || meta.label[loc];
          const isSystem = type === "system";

          return (
            <div key={idx} className={`chat-msg chat-msg-${type} ${isSystem ? "chat-msg-system" : ""}`}>
              {!isSystem && (
                <div className="chat-avatar" style={{ color: meta.color }}>
                  {meta.icon}
                </div>
              )}
              <div className={`chat-bubble ${isSystem ? "chat-bubble-system" : ""}`}>
                {!isSystem && (
                  <div className="chat-sender" style={{ color: meta.color }}>
                    {displayName}
                  </div>
                )}
                <div className="chat-text">{text}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
