"""Orchestrator API routes - Start/stop/monitor orchestration runs."""

import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional

from mado.backend.orchestrator.orchestrator import Orchestrator
from mado.backend.api.routes.agents import register_session
from mado.backend.api.routes.websocket import broadcaster

router = APIRouter()

# Active orchestration runs and their orchestrator instances
_runs: dict = {}
_orchestrators: dict[str, Orchestrator] = {}


class RunCreate(BaseModel):
    project_id: str
    goal: str
    max_iterations: Optional[int] = 10


class RunStatus(BaseModel):
    project_id: str
    status: str
    iteration: int
    max_iterations: int


@router.post("/run")
async def start_run(data: RunCreate, background_tasks: BackgroundTasks):
    """Start an orchestration run for a project."""
    if data.project_id in _runs and _runs[data.project_id].get("status") == "running":
        raise HTTPException(status_code=409, detail="Run already in progress")

    _runs[data.project_id] = {
        "status": "running",
        "iteration": 0,
        "max_iterations": data.max_iterations,
        "result": None,
    }

    background_tasks.add_task(_execute_run, data.project_id, data.goal, data.max_iterations)

    return {"status": "started", "project_id": data.project_id}


async def _execute_run(project_id: str, goal: str, max_iterations: int):
    """Execute orchestration run in background with async support."""
    try:
        orch = Orchestrator(project_id)
        orch.max_iterations = max_iterations
        _orchestrators[project_id] = orch

        # Connect WebSocket broadcasting
        async def ws_event_handler(event: dict):
            await broadcaster.broadcast(project_id, event)
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
    """Stop a running orchestration with actual cancellation."""
    run = _runs.get(project_id)
    if not run or run["status"] != "running":
        raise HTTPException(status_code=404, detail="No active run to stop")

    # Signal the orchestrator to cancel
    orch = _orchestrators.get(project_id)
    if orch:
        orch.cancel()

    _runs[project_id]["status"] = "stopped"
    return {"status": "stopped", "project_id": project_id}


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
