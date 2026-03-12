"""Orchestrator - Main loop for multi-agent task execution with parallel support.

Lifecycle states:
  idle -> initializing -> running -> completed | cancelled | error
  Agent states: idle -> active -> done | error

Enhanced with:
  - Project config/rules injection into all agents
  - Iteration context sharing (previous results feed into next iteration)
  - Shared context between agents within an iteration (e.g. researcher -> engineer)
  - Structured event emission with human-readable messages
  - Iteration summary memory persistence
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
        self.current_task: Optional[str] = None

    def activate(self, task_desc: str = ""):
        self.status = "active"
        self.last_active = time.time()
        self.current_task = task_desc[:100] if task_desc else None

    def complete_task(self):
        self.tasks_completed += 1
        self.status = "idle"
        self.current_task = None

    def fail_task(self, error: str):
        self.tasks_failed += 1
        self.error = error
        self.status = "error"
        self.current_task = None

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "status": self.status,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "error": self.error,
            "current_task": self.current_task,
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
        self._iteration_summaries: list = []  # context passed between iterations
        self._project_config: dict = {}

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

    def _load_parent_context(self, parent_id: str) -> None:
        """Load parent project context for child runs (agent profiles + memory)."""
        try:
            parent_config = self.workspace_manager.get_project_config(parent_id)
            if not parent_config:
                return

            # Merge parent agent_profiles as defaults (child overrides take priority)
            parent_profiles = parent_config.get("agent_profiles", {})
            child_profiles = self._project_config.get("agent_profiles", {})
            if parent_profiles and not child_profiles:
                self._project_config["agent_profiles"] = parent_profiles
                logger.info(f"Child {self.project_id} inherited agent_profiles from parent {parent_id}")

            # Load parent's project memory as additional context
            parent_memory_path = self.workspace_manager.projects_root / parent_id / "project_memory.md"
            if parent_memory_path.exists():
                parent_memory = parent_memory_path.read_text(encoding="utf-8")
                self._project_config["_parent_memory"] = parent_memory
                logger.info(f"Child {self.project_id} loaded parent memory from {parent_id}")

            # Inherit parent rules if child has none
            for rule_key in ("rules_must", "rules_forbidden"):
                if parent_config.get(rule_key) and not self._project_config.get(rule_key):
                    self._project_config[rule_key] = parent_config[rule_key]

        except Exception as e:
            logger.warning(f"Failed to load parent context from {parent_id}: {e}")

    def _build_goal_with_children(self, goal: str) -> str:
        """If project has children, augment the goal with child project context."""
        config = self.workspace_manager.get_project_config(self.project_id)
        children = config.get("children", [])
        if not children:
            return goal

        parts = [goal, "\n\n--- Sub-projects (managed by this team) ---"]
        for child_id in children:
            child_config = self.workspace_manager.get_project_config(child_id)
            if child_config.get("status") == "archived":
                continue
            child_goal = child_config.get("goal", "")
            child_status = child_config.get("status", "initialized")
            parts.append(f"- [{child_id}] status={child_status} goal={child_goal}")
        return "\n".join(parts)

    def _inject_agent_context(self, agent, config: dict) -> None:
        """Inject project config, rules, message bus, and iteration context into an agent."""
        agent.project_config = config
        agent.message_bus = self.message_bus
        agent.iteration_context = list(self._iteration_summaries)

    def _inject_shared_context(self, results_so_far: list) -> None:
        """Share results from completed tasks with all agents (for this iteration)."""
        shared = {}
        for r in results_so_far:
            if isinstance(r, dict):
                role = r.get("role", "unknown")
                shared[role] = {
                    "summary": r.get("summary", ""),
                    "files_modified": r.get("files_modified", []),
                    "result": str(r.get("result", ""))[:1000],
                }
        for agent in self.agents.values():
            agent.shared_context = shared

    def initialize_project(self, goal: str) -> None:
        """Initialize workspace and spawn agents for a project."""
        self._status = "initializing"
        self.workspace_manager.create_workspace(self.project_id)
        workspace_path = self.workspace_manager.get_workspace_path(self.project_id)

        # Load project config (includes rules_must, rules_forbidden, agent_profiles, etc.)
        self._project_config = self.workspace_manager.get_project_config(self.project_id)

        # If child project, load parent's project memory as additional context
        parent_id = self._project_config.get("parent_id")
        if parent_id:
            self._load_parent_context(parent_id)

        # Augment goal with child project context
        augmented_goal = self._build_goal_with_children(goal)

        # CTO analyzes the goal and determines required roles
        cto = self.agent_factory.create("cto", workspace_path)
        self._inject_agent_context(cto, self._project_config)
        self.agents["cto"] = cto
        self.agent_states["cto"] = AgentState("cto")
        self.message_bus.register("cto")

        required_roles = cto.analyze_and_plan(augmented_goal)

        # Spawn required agents and register on message bus
        for role in required_roles:
            agent = self.agent_factory.create(role, workspace_path)
            self._inject_agent_context(agent, self._project_config)
            self.agents[role] = agent
            self.agent_states[role] = AgentState(role)
            self.message_bus.register(role)

        # Also create workspaces for children so they share the same agent set
        config = self.workspace_manager.get_project_config(self.project_id)
        for child_id in config.get("children", []):
            child_config = self.workspace_manager.get_project_config(child_id)
            if child_config.get("status") != "archived":
                self.workspace_manager.create_workspace(child_id)

    async def run_async(self, goal: str) -> dict:
        """Execute the main orchestration loop with parallel task execution and lifecycle management."""
        self._start_time = time.time()
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.initialize_project, goal)
        self._status = "running"

        augmented_goal = self._build_goal_with_children(goal)

        await self._emit("run_started", {
            "goal": goal,
            "agents": list(self.agents.keys()),
            "message": f"開始: {len(self.agents)}エージェントでチーム構成完了",
        })

        results = []
        try:
            while self.iteration < self.max_iterations:
                if self._cancel_event.is_set():
                    self._status = "cancelled"
                    await self._emit("run_cancelled", {
                        "iteration": self.iteration,
                        "message": f"イテレーション {self.iteration} でキャンセルされました",
                    })
                    break

                self.iteration += 1

                # Update iteration context for all agents
                for agent in self.agents.values():
                    agent.iteration_context = list(self._iteration_summaries)

                await self._emit("iteration_started", {
                    "iteration": self.iteration,
                    "message": f"イテレーション {self.iteration}/{self.max_iterations} 開始",
                })

                # ── Phase 1: CTO Planning ──
                await self._emit("agent_activity", {
                    "role": "cto",
                    "activity": "planning",
                    "message": f"CTO がイテレーション {self.iteration} の計画を作成中...",
                })

                plan = await loop.run_in_executor(
                    None, self.agents["cto"].plan, augmented_goal, self.iteration
                )

                plan_summary = ""
                if isinstance(plan, dict):
                    plan_summary = plan.get("plan_summary", "")

                await self._emit("plan_created", {
                    "iteration": self.iteration,
                    "plan_summary": plan_summary[:300],
                    "message": f"計画: {plan_summary[:150]}" if plan_summary else "計画作成完了",
                })

                await self.message_bus.send(Message(
                    sender="cto", recipient="*", msg_type="plan", payload=plan,
                ))

                # ── Phase 2: Manager Task Breakdown ──
                if "manager" in self.agents:
                    await self._emit("agent_activity", {
                        "role": "manager",
                        "activity": "decomposing",
                        "message": "Manager がタスクを分解中...",
                    })
                    tasks = await loop.run_in_executor(
                        None, self.agents["manager"].decompose, plan
                    )
                    await self._emit("tasks_decomposed", {
                        "iteration": self.iteration,
                        "task_count": len(tasks),
                        "tasks": [
                            {"id": t.get("task_id", ""), "role": t.get("assigned_to", ""), "desc": t.get("description", "")[:80]}
                            for t in tasks[:10]
                        ],
                        "message": f"Manager: {len(tasks)}個のタスクに分解",
                    })
                else:
                    tasks = [plan]

                # ── Phase 3: Execute Tasks via DAG ──
                iteration_results = await self._execute_task_graph(tasks)

                # Share results between agents for this iteration
                self._inject_shared_context(iteration_results)

                # Broadcast results via message bus
                await self.message_bus.send(Message(
                    sender="orchestrator", recipient="*",
                    msg_type="results", payload=iteration_results,
                ))

                # ── Phase 4: Review ──
                if "reviewer" in self.agents:
                    await self._emit("agent_activity", {
                        "role": "reviewer",
                        "activity": "reviewing",
                        "message": "Reviewer が成果物をレビュー中...",
                    })
                    review = await loop.run_in_executor(
                        None, self.agents["reviewer"].review, iteration_results
                    )

                    approved = review.get("approved", False)
                    score = review.get("score", "?")
                    feedback = review.get("feedback", "")
                    issues = review.get("issues", [])

                    await self._emit("review_complete", {
                        "iteration": self.iteration,
                        "approved": approved,
                        "score": score,
                        "issue_count": len(issues),
                        "feedback": feedback[:200],
                        "message": (
                            f"レビュー: {'承認' if approved else '差し戻し'} "
                            f"(スコア: {score}/10, 問題: {len(issues)}件)"
                        ),
                    })

                    if approved:
                        await self._emit("iteration_approved", {
                            "iteration": self.iteration,
                            "message": f"イテレーション {self.iteration} が承認されました！",
                        })
                        break

                # ── Build iteration summary for next iteration ──
                iter_summary = self._build_iteration_summary(iteration_results, plan)
                self._iteration_summaries.append(iter_summary)

                # Save summary to project memory
                self._save_iteration_memory(iter_summary)

                results.extend(iteration_results)
                await self._emit("iteration_complete", {
                    "iteration": self.iteration,
                    "result_count": len(iteration_results),
                    "agents": {r: s.to_dict() for r, s in self.agent_states.items()},
                    "message": f"イテレーション {self.iteration} 完了 ({len(iteration_results)}件の成果)",
                })

            if self._status == "running":
                self._status = "completed"

        except Exception as e:
            self._status = "error"
            logger.error(f"Orchestration error: {e}")
            await self._emit("run_error", {
                "error": str(e),
                "message": f"エラー発生: {str(e)[:200]}",
            })
            raise
        finally:
            self._end_time = time.time()
            await self._cleanup()

        await self._emit("run_complete", {
            "iterations": self.iteration,
            "total_results": len(results),
            "elapsed_seconds": self.elapsed_seconds,
            "agent_summary": {r: s.to_dict() for r, s in self.agent_states.items()},
            "message": (
                f"完了: {self.iteration}イテレーション, {len(results)}件の成果, "
                f"{self.elapsed_seconds}秒"
            ),
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
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self.run_async(goal))
                return future.result()
        else:
            return asyncio.run(self.run_async(goal))

    def _build_iteration_summary(self, results: list, plan: dict) -> dict:
        """Build a concise summary of the iteration for context passing."""
        summaries = []
        files_modified = []
        errors = []

        for r in results:
            if isinstance(r, dict):
                summaries.append(f"[{r.get('role', '?')}] {r.get('summary', '')[:150]}")
                files_modified.extend(r.get("files_modified", []))
                if r.get("error"):
                    errors.append(f"[{r.get('role', '?')}] {r.get('result', '')[:100]}")

        plan_summary = plan.get("plan_summary", "") if isinstance(plan, dict) else str(plan)[:200]

        return {
            "iteration": self.iteration,
            "plan": plan_summary,
            "summary": "\n".join(summaries),
            "files_modified": files_modified,
            "errors": errors,
            "agent_states": {r: s.to_dict() for r, s in self.agent_states.items()},
        }

    def _save_iteration_memory(self, summary: dict) -> None:
        """Save iteration summary to project memory via any agent's memory tools."""
        for agent in self.agents.values():
            if agent.memory_tools:
                try:
                    text = (
                        f"Plan: {summary.get('plan', '')}\n"
                        f"Results:\n{summary.get('summary', '')}\n"
                        f"Files: {summary.get('files_modified', [])}\n"
                    )
                    if summary.get("errors"):
                        text += f"Errors: {summary['errors']}\n"
                    agent.save_memory(f"Iteration {summary['iteration']} Summary", text)
                except Exception as e:
                    logger.warning(f"Failed to save iteration memory: {e}")
                break

    async def _execute_parallel(self, tasks: list) -> list:
        """Execute multiple independent tasks concurrently using asyncio.gather."""
        async_tasks = []
        for task in tasks:
            async_tasks.append(self._execute_single(task))

        results = await asyncio.gather(*async_tasks, return_exceptions=True)

        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed.append({
                    "role": tasks[i].get("assigned_to", "unknown"),
                    "result": f"[Error] {result}",
                    "summary": f"Error: {result}",
                    "error": True,
                })
            else:
                processed.append(result)
        return processed

    async def _execute_single(self, task: dict) -> dict:
        """Execute a single task via its assigned agent, with state tracking and timeout."""
        agent_role = task.get("assigned_to", "engineer")
        task_desc = task.get("description", "")

        if agent_role not in self.agents:
            return {
                "role": agent_role,
                "result": f"[Error] No agent for role: {agent_role}",
                "summary": f"Error: no {agent_role} agent",
                "error": True,
            }

        agent = self.agents[agent_role]
        state = self.agent_states.get(agent_role)
        if state:
            state.activate(task_desc)

        await self._emit("task_started", {
            "role": agent_role,
            "task_id": task.get("task_id", ""),
            "task": task_desc[:200],
            "message": f"{agent_role}: {task_desc[:100]}",
        })

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
            await self._emit("task_timeout", {
                "role": agent_role,
                "timeout": self.task_timeout,
                "message": f"{agent_role}: タイムアウト ({self.task_timeout}秒)",
            })
            return {"role": agent_role, "result": error_msg, "summary": error_msg, "error": True}
        except Exception as e:
            error_msg = f"[Error] {e}"
            if state:
                state.fail_task(error_msg)
            await self._emit("task_error", {
                "role": agent_role,
                "error": str(e)[:200],
                "message": f"{agent_role}: エラー - {str(e)[:100]}",
            })
            return {"role": agent_role, "result": error_msg, "summary": error_msg, "error": True}

        # Post result to message bus
        await self.message_bus.send(Message(
            sender=agent_role, recipient="orchestrator",
            msg_type="result", payload=result,
        ))

        summary = result.get("summary", "") if isinstance(result, dict) else str(result)[:100]
        files_mod = result.get("files_modified", []) if isinstance(result, dict) else []
        await self._emit("task_complete", {
            "role": agent_role,
            "task_id": task.get("task_id", ""),
            "summary": summary[:200],
            "files_modified": files_mod,
            "message": f"{agent_role} 完了: {summary[:100]}",
        })
        return result

    async def _execute_task_graph(self, tasks: list) -> list:
        """Execute tasks respecting dependency order, maximizing parallelism."""
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
                "message": f"DAG実行: {graph.task_count}タスク, {len(layers)}レイヤー",
            })

            all_results = []
            for layer_idx, layer in enumerate(layers):
                if self._cancel_event.is_set():
                    break

                task_ids = [t.get("task_id", "") for t in layer]
                roles = [t.get("assigned_to", "") for t in layer]
                await self._emit("dag_layer_start", {
                    "layer": layer_idx,
                    "task_count": len(layer),
                    "tasks": task_ids,
                    "message": (
                        f"レイヤー {layer_idx + 1}/{len(layers)}: "
                        f"{', '.join(roles)} ({len(layer)}並列)"
                    ),
                })

                if len(layer) == 1:
                    result = await self._execute_single(layer[0])
                    all_results.append(result)
                else:
                    layer_results = await self._execute_parallel(layer)
                    all_results.extend(layer_results)

                # Share layer results with agents for context in next layers
                self._inject_shared_context(all_results)

            return all_results
        else:
            parallel, sequential = self._classify_tasks_simple(tasks)
            results = []
            if parallel:
                await self._emit("parallel_start", {
                    "iteration": self.iteration,
                    "task_count": len(parallel),
                    "message": f"{len(parallel)}タスクを並列実行中",
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
        for state in self.agent_states.values():
            if state.status == "active":
                state.status = "idle"
