"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import * as api from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { ProjectNode, RunStatus, AgentInfo, OrchestratorEvent, AgentProfileAssignment } from "@/lib/types";
import { useInlineStatus, StatusIndicator } from "@/components/Toast";
import { ProjectTree } from "@/components/ProjectTree";
import { AgentTerminalGrid } from "@/components/AgentTerminalGrid";
import { RunControl } from "@/components/RunControl";
import { Timeline } from "@/components/Timeline";
import { ModelPanel } from "@/components/ModelPanel";
import { TaskGraph } from "@/components/TaskGraph";
import { ProjectDetail } from "@/components/ProjectDetail";
import { AgentPanel } from "@/components/AgentPanel";
import { LangSwitcher } from "@/components/LangSwitcher";
import { ErrorBoundary } from "@/components/ErrorBoundary";

// ---------------------------------------------------------------------------
// localStorage persistence for per-project state
// ---------------------------------------------------------------------------
const STORAGE_KEY = "mado_project_states";

interface ProjectState {
  maxIter: number;
  events: OrchestratorEvent[];
}

function loadAllStates(): Record<string, ProjectState> {
  if (typeof window === "undefined") return {};
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveAllStates(states: Record<string, ProjectState>) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(states));
  } catch { /* quota exceeded - ignore */ }
}

function loadProjectState(id: string): ProjectState {
  const all = loadAllStates();
  return all[id] || { maxIter: 30, events: [] };
}

function saveProjectState(id: string, state: ProjectState) {
  const all = loadAllStates();
  all[id] = state;
  saveAllStates(all);
}

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------
export default function Dashboard() {
  const { t } = useI18n();
  const { status: treeOpStatus, showStatus: showTreeStatus } = useInlineStatus();
  const [projects, setProjects] = useState<string[]>([]);
  const [projectTree, setProjectTree] = useState<ProjectNode[]>([]);
  const [activeProject, setActiveProject] = useState<string | null>(null);
  const [runStatus, setRunStatus] = useState<RunStatus | null>(null);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [events, setEvents] = useState<OrchestratorEvent[]>([]);
  const [maxIter, setMaxIter] = useState(30);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [rightTab, setRightTab] = useState<"timeline" | "agents" | "models" | "tasks">("timeline");
  const [allRunStatuses, setAllRunStatuses] = useState<Record<string, string>>({});
  const [planUsage, setPlanUsage] = useState<{ projects: number; max_projects: number; plan: string } | null>(null);

  // --- refs for latest state (avoid stale closures in callbacks) ---
  const activeProjectRef = useRef(activeProject);
  const maxIterRef = useRef(maxIter);
  const eventsRef = useRef(events);
  activeProjectRef.current = activeProject;
  maxIterRef.current = maxIter;
  eventsRef.current = events;

  // --- load / save per-project state on switch ---
  const switchProject = useCallback(
    (id: string) => {
      // Save current project state before switching
      if (activeProjectRef.current) {
        saveProjectState(activeProjectRef.current, { maxIter: maxIterRef.current, events: eventsRef.current });
      }
      // Load new project state
      const saved = loadProjectState(id);
      setMaxIter(saved.maxIter);
      setEvents(saved.events);
      setActiveProject(id);
    },
    [],
  );

  // Persist on unmount / tab close
  useEffect(() => {
    const handleUnload = () => {
      if (activeProjectRef.current) {
        saveProjectState(activeProjectRef.current, { maxIter: maxIterRef.current, events: eventsRef.current });
      }
    };
    window.addEventListener("beforeunload", handleUnload);
    return () => window.removeEventListener("beforeunload", handleUnload);
  }, []);

  // Get goal from project config (saved by ProjectDetail)
  const activeNode = projectTree.find((n) => n.project_id === activeProject);
  const activeGoal = activeNode?.goal || "";
  const activeAgentProfiles: Record<string, AgentProfileAssignment> = activeNode?.agent_profiles || {};

  // --- data fetching ---
  const loadProjects = useCallback(async () => {
    try {
      const data = await api.listProjects();
      setProjects(data.projects);
      setProjectTree(data.tree || []);
      if (data.usage) {
        setPlanUsage({
          projects: data.usage.projects,
          max_projects: data.usage.max_projects,
          plan: data.plan?.display_name || data.plan?.plan || "Free",
        });
      }
    } catch { /* API not available */ }
  }, []);

  const loadRunStatus = useCallback(async () => {
    if (!activeProject) return;
    try {
      const status = await api.getRunStatus(activeProject);
      setRunStatus(status);
    } catch {
      setRunStatus(null);
    }
  }, [activeProject]);

  const loadAgents = useCallback(async () => {
    if (!activeProject) return;
    try {
      const data = await api.listAgents(activeProject);
      setAgents(data.agents);
    } catch {
      setAgents([]);
    }
  }, [activeProject]);

  // Poll all run statuses for the project tree
  const loadAllRunStatuses = useCallback(async () => {
    try {
      const data = await api.listRuns();
      const statuses: Record<string, string> = {};
      for (const [pid, info] of Object.entries(data.runs as Record<string, { status: string }>)) {
        statuses[pid] = info.status;
      }
      setAllRunStatuses(statuses);
    } catch { /* ignore */ }
  }, []);

  const handleSendOrder = useCallback(async (order: string) => {
    if (!activeProject) return;
    await api.updateProjectConfig(activeProject, { additional_order: order });
  }, [activeProject]);

  useEffect(() => {
    loadProjects();
    loadAllRunStatuses();
    const interval = setInterval(() => {
      loadProjects();
      loadAllRunStatuses();
    }, 5000);
    return () => clearInterval(interval);
  }, [loadProjects, loadAllRunStatuses]);

  useEffect(() => {
    if (!activeProject) return;
    loadRunStatus();
    loadAgents();
    const interval = setInterval(() => {
      loadRunStatus();
      loadAgents();
    }, 3000);
    return () => clearInterval(interval);
  }, [activeProject, loadRunStatus, loadAgents]);

  // WebSocket for real-time events
  useEffect(() => {
    if (!activeProject) return;
    let ws: WebSocket | null = null;
    let closed = false;
    try {
      ws = api.connectWebSocket(activeProject, (data) => {
        if (!closed) {
          setEvents((prev) => [...prev.slice(-200), data as OrchestratorEvent]);
        }
      });
    } catch { /* WebSocket not available */ }
    return () => {
      closed = true;
      if (ws) {
        try { ws.close(); } catch { /* already closed */ }
      }
    };
  }, [activeProject]);

  return (
    <div className={`app-layout ${sidebarOpen ? "" : "sidebar-is-collapsed"}`}>
      {/* ---- Left sidebar: Project Tree ---- */}
      <aside className={`sidebar ${sidebarOpen ? "" : "sidebar-collapsed"}`}>
        <div className="sidebar-header">
          <span className="sidebar-logo">MADO</span>
          <button
            className="sidebar-toggle"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            title={sidebarOpen ? t("collapse") : t("expand")}
          >
            {sidebarOpen ? "\u25C0" : "\u25B6"}
          </button>
        </div>
        {sidebarOpen && (
          <>
          <ProjectTree
            projectTree={projectTree}
            activeProject={activeProject}
            onSelect={switchProject}
            onRefresh={loadProjects}
            runStatuses={allRunStatuses}
            planUsage={planUsage}
            onStartRun={async (pid) => {
              const node = projectTree.find((n) => n.project_id === pid);
              const configGoal = node?.goal || "";
              const st = loadProjectState(pid);
              showTreeStatus(`「${node?.display_name || pid}」を実行準備中...`, "info");
              try {
                await api.startRun(pid, configGoal, st.maxIter || maxIter);
                loadAllRunStatuses();
                if (pid === activeProject) loadRunStatus();
                showTreeStatus(`「${node?.display_name || pid}」の実行を開始`, "success");
              } catch (e) {
                showTreeStatus(`実行エラー: ${e instanceof Error ? e.message : String(e)}`, "error");
              }
            }}
            onStopRun={async (pid) => {
              try {
                await api.stopRun(pid);
                loadAllRunStatuses();
                if (pid === activeProject) loadRunStatus();
                showTreeStatus("実行を停止しました", "success");
              } catch (e) {
                showTreeStatus(`停止エラー: ${e instanceof Error ? e.message : String(e)}`, "error");
              }
            }}
            onPauseRun={async (pid) => {
              try {
                await api.pauseRun(pid);
                loadAllRunStatuses();
                if (pid === activeProject) loadRunStatus();
                showTreeStatus("一時停止しました", "success");
              } catch (e) {
                showTreeStatus(`一時停止エラー: ${e instanceof Error ? e.message : String(e)}`, "error");
              }
            }}
          />
          {treeOpStatus && (
            <div className="tree-inline-status">
              <StatusIndicator status={treeOpStatus} />
            </div>
          )}
          </>
        )}
      </aside>

      {/* ---- Main area: Agent Grid (web conference style) ---- */}
      <main className="main-area">
        <div className="main-topbar">
          <RunControl
            activeProject={activeProject}
            runStatus={runStatus}
            onRefresh={loadRunStatus}
            goal={activeGoal}
            maxIter={maxIter}
            onMaxIterChange={setMaxIter}
            onExtendIterations={(extra) => {
              if (!activeProject) return;
              api.startRun(activeProject, activeGoal.trim(), extra).then(loadRunStatus).catch(() => {});
            }}
          />
        </div>
        <ProjectDetail
          activeProject={activeProject}
          projectTree={projectTree}
          onRefresh={loadProjects}
          allRunStatuses={allRunStatuses}
          onDispatchChild={async (parentId, childId, instruction) => {
            await api.dispatchChild(parentId, childId, instruction);
            loadAllRunStatuses();
          }}
          onStopChild={async (childId) => {
            await api.stopRun(childId);
            loadAllRunStatuses();
          }}
          onDispatchAll={async (parentId) => {
            await api.dispatchAllChildren(parentId);
            loadAllRunStatuses();
          }}
        />
        <ErrorBoundary>
          <AgentTerminalGrid
            events={events}
            agentProfiles={activeAgentProfiles}
            activeProject={activeProject}
            onSendOrder={handleSendOrder}
          />
        </ErrorBoundary>
      </main>

      {/* ---- Right panel: Tabs (Timeline / Models / Tasks) ---- */}
      <aside className="right-panel">
        <div className="right-tabs">
          <button
            className={`right-tab ${rightTab === "timeline" ? "right-tab-active" : ""}`}
            onClick={() => setRightTab("timeline")}
          >
            {t("timeline")}
          </button>
          <button
            className={`right-tab ${rightTab === "agents" ? "right-tab-active" : ""}`}
            onClick={() => setRightTab("agents")}
          >
            {t("agentsTab")}
          </button>
          <button
            className={`right-tab ${rightTab === "tasks" ? "right-tab-active" : ""}`}
            onClick={() => setRightTab("tasks")}
          >
            {t("tasks")}
          </button>
          <LangSwitcher />
        </div>
        <div className="right-content">
          {rightTab === "timeline" && <ErrorBoundary><Timeline events={events} /></ErrorBoundary>}
          {rightTab === "agents" && (
            <ErrorBoundary>
              <ModelPanel
                activeProject={activeProject}
                agentProfiles={activeAgentProfiles}
                onProfilesChange={async (profiles) => {
                  if (!activeProject) return;
                  try {
                    await api.updateProjectConfig(activeProject, { agent_profiles: profiles });
                    loadProjects();
                  } catch { /* ignore */ }
                }}
              />
              <AgentPanel
                activeProject={activeProject}
                agentProfiles={activeAgentProfiles}
                runtimeAgents={agents}
                onProfilesChanged={loadProjects}
              />
            </ErrorBoundary>
          )}
          {rightTab === "tasks" && <ErrorBoundary><TaskGraph runStatus={runStatus} events={events} /></ErrorBoundary>}
        </div>
      </aside>
    </div>
  );
}
