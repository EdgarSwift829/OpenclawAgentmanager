"""App-mode task management API routes."""

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from mado.backend.orchestrator.workspace_manager import get_workspace_manager
from mado.backend.scheduler.scheduler import AppTask, get_scheduler

logger = logging.getLogger(__name__)
router = APIRouter()
_workspace_manager = get_workspace_manager()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class AppTaskCreate(BaseModel):
    title: str
    prompt: str
    schedule_type: str = "manual"  # manual | interval | cron
    interval_minutes: int = 0
    cron_expr: str = ""
    deadline: Optional[str] = None
    enabled: bool = True


class AppTaskUpdate(BaseModel):
    title: Optional[str] = None
    prompt: Optional[str] = None
    schedule_type: Optional[str] = None
    interval_minutes: Optional[int] = None
    cron_expr: Optional[str] = None
    deadline: Optional[str] = None
    enabled: Optional[bool] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_app_mode(project_id: str) -> dict:
    """Validate project exists and is in app mode."""
    config = _workspace_manager.get_project_config(project_id)
    if not config:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    if config.get("mode") != "app":
        raise HTTPException(status_code=400, detail="Project is not in app mode")
    return config


def _save_tasks(project_id: str, tasks: List[AppTask]):
    """Persist task list to project config and update scheduler."""
    task_dicts = [t.to_dict() for t in tasks]
    _workspace_manager.update_project_config(project_id, {"app_tasks": task_dicts})
    get_scheduler().register_project(project_id, tasks)


def _load_tasks(project_id: str) -> List[AppTask]:
    """Load tasks from project config."""
    config = _workspace_manager.get_project_config(project_id)
    raw = config.get("app_tasks", [])
    return [AppTask.from_dict(d) for d in raw]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/{project_id}/tasks")
async def list_app_tasks(project_id: str):
    """List all tasks for an app-mode project."""
    _ensure_app_mode(project_id)
    tasks = _load_tasks(project_id)
    active = get_scheduler().get_active(project_id)
    return {
        "project_id": project_id,
        "tasks": [t.to_dict() for t in tasks],
        "active_task_ids": list(active.keys()),
    }


@router.post("/{project_id}/tasks")
async def create_app_task(project_id: str, data: AppTaskCreate):
    """Create a new task in an app-mode project."""
    _ensure_app_mode(project_id)
    tasks = _load_tasks(project_id)

    task = AppTask(
        title=data.title,
        prompt=data.prompt,
        schedule_type=data.schedule_type,
        interval_minutes=data.interval_minutes,
        cron_expr=data.cron_expr,
        deadline=data.deadline,
        enabled=data.enabled,
    )
    tasks.append(task)
    _save_tasks(project_id, tasks)
    return task.to_dict()


@router.put("/{project_id}/tasks/{task_id}")
async def update_app_task(project_id: str, task_id: str, data: AppTaskUpdate):
    """Update an existing task."""
    _ensure_app_mode(project_id)
    tasks = _load_tasks(project_id)
    task = next((t for t in tasks if t.task_id == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    updates = data.model_dump(exclude_none=True)
    for key, val in updates.items():
        setattr(task, key, val)

    _save_tasks(project_id, tasks)
    return task.to_dict()


@router.delete("/{project_id}/tasks/{task_id}")
async def delete_app_task(project_id: str, task_id: str):
    """Delete a task."""
    _ensure_app_mode(project_id)
    tasks = _load_tasks(project_id)
    tasks = [t for t in tasks if t.task_id != task_id]
    _save_tasks(project_id, tasks)
    return {"deleted": task_id}


@router.post("/{project_id}/tasks/{task_id}/run")
async def run_app_task(project_id: str, task_id: str, background_tasks: BackgroundTasks):
    """Manually trigger a task execution."""
    _ensure_app_mode(project_id)
    tasks = _load_tasks(project_id)
    task = next((t for t in tasks if t.task_id == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    scheduler = get_scheduler()
    active = scheduler.get_active(project_id)
    if task_id in active:
        raise HTTPException(status_code=409, detail="Task is already running")

    # Register tasks in scheduler if not already
    scheduler.register_project(project_id, tasks)

    async def _run():
        execution = await scheduler.execute_task(project_id, task)
        # Persist updated timing back to config
        _save_tasks(project_id, tasks)

    background_tasks.add_task(_run)
    return {"status": "started", "task_id": task_id}


@router.get("/{project_id}/history")
async def get_task_history(project_id: str, limit: int = 50):
    """Get execution history for an app-mode project."""
    _ensure_app_mode(project_id)
    history = get_scheduler().get_history(project_id, limit)
    return {
        "project_id": project_id,
        "history": [h.to_dict() for h in history],
    }


@router.post("/{project_id}/scheduler/start")
async def start_scheduler(project_id: str):
    """Start the scheduler for an app-mode project (enables auto-execution)."""
    _ensure_app_mode(project_id)
    tasks = _load_tasks(project_id)
    scheduler = get_scheduler()
    scheduler.register_project(project_id, tasks)
    scheduler.start()  # idempotent: starts the global loop if not running
    return {"status": "scheduler_started", "project_id": project_id}


@router.post("/{project_id}/scheduler/stop")
async def stop_scheduler_for_project(project_id: str):
    """Unregister a project from the scheduler."""
    _ensure_app_mode(project_id)
    get_scheduler().unregister_project(project_id)
    return {"status": "scheduler_stopped", "project_id": project_id}
