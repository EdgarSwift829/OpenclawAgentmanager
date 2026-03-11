"use client";

import { useState, useEffect, useCallback } from "react";
import * as api from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { ProjectTree } from "@/components/ProjectTree";
import { AgentGrid } from "@/components/AgentGrid";
import { RunControl } from "@/components/RunControl";
import { Timeline } from "@/components/Timeline";
import { ModelPanel } from "@/components/ModelPanel";
import { TaskGraph } from "@/components/TaskGraph";
import { LangSwitcher } from "@/components/LangSwitcher";

// ---------------------------------------------------------------------------
// localStorage persistence for per-project state
// ---------------------------------------------------------------------------
const STORAGE_KEY = "mado_project_states";

interface ProjectState {
  goal: string;
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
  return all[id] || { goal: "", maxIter: 10, events: [] };
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
  const [projects, setProjects] = useState<string[]>([]);
  const [activeProject, setActiveProject] = useState<string | null>(null);
  const [runStatus, setRunStatus] = useState<any>(null);
  const [agents, setAgents] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [goal, setGoal] = useState("");
  const [maxIter, setMaxIter] = useState(10);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [rightTab, setRightTab] = useState<"timeline" | "models" | "tasks">("timeline");

  // --- load / save per-project state on switch ---
  const switchProject = useCallback(
    (id: string) => {
      // Save current project state before switching
      if (activeProject) {
        saveProjectState(activeProject, { goal, maxIter, events });
      }
      // Load new project state
      const saved = loadProjectState(id);
      setGoal(saved.goal);
      setMaxIter(saved.maxIter);
      setEvents(saved.events);
      setActiveProject(id);
    },
    [activeProject, goal, maxIter, events],
  );

  // Persist on unmount / tab close
  useEffect(() => {
    const handleUnload = () => {
      if (activeProject) {
        saveProjectState(activeProject, { goal, maxIter, events });
      }
    };
    window.addEventListener("beforeunload", handleUnload);
    return () => window.removeEventListener("beforeunload", handleUnload);
  }, [activeProject, goal, maxIter, events]);

  // --- data fetching ---
  const loadProjects = useCallback(async () => {
    try {
      const data = await api.listProjects();
      setProjects(data.projects);
    } catch { /* API may not be running */ }
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

  useEffect(() => {
    loadProjects();
    const interval = setInterval(loadProjects, 10000);
    return () => clearInterval(interval);
  }, [loadProjects]);

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
          <ProjectTree
            projects={projects}
            activeProject={activeProject}
            onSelect={switchProject}
            onRefresh={loadProjects}
          />
        )}
      </aside>

      {/* ---- Main area: Agent Grid (web conference style) ---- */}
      <main className="main-area">
        <div className="main-topbar">
          <RunControl
            activeProject={activeProject}
            runStatus={runStatus}
            onRefresh={loadRunStatus}
            goal={goal}
            onGoalChange={setGoal}
            maxIter={maxIter}
            onMaxIterChange={setMaxIter}
          />
        </div>
        <AgentGrid agents={agents} events={events} />
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
          {rightTab === "models" && <ModelPanel />}
          {rightTab === "tasks" && <TaskGraph runStatus={runStatus} />}
        </div>
      </aside>
    </div>
  );
}
