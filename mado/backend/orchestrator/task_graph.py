"""TaskGraph - DAG-based task dependency management and execution ordering.

Represents tasks as a directed acyclic graph where edges indicate dependencies.
Provides topological sort for execution order and identifies parallelizable groups.
"""

from collections import defaultdict
from typing import Optional


class TaskGraph:
    """Directed Acyclic Graph for task dependency resolution.

    Each task is identified by a unique task_id.
    Tasks can declare dependencies via 'depends_on' (list of task_ids).
    The graph produces execution layers: each layer contains tasks
    that can be run in parallel because all their dependencies are satisfied.

    Usage:
        graph = TaskGraph()
        graph.add_tasks([
            {"task_id": "design", "assigned_to": "cto", "description": "..."},
            {"task_id": "impl", "assigned_to": "engineer", "depends_on": ["design"]},
            {"task_id": "test", "assigned_to": "tester", "depends_on": ["impl"]},
            {"task_id": "docs", "assigned_to": "documenter", "depends_on": ["design"]},
        ])
        layers = graph.get_execution_layers()
        # layers = [
        #   [design],          # Layer 0: no deps, run first
        #   [impl, docs],      # Layer 1: both depend only on design
        #   [test],            # Layer 2: depends on impl
        # ]
    """

    def __init__(self):
        self._tasks: dict[str, dict] = {}
        self._dependencies: dict[str, list[str]] = defaultdict(list)
        self._dependents: dict[str, list[str]] = defaultdict(list)

    def add_task(self, task: dict) -> None:
        """Add a single task to the graph.

        Task must have 'task_id'. Optional 'depends_on' is a list of task_ids.
        """
        task_id = task.get("task_id")
        if not task_id:
            # Auto-generate task_id from assigned_to + index
            task_id = f"{task.get('assigned_to', 'task')}_{len(self._tasks)}"
            task["task_id"] = task_id

        self._tasks[task_id] = task
        deps = task.get("depends_on", [])
        if isinstance(deps, str):
            deps = [deps]
        self._dependencies[task_id] = deps
        for dep in deps:
            self._dependents[dep].append(task_id)

    def add_tasks(self, tasks: list[dict]) -> None:
        """Add multiple tasks to the graph."""
        for task in tasks:
            self.add_task(task)

    def validate(self) -> list[str]:
        """Validate the graph. Returns list of errors (empty = valid).

        Checks:
        - No missing dependencies (referencing non-existent tasks)
        - No circular dependencies
        """
        errors = []

        # Check for missing deps
        for task_id, deps in self._dependencies.items():
            for dep in deps:
                if dep not in self._tasks:
                    errors.append(f"Task '{task_id}' depends on unknown task '{dep}'")

        # Check for cycles via DFS
        if not errors:
            cycle = self._detect_cycle()
            if cycle:
                errors.append(f"Circular dependency detected: {' -> '.join(cycle)}")

        return errors

    def _detect_cycle(self) -> Optional[list[str]]:
        """Detect cycles using DFS. Returns cycle path or None."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {tid: WHITE for tid in self._tasks}
        path = []

        def dfs(node):
            color[node] = GRAY
            path.append(node)
            for dep_of in self._dependents.get(node, []):
                if dep_of not in color:
                    continue
                if color[dep_of] == GRAY:
                    cycle_start = path.index(dep_of)
                    return path[cycle_start:] + [dep_of]
                if color[dep_of] == WHITE:
                    result = dfs(dep_of)
                    if result:
                        return result
            color[node] = BLACK
            path.pop()
            return None

        for task_id in self._tasks:
            if color[task_id] == WHITE:
                result = dfs(task_id)
                if result:
                    return result
        return None

    def get_execution_layers(self) -> list[list[dict]]:
        """Compute execution layers via topological sort (Kahn's algorithm).

        Returns a list of layers. Each layer is a list of tasks that can run in parallel.
        Tasks in layer N+1 depend on tasks in layer N or earlier.
        """
        errors = self.validate()
        if errors:
            raise ValueError(f"Invalid task graph: {'; '.join(errors)}")

        # Compute in-degree (only counting deps within the graph)
        in_degree = {tid: 0 for tid in self._tasks}
        for task_id, deps in self._dependencies.items():
            for dep in deps:
                if dep in self._tasks:
                    in_degree[task_id] += 1

        # Start with tasks that have no dependencies
        current_layer = [tid for tid, deg in in_degree.items() if deg == 0]
        layers = []

        while current_layer:
            layer_tasks = [self._tasks[tid] for tid in current_layer]
            layers.append(layer_tasks)

            next_layer = []
            for tid in current_layer:
                for dependent in self._dependents.get(tid, []):
                    if dependent in in_degree:
                        in_degree[dependent] -= 1
                        if in_degree[dependent] == 0:
                            next_layer.append(dependent)
            current_layer = next_layer

        return layers

    def get_task(self, task_id: str) -> Optional[dict]:
        return self._tasks.get(task_id)

    @property
    def task_count(self) -> int:
        return len(self._tasks)

    @property
    def task_ids(self) -> list[str]:
        return list(self._tasks.keys())
