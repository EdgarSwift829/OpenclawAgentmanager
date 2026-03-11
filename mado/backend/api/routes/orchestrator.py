"""Orchestrator API routes - Start/stop/monitor orchestration runs."""

import asyncio
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional

from mado.backend.orchestrator.workspace_manager import WorkspaceManager

logger = logging.getLogger(__name__)

router = APIRouter()

# Active orchestration runs and their orchestrator instances
_runs: dict = {}
_orchestrators: dict = {}
_workspace_manager = WorkspaceManager()


class RunCreate(BaseModel):
    project_id: str
    goal: str
    max_iterations: Optional[int] = 30


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


@router.get("/run/{project_id}")
async def get_run_status(project_id: str):
    """Get the status of an orchestration run."""
    run = _runs.get(project_id)
    if not run:
        raise HTTPException(status_code=404, detail="No run found for this project")
    return run


@router.post("/run/{project_id}/stop")
async def stop_run(project_id: str):
    """Stop a running orchestration with actual cancellation.
    Also stops all running child projects (parent off = children off).
    """
    run = _runs.get(project_id)
    if not run or run["status"] != "running":
        raise HTTPException(status_code=404, detail="No active run to stop")

    # Signal the orchestrator to cancel
    orch = _orchestrators.get(project_id)
    if orch:
        orch.cancel()

    _runs[project_id]["status"] = "stopped"

    # Cascade stop to children
    stopped_children = _cascade_stop_children(project_id)

    return {"status": "stopped", "project_id": project_id, "stopped_children": stopped_children}


def _cascade_stop_children(parent_id: str) -> list:
    """Recursively stop all running child projects."""
    config = _workspace_manager.get_project_config(parent_id)
    children_ids = config.get("children", [])
    stopped = []
    for cid in children_ids:
        child_run = _runs.get(cid, {})
        if child_run.get("status") == "running":
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
    """Pause a running orchestration (stops but preserves iteration count for resume)."""
    run = _runs.get(project_id)
    if not run or run["status"] != "running":
        raise HTTPException(status_code=404, detail="No active run to pause")

    orch = _orchestrators.get(project_id)
    if orch:
        orch.cancel()

    _runs[project_id]["status"] = "paused"
    return {
        "status": "paused",
        "project_id": project_id,
        "iteration": run.get("iteration", 0),
        "max_iterations": run.get("max_iterations", 0),
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
