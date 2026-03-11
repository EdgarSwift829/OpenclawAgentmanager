"""Orchestrator - Main loop for multi-agent task execution with parallel support."""

import asyncio
from typing import Optional, Callable
from mado.backend.orchestrator.agent_factory import AgentFactory
from mado.backend.orchestrator.workspace_manager import WorkspaceManager
from mado.backend.orchestrator.message_bus import MessageBus, Message
from mado.backend.models.model_manager import ModelManager


class Orchestrator:
    """Core orchestration loop with parallel task execution and message bus.

    Flow: goal -> CTO planning -> Manager breakdown -> parallel execute -> review -> iterate.
    """

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.workspace_manager = WorkspaceManager()
        self.model_manager = ModelManager()
        self.agent_factory = AgentFactory(self.model_manager)
        self.agents: dict = {}
        self.iteration = 0
        self.max_iterations = 10
        self.message_bus = MessageBus()
        self._cancel_event = asyncio.Event()
        self._event_callback: Optional[Callable] = None

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
        self.workspace_manager.create_workspace(self.project_id)
        workspace_path = self.workspace_manager.get_workspace_path(self.project_id)

        # CTO analyzes the goal and determines required roles
        cto = self.agent_factory.create("cto", workspace_path)
        self.agents["cto"] = cto
        self.message_bus.register("cto")

        required_roles = cto.analyze_and_plan(goal)

        # Spawn required agents and register on message bus
        for role in required_roles:
            agent = self.agent_factory.create(role, workspace_path)
            self.agents[role] = agent
            self.message_bus.register(role)

    async def run_async(self, goal: str) -> dict:
        """Execute the main orchestration loop with parallel task execution."""
        self.initialize_project(goal)
        await self._emit("run_started", {"goal": goal})

        results = []
        while self.iteration < self.max_iterations:
            if self._cancel_event.is_set():
                await self._emit("run_cancelled", {"iteration": self.iteration})
                break

            self.iteration += 1
            await self._emit("iteration_started", {"iteration": self.iteration})

            # CTO planning
            plan = self.agents["cto"].plan(goal, self.iteration)
            await self.message_bus.send(Message(
                sender="cto", recipient="*", msg_type="plan", payload=plan,
            ))

            # Manager task breakdown
            if "manager" in self.agents:
                tasks = self.agents["manager"].decompose(plan)
            else:
                tasks = [plan]

            # Classify tasks: parallel (independent) vs sequential (dependent)
            parallel_tasks, sequential_tasks = self._classify_tasks(tasks)

            iteration_results = []

            # Execute independent tasks in parallel
            if parallel_tasks:
                await self._emit("parallel_start", {
                    "iteration": self.iteration,
                    "task_count": len(parallel_tasks),
                })
                parallel_results = await self._execute_parallel(parallel_tasks)
                iteration_results.extend(parallel_results)

            # Execute dependent tasks sequentially
            for task in sequential_tasks:
                if self._cancel_event.is_set():
                    break
                result = await self._execute_single(task)
                iteration_results.append(result)

            # Broadcast results via message bus
            await self.message_bus.send(Message(
                sender="orchestrator", recipient="*",
                msg_type="results", payload=iteration_results,
            ))

            # Review
            if "reviewer" in self.agents:
                review = self.agents["reviewer"].review(iteration_results)
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
            })

        await self._emit("run_complete", {
            "iterations": self.iteration,
            "total_results": len(results),
        })
        return {
            "project_id": self.project_id,
            "iterations": self.iteration,
            "results": results,
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
        """Execute a single task via its assigned agent, in a thread executor."""
        agent_role = task.get("assigned_to", "engineer")
        if agent_role not in self.agents:
            return {"role": agent_role, "result": f"[Error] No agent for role: {agent_role}", "error": True}

        agent = self.agents[agent_role]
        await self._emit("task_started", {
            "role": agent_role,
            "task": str(task.get("description", ""))[:200],
        })

        # Run blocking LLM call in thread executor
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, agent.execute, task)

        # Post result to message bus
        await self.message_bus.send(Message(
            sender=agent_role, recipient="orchestrator",
            msg_type="result", payload=result,
        ))

        await self._emit("task_complete", {"role": agent_role})
        return result

    def _classify_tasks(self, tasks: list) -> tuple[list, list]:
        """Classify tasks into parallel (independent) and sequential (dependent).

        Tasks with depends_on field are sequential; others are parallel.
        """
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
