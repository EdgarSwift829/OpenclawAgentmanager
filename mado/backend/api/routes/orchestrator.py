"""Orchestrator API routes - Start/stop/monitor orchestration runs."""

import asyncio
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional

from mado.backend.orchestrator.workspace_manager import get_workspace_manager

logger = logging.getLogger(__name__)

router = APIRouter()

# Active orchestration runs and their orchestrator instances
_runs: dict = {}
_orchestrators: dict = {}
_workspace_manager = get_workspace_manager()


class RunCreate(BaseModel):
    project_id: str
    goal: str
    max_iterations: Optional[int] = 30


class DispatchChild(BaseModel):
    parent_id: str
    child_id: str
    instruction: Optional[str] = None


class DispatchAllChildren(BaseModel):
    parent_id: str


class RunStatus(BaseModel):
    project_id: str
    status: str
    iteration: int
    max_iterations: int


def _check_parent_running(project_id: str):
    """Ensure parent project is running before allowing child to start."""
    config = _workspace_manager.get_project_config(project_id)
    parent_id = config.get("parent_id")
    if not parent_id:
        return  # Top-level project, no restriction
    parent_run = _runs.get(parent_id, {})
    if parent_run.get("status") != "running":
        raise HTTPException(
            status_code=409,
            detail=f"Parent project '{parent_id}' is not running. Start the parent first.",
        )


@router.post("/run")
async def start_run(data: RunCreate, background_tasks: BackgroundTasks):
    """Start an orchestration run for a project."""
    try:
        if data.project_id in _runs and _runs[data.project_id].get("status") == "running":
            raise HTTPException(status_code=409, detail="Run already in progress")

        # Enforce parent dependency: child can't start if parent is off
        _check_parent_running(data.project_id)

        max_iter = data.max_iterations if data.max_iterations and data.max_iterations > 0 else 30

        _runs[data.project_id] = {
            "status": "running",
            "iteration": 0,
            "max_iterations": max_iter,
            "result": None,
        }

        background_tasks.add_task(_execute_run, data.project_id, data.goal, max_iter)

        return {"status": "started", "project_id": data.project_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start run for {data.project_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start: {e}")


async def _execute_run(project_id: str, goal: str, max_iterations: int):
    """Execute orchestration run in background with async support."""
    try:
        # Lazy imports to avoid module-level import errors blocking the route
        from mado.backend.orchestrator.orchestrator import Orchestrator
        from mado.backend.api.routes.agents import register_session
        from mado.backend.api.routes.websocket import broadcaster

        orch = Orchestrator(project_id)
        orch.max_iterations = max_iterations
        _orchestrators[project_id] = orch

        # Connect WebSocket broadcasting
        async def ws_event_handler(event: dict):
            try:
                await broadcaster.broadcast(project_id, event)
            except Exception:
                pass
            if event.get("type") == "iteration_started":
                _runs[project_id]["iteration"] = event.get("iteration", 0)

        orch.on_event(ws_event_handler)

        # Run directly as async
        result = await orch.run_async(goal)

        register_session(project_id, orch.agents)

        _runs[project_id] = {
            "status": "completed",
            "iteration": orch.iteration,
            "max_iterations": max_iterations,
            "result": result,
        }
    except Exception as e:
        logger.error(f"Orchestration error for {project_id}: {e}", exc_info=True)
        _runs[project_id] = {
            "status": "error",
            "iteration": 0,
            "max_iterations": max_iterations,
            "error": str(e),
        }
    finally:
        _orchestrators.pop(project_id, None)


def _inherit_parent_context(parent_id: str, child_id: str):
    """Copy agent_profiles and project_memory from parent to child."""
    import shutil

    parent_config = _workspace_manager.get_project_config(parent_id)
    child_config = _workspace_manager.get_project_config(child_id)

    # Inherit agent_profiles: parent profiles are base, child overrides take priority
    parent_profiles = parent_config.get("agent_profiles", {})
    child_profiles = child_config.get("agent_profiles", {})
    if parent_profiles:
        merged = {**parent_profiles}  # start with parent
        for role, profile in child_profiles.items():
            # Only override if child has non-empty values
            if profile.get("title") or profile.get("personality"):
                merged[role] = profile
        _workspace_manager.update_project_config(child_id, {"agent_profiles": merged})
        logger.info(f"Inherited agent_profiles from {parent_id} to {child_id}")

    # Share project memory: append parent memory to child
    parent_dir = _workspace_manager.projects_root / parent_id
    child_dir = _workspace_manager.projects_root / child_id
    parent_memory = parent_dir / "project_memory.md"
    child_memory = child_dir / "project_memory.md"

    if parent_memory.exists():
        parent_text = parent_memory.read_text(encoding="utf-8")
        child_text = ""
        if child_memory.exists():
            child_text = child_memory.read_text(encoding="utf-8")

        # Add parent context section if not already present
        marker = f"## Inherited from parent: {parent_id}"
        if marker not in child_text:
            inherited_section = f"\n\n{marker}\n\n{parent_text}\n"
            child_memory.write_text(
                child_text + inherited_section, encoding="utf-8"
            )
            logger.info(f"Shared project_memory from {parent_id} to {child_id}")

    # Inherit rules if child has none
    for rule_key in ("rules_must", "rules_forbidden"):
        parent_rules = parent_config.get(rule_key, "")
        child_rules = child_config.get(rule_key, "")
        if parent_rules and not child_rules:
            _workspace_manager.update_project_config(child_id, {rule_key: parent_rules})
            logger.info(f"Inherited {rule_key} from {parent_id} to {child_id}")


@router.post("/dispatch-child")
async def dispatch_child(data: DispatchChild, background_tasks: BackgroundTasks):
    """Start a child project run with inherited parent context."""
    try:
        parent_config = _workspace_manager.get_project_config(data.parent_id)
        if not parent_config:
            raise HTTPException(status_code=404, detail=f"Parent '{data.parent_id}' not found")

        child_config = _workspace_manager.get_project_config(data.child_id)
        if not child_config:
            raise HTTPException(status_code=404, detail=f"Child '{data.child_id}' not found")

        # Verify parent-child relationship
        if data.child_id not in parent_config.get("children", []):
            raise HTTPException(status_code=400, detail=f"'{data.child_id}' is not a child of '{data.parent_id}'")

        if data.child_id in _runs and _runs[data.child_id].get("status") == "running":
            raise HTTPException(status_code=409, detail="Child run already in progress")

        # Inherit parent context to child
        _inherit_parent_context(data.parent_id, data.child_id)

        # Determine goal: instruction > child goal > parent goal
        goal = data.instruction or child_config.get("goal", "") or parent_config.get("goal", "")
        if data.instruction and child_config.get("goal"):
            goal = f"{child_config['goal']}\n\n親プロジェクトからの指示: {data.instruction}"

        max_iter = 30
        _runs[data.child_id] = {
            "status": "running",
            "iteration": 0,
            "max_iterations": max_iter,
            "result": None,
        }

        background_tasks.add_task(_execute_run, data.child_id, goal, max_iter)

        return {
            "status": "started",
            "child_id": data.child_id,
            "parent_id": data.parent_id,
            "inherited": True,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to dispatch child {data.child_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to dispatch: {e}")


@router.post("/dispatch-children")
async def dispatch_all_children(data: DispatchAllChildren, background_tasks: BackgroundTasks):
    """Start all child projects of a parent with inherited context."""
    try:
        parent_config = _workspace_manager.get_project_config(data.parent_id)
        if not parent_config:
            raise HTTPException(status_code=404, detail=f"Parent '{data.parent_id}' not found")

        children = parent_config.get("children", [])
        started = []
        skipped = []

        for child_id in children:
            child_config = _workspace_manager.get_project_config(child_id)
            if not child_config or child_config.get("status") == "archived":
                skipped.append(child_id)
                continue

            if child_id in _runs and _runs[child_id].get("status") == "running":
                skipped.append(child_id)
                continue

            # Inherit parent context
            _inherit_parent_context(data.parent_id, child_id)

            goal = child_config.get("goal", "") or parent_config.get("goal", "")
            max_iter = 30

            _runs[child_id] = {
                "status": "running",
                "iteration": 0,
                "max_iterations": max_iter,
                "result": None,
            }
            background_tasks.add_task(_execute_run, child_id, goal, max_iter)
            started.append(child_id)

        return {
            "status": "dispatched",
            "parent_id": data.parent_id,
            "started": started,
            "skipped": skipped,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to dispatch children of {data.parent_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to dispatch: {e}")


@router.get("/run/{project_id}")
async def get_run_status(project_id: str):
    """Get the status of an orchestration run."""
    run = _runs.get(project_id)
    if not run:
        raise HTTPException(status_code=404, detail="No run found for this project")
    return run


def _backup_project(project_id: str, reason: str):
    """Take a backup of the project, logging any errors."""
    try:
        path = _workspace_manager.backup_project(project_id, reason)
        logger.info(f"Backup created for {project_id}: {path}")
        return path
    except Exception as e:
        logger.warning(f"Backup failed for {project_id}: {e}")
        return None


@router.post("/run/{project_id}/stop")
async def stop_run(project_id: str):
    """Stop a running orchestration with actual cancellation.
    Creates a backup before stopping. Also stops all running child projects.
    """
    run = _runs.get(project_id)
    if not run or run["status"] != "running":
        raise HTTPException(status_code=404, detail="No active run to stop")

    # Backup before stopping
    iter_info = f"iter{run.get('iteration', 0)}"
    backup_path = _backup_project(project_id, f"stop_{iter_info}")

    # Signal the orchestrator to cancel
    orch = _orchestrators.get(project_id)
    if orch:
        orch.cancel()

    _runs[project_id]["status"] = "stopped"

    # Cascade stop to children (with backups)
    stopped_children = _cascade_stop_children(project_id)

    return {
        "status": "stopped",
        "project_id": project_id,
        "stopped_children": stopped_children,
        "backup": backup_path,
    }


def _cascade_stop_children(parent_id: str) -> list:
    """Recursively stop all running child projects with backups."""
    config = _workspace_manager.get_project_config(parent_id)
    children_ids = config.get("children", [])
    stopped = []
    for cid in children_ids:
        child_run = _runs.get(cid, {})
        if child_run.get("status") == "running":
            # Backup child before stopping
            _backup_project(cid, f"cascade_stop_iter{child_run.get('iteration', 0)}")
            orch = _orchestrators.get(cid)
            if orch:
                orch.cancel()
            _runs[cid]["status"] = "stopped"
            stopped.append(cid)
        # Recurse into grandchildren
        stopped.extend(_cascade_stop_children(cid))
    return stopped


@router.post("/run/{project_id}/pause")
async def pause_run(project_id: str):
    """Pause a running orchestration (stops but preserves iteration count for resume).
    Creates a backup before pausing.
    """
    run = _runs.get(project_id)
    if not run or run["status"] != "running":
        raise HTTPException(status_code=404, detail="No active run to pause")

    # Backup before pausing
    iter_info = f"iter{run.get('iteration', 0)}"
    backup_path = _backup_project(project_id, f"pause_{iter_info}")

    orch = _orchestrators.get(project_id)
    if orch:
        orch.cancel()

    _runs[project_id]["status"] = "paused"
    return {
        "status": "paused",
        "project_id": project_id,
        "iteration": run.get("iteration", 0),
        "max_iterations": run.get("max_iterations", 0),
        "backup": backup_path,
    }


@router.get("/run/{project_id}/state")
async def get_run_state(project_id: str):
    """Get detailed orchestrator state including agent lifecycle info."""
    orch = _orchestrators.get(project_id)
    if orch:
        return orch.get_state()

    run = _runs.get(project_id)
    if not run:
        raise HTTPException(status_code=404, detail="No run found for this project")
    return run


@router.get("/runs")
async def list_runs():
    """List all orchestration runs."""
    return {"runs": {k: {"status": v["status"], "iteration": v["iteration"]} for k, v in _runs.items()}}
