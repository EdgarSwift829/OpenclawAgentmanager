/** Shared type definitions for MADO frontend. */

/** Task item within a project. */
export interface TaskItem {
  id: string;
  title: string;
  description: string;
  status: string;
  deadline: string;
  priority: string;
}

/** A node in the project tree returned by listProjects(). */
export interface ProjectNode {
  project_id: string;
  display_name?: string;
  mode?: "orchestration" | "app";
  parent_id: string | null;
  children: string[];
  status: string;
  goal: string;
  overview: string;
  policy: string;
  roadmap: string;
  description: string;
  deadline: string | null;
  tasks: TaskItem[];
  rules_must?: string;
  rules_forbidden?: string;
  agent_profiles?: Record<string, AgentProfileAssignment>;
  app_tasks?: AppTaskDef[];
}

/** App-mode task definition. */
export interface AppTaskDef {
  task_id: string;
  title: string;
  prompt: string;
  schedule_type: "manual" | "interval" | "cron";
  interval_minutes: number;
  cron_expr: string;
  deadline: string | null;
  enabled: boolean;
  last_run: string | null;
  next_run: string | null;
}

/** App-mode task execution record. */
export interface AppTaskExecution {
  execution_id: string;
  task_id: string;
  project_id: string;
  started_at: string;
  finished_at: string | null;
  status: "running" | "completed" | "error";
  result: string | null;
  error: string | null;
}

/** Agent profile assignment stored in project config (per-role). */
export interface AgentProfileAssignment {
  profile_id?: string;
  additional_prompt?: string;
}

/** Legacy agent profile format (backward compatibility). */
export interface AgentProfile {
  title?: string;
  personality?: string;
  profile_id?: string;
  additional_prompt?: string;
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
  // Task-related fields
  task_id?: string;
  task?: string;
  tasks?: Array<{ id: string; role: string; desc: string }>;
  // Review fields
  approved?: boolean;
  feedback?: string;
  score?: number | string;
  issues?: Array<{ severity: string; description: string }>;
  // Run fields
  goal?: string;
  agents?: string[];
  error?: string;
  summary?: string;
  files_modified?: string[];
  // DAG fields
  layers?: number;
  total_tasks?: number;
  task_count?: number;
  layer?: number;
  // Agent activity
  activity?: string;
  sender?: string;
  timeout?: number;
  reason?: string;
  plan_summary?: string;
  // Run completion
  iterations?: number;
  elapsed_seconds?: number;
  total_results?: number;
}
