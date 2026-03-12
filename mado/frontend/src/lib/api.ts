const API_BASE = "/api";

async function fetchJSON(path: string, options?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || res.statusText);
  }
  return res.json();
}

// Projects
export const listProjects = () => fetchJSON("/projects/");
export const getProjectsRoot = () => fetchJSON("/projects/settings/root");
export const setProjectsRoot = (projects_root: string) =>
  fetchJSON("/projects/settings/root", { method: "PUT", body: JSON.stringify({ projects_root }) });
export const createProject = (project_id: string, goal: string, parent_id?: string) =>
  fetchJSON("/projects/", { method: "POST", body: JSON.stringify({ project_id, goal, parent_id }) });
export const getProject = (id: string) => fetchJSON(`/projects/${id}`);
export const renameProject = (id: string, new_id: string) =>
  fetchJSON(`/projects/${id}/rename`, { method: "PUT", body: JSON.stringify({ new_id }) });
export const deleteProject = (id: string) => fetchJSON(`/projects/${id}`, { method: "DELETE" });
export const moveProject = (id: string, new_parent_id: string | null) =>
  fetchJSON(`/projects/${id}/move`, { method: "PUT", body: JSON.stringify({ new_parent_id }) });
export const reorderProjects = (order: string[], parent_id?: string | null) =>
  fetchJSON("/projects/reorder", { method: "PUT", body: JSON.stringify({ order, parent_id: parent_id || null }) });
export const getProjectMemory = (id: string) => fetchJSON(`/projects/${id}/memory`);
export const getProjectFiles = (id: string) => fetchJSON(`/projects/${id}/files`);
export const listChildren = (id: string) => fetchJSON(`/projects/${id}/children`);
export const getProjectProgress = (id: string) => fetchJSON(`/projects/${id}/progress`);
export const updateProjectConfig = (id: string, updates: Record<string, any>) =>
  fetchJSON(`/projects/${id}/config`, { method: "PUT", body: JSON.stringify(updates) });
export const listBackups = (id: string) => fetchJSON(`/projects/${id}/backups`);
export const restoreBackup = (id: string, backup_name: string) =>
  fetchJSON(`/projects/${id}/backups/restore`, { method: "POST", body: JSON.stringify({ backup_name }) });

// Agents
export const listAgents = (projectId: string) => fetchJSON(`/agents/${projectId}`);
export const getAgent = (projectId: string, role: string) => fetchJSON(`/agents/${projectId}/${role}`);

// Models
export const listModels = () => fetchJSON("/models/");
export const getAssignments = () => fetchJSON("/models/assignments");
export const switchModel = (role: string, new_model: string) =>
  fetchJSON("/models/switch", { method: "PUT", body: JSON.stringify({ role, new_model }) });
export const reorderRoles = (roles: string[]) =>
  fetchJSON("/models/reorder", { method: "PUT", body: JSON.stringify({ roles }) });
export const reloadModels = () => fetchJSON("/models/reload", { method: "POST" });

// Orchestrator
export const startRun = (project_id: string, goal: string, max_iterations?: number) =>
  fetchJSON("/orchestrator/run", {
    method: "POST",
    body: JSON.stringify({ project_id, goal, max_iterations }),
  });
export const getRunStatus = (projectId: string) => fetchJSON(`/orchestrator/run/${projectId}`);
export const stopRun = (projectId: string) =>
  fetchJSON(`/orchestrator/run/${projectId}/stop`, { method: "POST" });
export const listRuns = () => fetchJSON("/orchestrator/runs");
export const dispatchChild = (parent_id: string, child_id: string, instruction?: string) =>
  fetchJSON("/orchestrator/dispatch-child", {
    method: "POST",
    body: JSON.stringify({ parent_id, child_id, instruction }),
  });
export const dispatchAllChildren = (parent_id: string) =>
  fetchJSON("/orchestrator/dispatch-children", {
    method: "POST",
    body: JSON.stringify({ parent_id }),
  });

// Orchestrator - pause
export const pauseRun = (projectId: string) =>
  fetchJSON(`/orchestrator/run/${projectId}/pause`, { method: "POST" });

// OpenClaw
export const checkOpenClaw = () => fetchJSON("/openclaw/status");
export const installOpenClaw = () => fetchJSON("/openclaw/install", { method: "POST" });

// WebSocket
export function connectWebSocket(projectId: string, onMessage: (data: any) => void): WebSocket {
  const ws = new WebSocket(`ws://localhost:8000/api/ws/${projectId}`);
  ws.onmessage = (event) => onMessage(JSON.parse(event.data));
  return ws;
}
