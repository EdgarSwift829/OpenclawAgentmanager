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
export const createProject = (project_id: string, goal: string) =>
  fetchJSON("/projects/", { method: "POST", body: JSON.stringify({ project_id, goal }) });
export const getProject = (id: string) => fetchJSON(`/projects/${id}`);
export const deleteProject = (id: string) => fetchJSON(`/projects/${id}`, { method: "DELETE" });
export const getProjectMemory = (id: string) => fetchJSON(`/projects/${id}/memory`);
export const getProjectFiles = (id: string) => fetchJSON(`/projects/${id}/files`);

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

// WebSocket
export function connectWebSocket(projectId: string, onMessage: (data: any) => void): WebSocket {
  const ws = new WebSocket(`ws://localhost:8000/api/ws/${projectId}`);
  ws.onmessage = (event) => onMessage(JSON.parse(event.data));
  return ws;
}
