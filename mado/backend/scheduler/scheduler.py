"""App-mode scheduler: manages periodic and one-shot task execution.

Each app-mode project has a list of AppTask definitions.  The scheduler
checks which tasks are due, dispatches them to the orchestrator, and
records execution history.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class AppTask:
    """A user-defined task within an app-mode project."""

    def __init__(
        self,
        task_id: str = "",
        title: str = "",
        prompt: str = "",
        schedule_type: str = "manual",  # manual | interval | cron
        interval_minutes: int = 0,
        cron_expr: str = "",
        deadline: Optional[str] = None,  # ISO datetime or None (perpetual)
        enabled: bool = True,
        last_run: Optional[str] = None,
        next_run: Optional[str] = None,
    ):
        self.task_id = task_id or str(uuid.uuid4())[:8]
        self.title = title
        self.prompt = prompt
        self.schedule_type = schedule_type
        self.interval_minutes = interval_minutes
        self.cron_expr = cron_expr
        self.deadline = deadline
        self.enabled = enabled
        self.last_run = last_run
        self.next_run = next_run

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "prompt": self.prompt,
            "schedule_type": self.schedule_type,
            "interval_minutes": self.interval_minutes,
            "cron_expr": self.cron_expr,
            "deadline": self.deadline,
            "enabled": self.enabled,
            "last_run": self.last_run,
            "next_run": self.next_run,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AppTask":
        return cls(
            task_id=d.get("task_id", ""),
            title=d.get("title", ""),
            prompt=d.get("prompt", ""),
            schedule_type=d.get("schedule_type", "manual"),
            interval_minutes=d.get("interval_minutes", 0),
            cron_expr=d.get("cron_expr", ""),
            deadline=d.get("deadline"),
            enabled=d.get("enabled", True),
            last_run=d.get("last_run"),
            next_run=d.get("next_run"),
        )

    def is_due(self) -> bool:
        """Check if this task should run now."""
        if not self.enabled:
            return False
        if self.schedule_type == "manual":
            return False  # manual tasks are triggered explicitly

        # Check deadline expiry
        if self.deadline:
            try:
                dl = datetime.fromisoformat(self.deadline)
                if dl.tzinfo is None:
                    dl = dl.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > dl:
                    return False
            except (ValueError, TypeError):
                pass

        if not self.next_run:
            return True  # never run before, due now

        try:
            nr = datetime.fromisoformat(self.next_run)
            if nr.tzinfo is None:
                nr = nr.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) >= nr
        except (ValueError, TypeError):
            return True

    def compute_next_run(self) -> Optional[str]:
        """Compute next_run based on schedule_type."""
        now = datetime.now(timezone.utc)
        if self.schedule_type == "interval" and self.interval_minutes > 0:
            from datetime import timedelta
            nxt = now + timedelta(minutes=self.interval_minutes)
            return nxt.isoformat()
        # For cron or manual, no automatic next_run
        return None


class TaskExecution:
    """Record of a single task execution."""

    def __init__(
        self,
        execution_id: str = "",
        task_id: str = "",
        project_id: str = "",
        started_at: str = "",
        finished_at: Optional[str] = None,
        status: str = "running",  # running | completed | error
        result: Optional[str] = None,
        error: Optional[str] = None,
    ):
        self.execution_id = execution_id or str(uuid.uuid4())[:8]
        self.task_id = task_id
        self.project_id = project_id
        self.started_at = started_at or datetime.now(timezone.utc).isoformat()
        self.finished_at = finished_at
        self.status = status
        self.result = result
        self.error = error

    def to_dict(self) -> dict:
        return {
            "execution_id": self.execution_id,
            "task_id": self.task_id,
            "project_id": self.project_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status,
            "result": self.result,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

class AppScheduler:
    """Manages scheduling for app-mode projects.

    Runs a background loop that periodically checks for due tasks
    and dispatches them to the orchestrator.
    """

    def __init__(self):
        self._running = False
        self._loop_task: Optional[asyncio.Task] = None
        # project_id -> list of AppTask
        self._tasks: Dict[str, List[AppTask]] = {}
        # project_id -> list of TaskExecution (recent, capped)
        self._history: Dict[str, List[TaskExecution]] = {}
        # project_id -> task_id -> TaskExecution (currently running)
        self._active: Dict[str, Dict[str, TaskExecution]] = {}
        self._check_interval = 30  # seconds between scheduler ticks

    def register_project(self, project_id: str, tasks: List[AppTask]):
        """Register or update tasks for an app-mode project."""
        self._tasks[project_id] = tasks
        if project_id not in self._history:
            self._history[project_id] = []
        if project_id not in self._active:
            self._active[project_id] = {}

    def unregister_project(self, project_id: str):
        """Remove a project from the scheduler."""
        self._tasks.pop(project_id, None)
        self._history.pop(project_id, None)
        self._active.pop(project_id, None)

    def get_tasks(self, project_id: str) -> List[AppTask]:
        return self._tasks.get(project_id, [])

    def get_history(self, project_id: str, limit: int = 50) -> List[TaskExecution]:
        return self._history.get(project_id, [])[-limit:]

    def get_active(self, project_id: str) -> Dict[str, TaskExecution]:
        return self._active.get(project_id, {})

    async def execute_task(self, project_id: str, task: AppTask) -> TaskExecution:
        """Execute a single app-mode task using the orchestrator."""
        execution = TaskExecution(
            task_id=task.task_id,
            project_id=project_id,
            status="running",
        )

        if project_id not in self._active:
            self._active[project_id] = {}
        self._active[project_id][task.task_id] = execution

        try:
            from mado.backend.orchestrator.orchestrator import Orchestrator
            from mado.backend.api.routes.websocket import broadcaster

            orch = Orchestrator(project_id)
            orch.max_iterations = 30

            async def ws_handler(event: dict):
                try:
                    await broadcaster.broadcast(project_id, event)
                except Exception:
                    pass

            orch.on_event(ws_handler)

            result = await orch.run_async(task.prompt)

            execution.status = "completed"
            execution.result = str(result) if result else "completed"
            execution.finished_at = datetime.now(timezone.utc).isoformat()

        except Exception as e:
            logger.error("App task execution failed: %s / %s: %s", project_id, task.task_id, e)
            execution.status = "error"
            execution.error = str(e)
            execution.finished_at = datetime.now(timezone.utc).isoformat()

        finally:
            # Update task timing
            task.last_run = datetime.now(timezone.utc).isoformat()
            task.next_run = task.compute_next_run()

            # Move from active to history
            self._active.get(project_id, {}).pop(task.task_id, None)
            if project_id not in self._history:
                self._history[project_id] = []
            self._history[project_id].append(execution)
            # Cap history
            if len(self._history[project_id]) > 200:
                self._history[project_id] = self._history[project_id][-100:]

        return execution

    async def run_manual_task(self, project_id: str, task_id: str) -> Optional[TaskExecution]:
        """Manually trigger a specific task."""
        tasks = self._tasks.get(project_id, [])
        task = next((t for t in tasks if t.task_id == task_id), None)
        if not task:
            return None

        # Don't run if already active
        if task_id in self._active.get(project_id, {}):
            return None

        return await self.execute_task(project_id, task)

    async def _scheduler_loop(self):
        """Background loop that checks for due tasks."""
        while self._running:
            try:
                for project_id, tasks in list(self._tasks.items()):
                    active = self._active.get(project_id, {})
                    for task in tasks:
                        if task.task_id in active:
                            continue  # already running
                        if task.is_due():
                            logger.info("Scheduler: dispatching task %s/%s", project_id, task.task_id)
                            asyncio.create_task(self.execute_task(project_id, task))
            except Exception as e:
                logger.error("Scheduler loop error: %s", e)

            await asyncio.sleep(self._check_interval)

    def start(self):
        """Start the scheduler background loop."""
        if self._running:
            return
        self._running = True
        self._loop_task = asyncio.ensure_future(self._scheduler_loop())
        logger.info("App scheduler started")

    def stop(self):
        """Stop the scheduler background loop."""
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            self._loop_task = None
        logger.info("App scheduler stopped")


# Singleton instance
_scheduler: Optional[AppScheduler] = None


def get_scheduler() -> AppScheduler:
    """Get the global app scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AppScheduler()
    return _scheduler
