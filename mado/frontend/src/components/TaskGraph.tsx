"use client";

interface Props {
  runStatus: any;
}

interface TaskNode {
  name: string;
  status: "pending" | "running" | "completed" | "error";
}

export function TaskGraph({ runStatus }: Props) {
  const tasks: TaskNode[] = buildTasks(runStatus);

  return (
    <div className="card">
      <h2>Task Graph</h2>
      <div className="task-graph">
        {tasks.length === 0 ? (
          <span style={{ color: "var(--text-secondary)", fontSize: "0.8125rem" }}>
            No active tasks
          </span>
        ) : (
          tasks.map((task, i) => (
            <div key={i} className={`task-node ${task.status}`}>
              <span>{task.name}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function buildTasks(runStatus: any): TaskNode[] {
  if (!runStatus) return [];

  const iteration = runStatus.iteration || 0;
  const maxIter = runStatus.max_iterations || 10;
  const status = runStatus.status || "idle";

  const phases = [
    { name: "CTO Planning", step: 1 },
    { name: "Task Decomposition", step: 2 },
    { name: "Research", step: 3 },
    { name: "Implementation", step: 4 },
    { name: "Code Review", step: 5 },
    { name: "Testing", step: 6 },
  ];

  if (status === "completed") {
    return phases.map((p) => ({ name: p.name, status: "completed" as const }));
  }
  if (status === "error") {
    return phases.map((p, i) => ({
      name: p.name,
      status: i === 0 ? ("error" as const) : ("pending" as const),
    }));
  }

  // Estimate current phase based on iteration progress
  const progress = Math.min(iteration / Math.max(maxIter, 1), 1);
  const currentStep = Math.floor(progress * phases.length);

  return phases.map((p, i) => ({
    name: `${p.name}${i === currentStep && status === "running" ? ` (iter ${iteration})` : ""}`,
    status:
      i < currentStep ? ("completed" as const) :
      i === currentStep && status === "running" ? ("running" as const) :
      ("pending" as const),
  }));
}
