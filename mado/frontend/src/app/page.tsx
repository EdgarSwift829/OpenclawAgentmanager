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
import { SetupWizard } from "@/components/SetupWizard";
import { LlmSettings } from "@/components/LlmSettings";
import { AppModeView } from "@/components/AppModeView";

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
  return all[id] || { maxIter: 200, events: [] };
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
  const [maxIter, setMaxIter] = useState(200);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [rightTab, setRightTab] = useState<"timeline" | "agents" | "models" | "tasks" | "llm">("timeline");
  const [allRunStatuses, setAllRunStatuses] = useState<Record<string, string>>({});
  const [planUsage, setPlanUsage] = useState<{ projects: number; max_projects: number; plan: string } | null>(null);

  // --- App mode proposal state ---
  const [appProposal, setAppProposal] = useState<{ parentId: string; parentName: string } | null>(null);
  const [appProposalName, setAppProposalName] = useState("");
  const [appProposalCreating, setAppProposalCreating] = useState(false);

  // --- API connection state ---
  const [apiConnected, setApiConnected] = useState(true);

  // --- Setup wizard state ---
  const [setupChecked, setSetupChecked] = useState(false);
  const [needsSetup, setNeedsSetup] = useState(false);

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
  const isAppMode = activeNode?.mode === "app";

  // --- data fetching ---
  const loadProjects = useCallback(async () => {
    try {
      const data = await api.listProjects();
      setProjects(data.projects);
      setProjectTree(data.tree || []);
      setApiConnected(true);
      if (data.usage) {
        setPlanUsage({
          projects: data.usage.projects,
          max_projects: data.usage.max_projects,
          plan: data.plan?.display_name || data.plan?.plan || "Free",
        });
      }
    } catch {
      setApiConnected(false);
    }
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

  // --- Check if initial setup is needed ---
  useEffect(() => {
    api.getSetupStatus()
      .then((res) => {
        setNeedsSetup(!res.initialized);
        setSetupChecked(true);
      })
      .catch(() => {
        // API not available yet, skip setup check
        setSetupChecked(true);
      });
  }, []);

  const handleSetupComplete = useCallback(() => {
    setNeedsSetup(false);
    // Reload projects after setup (demo project will be available)
    loadProjects().then(() => {
      // Auto-select first project after setup
      // (handled by the auto-select effect below)
    });
  }, [loadProjects]);

  useEffect(() => {
    if (needsSetup) return; // Don't poll while setup wizard is open
    loadProjects();
    loadAllRunStatuses();
    const interval = setInterval(() => {
      loadProjects();
      loadAllRunStatuses();
    }, 5000);
    return () => clearInterval(interval);
  }, [loadProjects, loadAllRunStatuses, needsSetup]);

  // Auto-select first project when none is active
  useEffect(() => {
    if (!activeProject && projectTree.length > 0) {
      switchProject(projectTree[0].project_id);
    }
  }, [activeProject, projectTree, switchProject]);

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

  // WebSocket for real-time events (with auto-reconnect)
  useEffect(() => {
    if (!activeProject) return;
    let closed = false;
    let ws: WebSocket | null = null;
    let retryCount = 0;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      if (closed) return;
      try {
        ws = api.connectWebSocket(activeProject, (data) => {
          if (!closed) {
            retryCount = 0; // reset on successful message
            setEvents((prev) => [...prev.slice(-200), data as OrchestratorEvent]);
          }
        });
        if (ws) {
          ws.addEventListener("close", () => {
            if (!closed && retryCount < 10) {
              const delay = Math.min(2000 * Math.pow(1.5, retryCount), 30000);
              retryCount++;
              retryTimer = setTimeout(connect, delay);
            }
          });
          ws.addEventListener("error", () => {
            // error fires before close, handled by close handler
          });
        }
      } catch { /* WebSocket not available */ }
    };

    connect();
    return () => {
      closed = true;
      if (retryTimer) clearTimeout(retryTimer);
      if (ws) {
        try { ws.close(); } catch { /* already closed */ }
      }
    };
  }, [activeProject]);

  // --- Detect orchestration completion → propose app-mode child ---
  const prevRunStatusRef = useRef<string | null>(null);
  useEffect(() => {
    if (!runStatus || !activeProject) return;
    const prev = prevRunStatusRef.current;
    prevRunStatusRef.current = runStatus.status;

    // Only trigger on transition from "running" to "completed"
    if (prev === "running" && runStatus.status === "completed") {
      const node = projectTree.find((n) => n.project_id === activeProject);
      if (!node || node.mode === "app") return; // skip if already app mode

      // Check if this project already has an app-mode child
      const hasAppChild = node.children.some((cid) => {
        const child = projectTree.find((n) => n.project_id === cid);
        return child?.mode === "app";
      });
      if (!hasAppChild) {
        setAppProposal({
          parentId: activeProject,
          parentName: node.display_name || activeProject,
        });
        setAppProposalName(`${node.display_name || activeProject}-app`);
      }
    }
  }, [runStatus, activeProject, projectTree]);

  const handleAppProposalCreate = async () => {
    if (!appProposal || !appProposalName.trim()) return;
    setAppProposalCreating(true);
    try {
      const result = await api.createProject(
        appProposalName.trim(),
        "",
        appProposal.parentId,
        "app",
      );
      const newId = result.project_id || appProposalName.trim();
      setAppProposal(null);
      setAppProposalName("");
      loadProjects();
      switchProject(newId);
    } catch { /* ignore */ }
    setAppProposalCreating(false);
  };

  // Global keyboard shortcuts: Ctrl+Enter to start run
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.key === "Enter") {
        const tag = (e.target as HTMLElement).tagName;
        if (tag === "TEXTAREA") return; // テキストエリア内のCtrl+Enterは無視
        e.preventDefault();
        if (activeProjectRef.current && activeGoal?.trim() && runStatus?.status !== "running") {
          api.startRun(activeProjectRef.current, activeGoal.trim(), maxIterRef.current)
            .then(() => loadRunStatus())
            .catch(() => {});
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeGoal, runStatus, loadRunStatus]);

  // Show loading while checking setup status
  if (!setupChecked) {
    return (
      <div className="app-loading">
        <div className="app-loading-spinner" />
        <span className="app-loading-text">MADO</span>
        <span className="app-loading-sub">Loading...</span>
      </div>
    );
  }
  if (needsSetup) {
    return <SetupWizard onComplete={handleSetupComplete} />;
  }

  return (
    <div className={`app-layout ${sidebarOpen ? "" : "sidebar-is-collapsed"}`}>
      {/* ---- API disconnected banner ---- */}
      {!apiConnected && (
        <div className="api-disconnected-banner" role="alert">
          <span className="api-disconnected-icon">{"\u26A0"}</span>
          <span>{t("apiDisconnected") || "バックエンドに接続できません。サーバーが起動しているか確認してください。"}</span>
        </div>
      )}
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

      {/* ---- Main area ---- */}
      <main className="main-area">
        {/* App-mode proposal banner */}
        {appProposal && (
          <div className="app-proposal-banner">
            <div className="app-proposal-content">
              <span className="app-proposal-icon">{"\u26A1"}</span>
              <div className="app-proposal-text">
                <strong>{t("appProposalTitle")}</strong>
                <span>{t("appProposalDesc")}</span>
              </div>
            </div>
            <div className="app-proposal-actions">
              <input
                className="app-proposal-input"
                value={appProposalName}
                onChange={(e) => setAppProposalName(e.target.value)}
                placeholder={t("appProposalNamePlaceholder")}
                onKeyDown={(e) => e.key === "Enter" && handleAppProposalCreate()}
              />
              <button
                className="btn btn-primary btn-sm"
                onClick={handleAppProposalCreate}
                disabled={appProposalCreating || !appProposalName.trim()}
              >
                {t("appProposalCreate")}
              </button>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => setAppProposal(null)}
              >
                {t("appProposalDismiss")}
              </button>
            </div>
          </div>
        )}

        {isAppMode && activeProject ? (
          /* App Mode: task automation view */
          <ErrorBoundary>
            <AppModeView projectId={activeProject} />
          </ErrorBoundary>
        ) : (
          /* Orchestration Mode: Agent Grid (web conference style) */
          <>
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
          </>
        )}
      </main>

      {/* ---- Right panel: Tabs (Timeline / Models / Tasks) ---- */}
      <aside className="right-panel">
        <div className="right-tabs">
          <button
            className={`right-tab ${rightTab === "timeline" ? "right-tab-active" : ""}`}
            onClick={() => setRightTab("timeline")}
            title={t("timeline")}
          >
            <span className="right-tab-icon">{"\u23F1"}</span>
            {t("timeline")}
          </button>
          <button
            className={`right-tab ${rightTab === "agents" ? "right-tab-active" : ""}`}
            onClick={() => setRightTab("agents")}
            title={t("agentsTab")}
          >
            <span className="right-tab-icon">{"\uD83E\uDDE0"}</span>
            {t("agentsTab")}
          </button>
          <button
            className={`right-tab ${rightTab === "tasks" ? "right-tab-active" : ""}`}
            onClick={() => setRightTab("tasks")}
            title={t("tasks")}
          >
            <span className="right-tab-icon">{"\u2611"}</span>
            {t("tasks")}
          </button>
          <button
            className={`right-tab ${rightTab === "llm" ? "right-tab-active" : ""}`}
            onClick={() => setRightTab("llm")}
            title={t("llmSettings")}
          >
            <span className="right-tab-icon">{"\u2699"}</span>
            {t("llmSettings")}
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
          {rightTab === "llm" && <ErrorBoundary><LlmSettings /></ErrorBoundary>}
        </div>
      </aside>
    </div>
  );
}
