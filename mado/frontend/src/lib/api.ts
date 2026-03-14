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

// Agent Profiles (global, cross-project)
export const listAllProfiles = () => fetchJSON("/profiles/");
export const listRoleProfiles = (role: string) => fetchJSON(`/profiles/${role}`);
export const createProfile = (role: string, name: string, additional_prompt: string, clone_from?: string) =>
  fetchJSON(`/profiles/${role}`, {
    method: "POST",
    body: JSON.stringify({ name, additional_prompt, clone_from: clone_from || null }),
  });
export const updateProfile = (role: string, profileId: string, updates: { name?: string; additional_prompt?: string }) =>
  fetchJSON(`/profiles/${role}/${profileId}`, { method: "PUT", body: JSON.stringify(updates) });
export const deleteProfile = (role: string, profileId: string) =>
  fetchJSON(`/profiles/${role}/${profileId}`, { method: "DELETE" });

// Models
export const listModels = () => fetchJSON("/models/");
export const getAssignments = () => fetchJSON("/models/assignments");
export const switchModel = (role: string, new_model: string) =>
  fetchJSON("/models/switch", { method: "PUT", body: JSON.stringify({ role, new_model }) });
export const reorderRoles = (roles: string[]) =>
  fetchJSON("/models/reorder", { method: "PUT", body: JSON.stringify({ roles }) });
export const addRole = (role: string, model: string) =>
  fetchJSON(`/models/assignments/${role}`, { method: "POST", body: JSON.stringify({ model }) });
export const removeRole = (role: string) =>
  fetchJSON(`/models/assignments/${role}`, { method: "DELETE" });
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

// WebSocket with auto-reconnect
export function connectWebSocket(
  projectId: string,
  onMessage: (data: unknown) => void,
): WebSocket {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = window.location.host;
  const encodedId = encodeURIComponent(projectId);
  const url = `${protocol}//${host}/api/ws/${encodedId}`;

  let reconnectDelay = 1000;
  const MAX_RECONNECT_DELAY = 30000;
  let stopped = false;

  function create(): WebSocket {
    const ws = new WebSocket(url);
    ws.onmessage = (event) => onMessage(JSON.parse(event.data));
    ws.onopen = () => {
      reconnectDelay = 1000; // reset on successful connect
    };
    ws.onclose = (event) => {
      if (stopped || event.code === 1000) return; // normal close — don't reconnect
      setTimeout(() => {
        if (!stopped) create();
      }, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT_DELAY);
    };
    // Expose a way to permanently close from the outside
    const origClose = ws.close.bind(ws);
    ws.close = (code?: number, reason?: string) => {
      stopped = true;
      origClose(code, reason);
    };
    return ws;
  }

  return create();
}
