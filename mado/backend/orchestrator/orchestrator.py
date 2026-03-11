"""Orchestrator - Main loop for multi-agent task execution with parallel support.

Lifecycle states:
  idle -> initializing -> running -> completed | cancelled | error
  Agent states: idle -> active -> done | error
"""

import asyncio
import logging
import time
from typing import Optional, Callable
from mado.backend.orchestrator.agent_factory import AgentFactory
from mado.backend.orchestrator.workspace_manager import WorkspaceManager
from mado.backend.orchestrator.message_bus import MessageBus, Message
from mado.backend.orchestrator.task_graph import TaskGraph
from mado.backend.models.model_manager import ModelManager

logger = logging.getLogger(__name__)


class AgentState:
    """Track individual agent lifecycle state."""

    def __init__(self, role: str):
        self.role = role
        self.status = "idle"  # idle | active | done | error
        self.tasks_completed = 0
        self.tasks_failed = 0
        self.last_active: Optional[float] = None
        self.error: Optional[str] = None

    def activate(self):
        self.status = "active"
        self.last_active = time.time()

    def complete_task(self):
        self.tasks_completed += 1
        self.status = "idle"

    def fail_task(self, error: str):
        self.tasks_failed += 1
        self.error = error
        self.status = "error"

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "status": self.status,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "error": self.error,
        }


class Orchestrator:
    """Core orchestration loop with parallel task execution, message bus, and lifecycle management.

    Flow: goal -> CTO planning -> Manager breakdown -> parallel execute -> review -> iterate.
    """

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.workspace_manager = WorkspaceManager()
        self.model_manager = ModelManager()
        self.agent_factory = AgentFactory(self.model_manager)
        self.agents: dict = {}
        self.agent_states: dict[str, AgentState] = {}
        self.iteration = 0
        self.max_iterations = 10
        self.task_timeout = 300  # seconds per individual task
        self.message_bus = MessageBus()
        self._cancel_event = asyncio.Event()
        self._event_callback: Optional[Callable] = None
        self._status = "idle"  # idle | initializing | running | completed | cancelled | error
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None

    @property
    def status(self) -> str:
        return self._status

    @property
    def elapsed_seconds(self) -> Optional[float]:
        if self._start_time is None:
            return None
        end = self._end_time or time.time()
        return round(end - self._start_time, 2)

    def get_state(self) -> dict:
        """Get full orchestrator state snapshot for monitoring."""
        return {
            "project_id": self.project_id,
            "status": self._status,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "elapsed_seconds": self.elapsed_seconds,
            "agents": {role: s.to_dict() for role, s in self.agent_states.items()},
        }

    def on_event(self, callback: Callable) -> None:
        """Register callback for orchestration events (e.g. WebSocket broadcast)."""
        self._event_callback = callback

    async def _emit(self, event_type: str, data: dict) -> None:
        """Emit an event to the registered callback and message bus."""
        event = {"type": event_type, "project_id": self.project_id, **data}
        if self._event_callback:
            try:
                await self._event_callback(event)
            except Exception:
                pass

    def initialize_project(self, goal: str) -> None:
        """Initialize workspace and spawn agents for a project."""
        self._status = "initializing"
        self.workspace_manager.create_workspace(self.project_id)
        workspace_path = self.workspace_manager.get_workspace_path(self.project_id)

        # CTO analyzes the goal and determines required roles
        cto = self.agent_factory.create("cto", workspace_path)
        self.agents["cto"] = cto
        self.agent_states["cto"] = AgentState("cto")
        self.message_bus.register("cto")

        required_roles = cto.analyze_and_plan(goal)

        # Spawn required agents and register on message bus
        for role in required_roles:
            agent = self.agent_factory.create(role, workspace_path)
            self.agents[role] = agent
            self.agent_states[role] = AgentState(role)
            self.message_bus.register(role)

    async def run_async(self, goal: str) -> dict:
        """Execute the main orchestration loop with parallel task execution and lifecycle management."""
        self._start_time = time.time()
        # Run blocking initialization in executor to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.initialize_project, goal)
        self._status = "running"
        await self._emit("run_started", {
            "goal": goal,
            "agents": list(self.agents.keys()),
        })

        results = []
        try:
            while self.iteration < self.max_iterations:
                if self._cancel_event.is_set():
                    self._status = "cancelled"
                    await self._emit("run_cancelled", {"iteration": self.iteration})
                    break

                self.iteration += 1
                await self._emit("iteration_started", {"iteration": self.iteration})

                # CTO planning (blocking LLM call -> run in executor)
                plan = await loop.run_in_executor(
                    None, self.agents["cto"].plan, goal, self.iteration
                )
                await self.message_bus.send(Message(
                    sender="cto", recipient="*", msg_type="plan", payload=plan,
                ))

                # Manager task breakdown (blocking LLM call -> run in executor)
                if "manager" in self.agents:
                    tasks = await loop.run_in_executor(
                        None, self.agents["manager"].decompose, plan
                    )
                else:
                    tasks = [plan]

                # Execute tasks via DAG (respects dependencies, maximizes parallelism)
                iteration_results = await self._execute_task_graph(tasks)

                # Broadcast results via message bus
                await self.message_bus.send(Message(
                    sender="orchestrator", recipient="*",
                    msg_type="results", payload=iteration_results,
                ))

                # Review (blocking LLM call -> run in executor)
                if "reviewer" in self.agents:
                    review = await loop.run_in_executor(
                        None, self.agents["reviewer"].review, iteration_results
                    )
                    await self._emit("review_complete", {
                        "iteration": self.iteration,
                        "approved": review.get("approved", False),
                    })
                    if review.get("approved", False):
                        break

                results.extend(iteration_results)
                await self._emit("iteration_complete", {
                    "iteration": self.iteration,
                    "result_count": len(iteration_results),
                    "agents": {r: s.to_dict() for r, s in self.agent_states.items()},
                })

            if self._status == "running":
                self._status = "completed"

        except Exception as e:
            self._status = "error"
            logger.error(f"Orchestration error: {e}")
            await self._emit("run_error", {"error": str(e)})
            raise
        finally:
            self._end_time = time.time()
            await self._cleanup()

        await self._emit("run_complete", {
            "iterations": self.iteration,
            "total_results": len(results),
            "elapsed_seconds": self.elapsed_seconds,
            "agent_summary": {r: s.to_dict() for r, s in self.agent_states.items()},
        })
        return {
            "project_id": self.project_id,
            "iterations": self.iteration,
            "results": results,
            "elapsed_seconds": self.elapsed_seconds,
        }

    def run(self, goal: str) -> dict:
        """Synchronous wrapper for run_async (backward compatible)."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already in an async context - create a task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self.run_async(goal))
                return future.result()
        else:
            return asyncio.run(self.run_async(goal))

    async def _execute_parallel(self, tasks: list) -> list:
        """Execute multiple independent tasks concurrently using asyncio.gather."""
        async_tasks = []
        for task in tasks:
            async_tasks.append(self._execute_single(task))

        results = await asyncio.gather(*async_tasks, return_exceptions=True)

        # Convert exceptions to error results
        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed.append({
                    "role": tasks[i].get("assigned_to", "unknown"),
                    "result": f"[Error] {result}",
                    "error": True,
                })
            else:
                processed.append(result)
        return processed

    async def _execute_single(self, task: dict) -> dict:
        """Execute a single task via its assigned agent, with state tracking and timeout."""
        agent_role = task.get("assigned_to", "engineer")
        if agent_role not in self.agents:
            return {"role": agent_role, "result": f"[Error] No agent for role: {agent_role}", "error": True}

        agent = self.agents[agent_role]
        state = self.agent_states.get(agent_role)
        if state:
            state.activate()

        await self._emit("task_started", {
            "role": agent_role,
            "task": str(task.get("description", ""))[:200],
        })

        # Run blocking LLM call in thread executor with timeout
        loop = asyncio.get_event_loop()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(None, agent.execute, task),
                timeout=self.task_timeout,
            )
            if state:
                state.complete_task()
        except asyncio.TimeoutError:
            error_msg = f"[Error] Task timed out after {self.task_timeout}s"
            if state:
                state.fail_task(error_msg)
            await self._emit("task_timeout", {"role": agent_role, "timeout": self.task_timeout})
            return {"role": agent_role, "result": error_msg, "error": True}
        except Exception as e:
            error_msg = f"[Error] {e}"
            if state:
                state.fail_task(error_msg)
            return {"role": agent_role, "result": error_msg, "error": True}

        # Post result to message bus
        await self.message_bus.send(Message(
            sender=agent_role, recipient="orchestrator",
            msg_type="result", payload=result,
        ))

        await self._emit("task_complete", {"role": agent_role})
        return result

    async def _execute_task_graph(self, tasks: list) -> list:
        """Execute tasks respecting dependency order, maximizing parallelism.

        Uses TaskGraph to compute execution layers. Each layer runs in parallel.
        Falls back to simple parallel/sequential classification if tasks lack task_id.
        """
        # Check if tasks have DAG structure (task_id + depends_on)
        has_dag = any(t.get("task_id") for t in tasks)

        if has_dag:
            graph = TaskGraph()
            graph.add_tasks(tasks)
            errors = graph.validate()
            if errors:
                logger.warning(f"Invalid task graph, falling back to simple: {errors}")
                has_dag = False

        if has_dag:
            layers = graph.get_execution_layers()
            await self._emit("dag_execution", {
                "iteration": self.iteration,
                "layers": len(layers),
                "total_tasks": graph.task_count,
            })

            all_results = []
            for layer_idx, layer in enumerate(layers):
                if self._cancel_event.is_set():
                    break
                await self._emit("dag_layer_start", {
                    "layer": layer_idx,
                    "task_count": len(layer),
                    "tasks": [t.get("task_id", "") for t in layer],
                })
                if len(layer) == 1:
                    result = await self._execute_single(layer[0])
                    all_results.append(result)
                else:
                    layer_results = await self._execute_parallel(layer)
                    all_results.extend(layer_results)
            return all_results
        else:
            # Fallback: simple parallel/sequential classification
            parallel, sequential = self._classify_tasks_simple(tasks)
            results = []
            if parallel:
                await self._emit("parallel_start", {
                    "iteration": self.iteration,
                    "task_count": len(parallel),
                })
                results.extend(await self._execute_parallel(parallel))
            for task in sequential:
                if self._cancel_event.is_set():
                    break
                results.append(await self._execute_single(task))
            return results

    def _classify_tasks_simple(self, tasks: list) -> tuple[list, list]:
        """Simple classification: tasks with depends_on are sequential, others parallel."""
        parallel = []
        sequential = []
        for task in tasks:
            if task.get("depends_on"):
                sequential.append(task)
            else:
                parallel.append(task)
        return parallel, sequential

    def cancel(self) -> None:
        """Request cancellation of the current run."""
        self._cancel_event.set()
        self._status = "cancelled"
        logger.info(f"Cancellation requested for project {self.project_id}")

    async def _cleanup(self) -> None:
        """Clean up resources after run completes, cancels, or errors."""
        logger.info(
            f"Cleanup: project={self.project_id} status={self._status} "
            f"elapsed={self.elapsed_seconds}s"
        )
        # Reset agent states to idle
        for state in self.agent_states.values():
            if state.status == "active":
                state.status = "idle"
