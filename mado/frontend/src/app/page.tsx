"use client";

import { useState, useEffect, useCallback } from "react";
import * as api from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useInlineStatus, StatusIndicator } from "@/components/Toast";
import { ProjectTree } from "@/components/ProjectTree";
import { AgentGrid } from "@/components/AgentGrid";
import { RunControl } from "@/components/RunControl";
import { Timeline } from "@/components/Timeline";
import { ModelPanel } from "@/components/ModelPanel";
import { TaskGraph } from "@/components/TaskGraph";
import { ProjectDetail } from "@/components/ProjectDetail";
import { LangSwitcher } from "@/components/LangSwitcher";

// ---------------------------------------------------------------------------
// localStorage persistence for per-project state
// ---------------------------------------------------------------------------
const STORAGE_KEY = "mado_project_states";

interface ProjectState {
  maxIter: number;
  events: any[];
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
  const [projectTree, setProjectTree] = useState<any[]>([]);
  const [activeProject, setActiveProject] = useState<string | null>(null);
  const [runStatus, setRunStatus] = useState<any>(null);
  const [agents, setAgents] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [maxIter, setMaxIter] = useState(30);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [rightTab, setRightTab] = useState<"timeline" | "models" | "tasks">("timeline");
  const [allRunStatuses, setAllRunStatuses] = useState<Record<string, string>>({});

  // --- load / save per-project state on switch ---
  const switchProject = useCallback(
    (id: string) => {
      // Save current project state before switching
      if (activeProject) {
        saveProjectState(activeProject, { maxIter, events });
      }
      // Load new project state
      const saved = loadProjectState(id);
      setMaxIter(saved.maxIter);
      setEvents(saved.events);
      setActiveProject(id);
    },
    [activeProject, maxIter, events],
  );

  // Persist on unmount / tab close
  useEffect(() => {
    const handleUnload = () => {
      if (activeProject) {
        saveProjectState(activeProject, { maxIter, events });
      }
    };
    window.addEventListener("beforeunload", handleUnload);
    return () => window.removeEventListener("beforeunload", handleUnload);
  }, [activeProject, maxIter, events]);

  // Get goal from project config (saved by ProjectDetail)
  const activeNode = projectTree.find((n: any) => n.project_id === activeProject);
  const activeGoal = activeNode?.goal || "";
  const activeAgentProfiles = activeNode?.agent_profiles || {};

  // --- data fetching ---
  const loadProjects = useCallback(async () => {
    try {
      const data = await api.listProjects();
      setProjects(data.projects);
      setProjectTree(data.tree || []);
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
      for (const [pid, info] of Object.entries(data.runs as Record<string, any>)) {
        statuses[pid] = info.status;
      }
      setAllRunStatuses(statuses);
    } catch { /* ignore */ }
  }, []);

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
    let ws: WebSocket;
    try {
      ws = api.connectWebSocket(activeProject, (data) => {
        setEvents((prev) => [...prev.slice(-200), data]);
      });
    } catch { /* WebSocket not available */ }
    return () => ws?.close();
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
            onStartRun={async (pid) => {
              const node = projectTree.find((n: any) => n.project_id === pid);
              const configGoal = node?.goal || "";
              const st = loadProjectState(pid);
              showTreeStatus(`「${node?.display_name || pid}」を実行準備中...`, "info");
              try {
                await api.startRun(pid, configGoal, st.maxIter || maxIter);
                loadAllRunStatuses();
                if (pid === activeProject) loadRunStatus();
                showTreeStatus(`「${node?.display_name || pid}」の実行を開始`, "success");
              } catch (e: any) {
                showTreeStatus(`実行エラー: ${e.message}`, "error");
              }
            }}
            onStopRun={async (pid) => {
              try {
                await api.stopRun(pid);
                loadAllRunStatuses();
                if (pid === activeProject) loadRunStatus();
                showTreeStatus("実行を停止しました", "success");
              } catch (e: any) {
                showTreeStatus(`停止エラー: ${e.message}`, "error");
              }
            }}
            onPauseRun={async (pid) => {
              try {
                await api.pauseRun(pid);
                loadAllRunStatuses();
                if (pid === activeProject) loadRunStatus();
                showTreeStatus("一時停止しました", "success");
              } catch (e: any) {
                showTreeStatus(`一時停止エラー: ${e.message}`, "error");
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
        />
        <AgentGrid agents={agents} events={events} agentProfiles={activeAgentProfiles} />
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
            className={`right-tab ${rightTab === "models" ? "right-tab-active" : ""}`}
            onClick={() => setRightTab("models")}
          >
            {t("models")}
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
          {rightTab === "timeline" && <Timeline events={events} />}
          {rightTab === "models" && (
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
          )}
          {rightTab === "tasks" && <TaskGraph runStatus={runStatus} />}
        </div>
      </aside>
    </div>
  );
}
