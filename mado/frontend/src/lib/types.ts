/** Shared type definitions for MADO frontend. */

/** A node in the project tree returned by listProjects(). */
export interface ProjectNode {
  project_id: string;
  display_name?: string;
  parent_id: string | null;
  children: string[];
  status: string;
  goal?: string;
  overview?: string;
  policy?: string;
  roadmap?: string;
  description?: string;
  agent_profiles?: Record<string, AgentProfile>;
}

/** Agent profile stored in project config. */
export interface AgentProfile {
  title: string;
  personality: string;
}

/** Run status returned by getRunStatus(). */
export interface RunStatus {
  status: "idle" | "running" | "completed" | "error" | "paused";
  iteration: number;
  max_iterations: number;
  project_id?: string;
  goal?: string;
  error?: string;
}

/** Runtime agent info returned by listAgents(). */
export interface AgentInfo {
  role: string;
  status: string;
  model?: string;
  last_activity?: string;
}

/** WebSocket / orchestrator event. */
export interface OrchestratorEvent {
  type: string;
  timestamp?: string;
  role?: string;
  message?: string;
  iteration?: number;
  detail?: string;
  [key: string]: unknown;
}
