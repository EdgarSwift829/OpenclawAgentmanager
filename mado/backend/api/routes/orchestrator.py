"""Orchestrator API routes - Start/stop/monitor orchestration runs."""

import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional

from mado.backend.orchestrator.orchestrator import Orchestrator
from mado.backend.api.routes.agents import register_session

router = APIRouter()

# Active orchestration runs
_runs: dict = {}


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
    """Execute orchestration run in background."""
    try:
        orch = Orchestrator(project_id)
        orch.max_iterations = max_iterations

        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, orch.run, goal)

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


@router.get("/run/{project_id}")
async def get_run_status(project_id: str):
    """Get the status of an orchestration run."""
    run = _runs.get(project_id)
    if not run:
        raise HTTPException(status_code=404, detail="No run found for this project")
    return run


@router.post("/run/{project_id}/stop")
async def stop_run(project_id: str):
    """Stop a running orchestration."""
    run = _runs.get(project_id)
    if not run or run["status"] != "running":
        raise HTTPException(status_code=404, detail="No active run to stop")
    _runs[project_id]["status"] = "stopped"
    return {"status": "stopped", "project_id": project_id}


@router.get("/runs")
async def list_runs():
    """List all orchestration runs."""
    return {"runs": {k: {"status": v["status"], "iteration": v["iteration"]} for k, v in _runs.items()}}
