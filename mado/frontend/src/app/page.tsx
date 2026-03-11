"use client";

import { useState, useEffect, useCallback } from "react";
import * as api from "@/lib/api";
import { TaskGraph } from "@/components/TaskGraph";
import { AgentActivity } from "@/components/AgentActivity";
import { Timeline } from "@/components/Timeline";
import { ProjectPanel } from "@/components/ProjectPanel";
import { ModelPanel } from "@/components/ModelPanel";
import { RunControl } from "@/components/RunControl";

export default function Dashboard() {
  const [projects, setProjects] = useState<string[]>([]);
  const [activeProject, setActiveProject] = useState<string | null>(null);
  const [runStatus, setRunStatus] = useState<any>(null);
  const [agents, setAgents] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);

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
    <div className="container">
      <div className="header">
        <h1>MADO - Multi-Agent Dev Orchestrator</h1>
        <span className="badge badge-idle">v0.1.0</span>
      </div>

      <div className="grid grid-3" style={{ marginBottom: "1rem" }}>
        <ProjectPanel
          projects={projects}
          activeProject={activeProject}
          onSelect={setActiveProject}
          onRefresh={loadProjects}
        />
        <RunControl
          activeProject={activeProject}
          runStatus={runStatus}
          onRefresh={loadRunStatus}
        />
        <ModelPanel />
      </div>

      {activeProject && (
        <div className="grid grid-3">
          <TaskGraph runStatus={runStatus} />
          <AgentActivity agents={agents} />
          <Timeline events={events} />
        </div>
      )}
    </div>
  );
}
