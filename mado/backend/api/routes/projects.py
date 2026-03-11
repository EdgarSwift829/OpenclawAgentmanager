"""Project management API routes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from mado.backend.orchestrator.workspace_manager import WorkspaceManager

router = APIRouter()
workspace_manager = WorkspaceManager()


class ProjectCreate(BaseModel):
    project_id: str
    goal: Optional[str] = ""


class ProjectResponse(BaseModel):
    project_id: str
    status: str
    workspace_path: str


class ProjectsRootUpdate(BaseModel):
    projects_root: str


@router.get("/")
async def list_projects():
    """List all projects."""
    projects = workspace_manager.list_projects()
    return {"projects": projects, "projects_root": workspace_manager.get_projects_root()}


@router.get("/settings/root")
async def get_projects_root():
    """Get current projects root path."""
    return {"projects_root": workspace_manager.get_projects_root()}


@router.put("/settings/root")
async def set_projects_root(data: ProjectsRootUpdate):
    """Update projects root path."""
    new_root = data.projects_root.strip()
    if not new_root:
        raise HTTPException(status_code=400, detail="Path cannot be empty")
    try:
        workspace_manager.set_projects_root(new_root)
        projects = workspace_manager.list_projects()
        return {"projects_root": workspace_manager.get_projects_root(), "projects": projects}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/", response_model=ProjectResponse)
async def create_project(data: ProjectCreate):
    """Create a new project workspace."""
    workspace_path = workspace_manager.create_workspace(data.project_id)
    return ProjectResponse(
        project_id=data.project_id,
        status="initialized",
        workspace_path=workspace_path,
    )


@router.get("/{project_id}")
async def get_project(project_id: str):
    """Get project details."""
    import json
    from pathlib import Path

    config_path = Path(workspace_manager.projects_root) / project_id / "config.json"
    if not config_path.exists():
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    config = json.loads(config_path.read_text())
    return config


@router.delete("/{project_id}")
async def delete_project(project_id: str):
    """Delete a project (removes workspace)."""
    import shutil
    from pathlib import Path

    project_path = Path(workspace_manager.projects_root) / project_id
    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    shutil.rmtree(project_path)
    return {"deleted": project_id}


@router.get("/{project_id}/memory")
async def get_project_memory(project_id: str):
    """Get project memory contents."""
    from mado.backend.memory.project_memory import ProjectMemory
    from pathlib import Path

    project_path = Path(workspace_manager.projects_root) / project_id
    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    memory = ProjectMemory(str(project_path))
    return {"memory": memory.load(), "context": memory.get_context()}


@router.get("/{project_id}/files")
async def list_project_files(project_id: str):
    """List files in project workspace."""
    from mado.backend.tools.file_tools import FileTools

    workspace_path = workspace_manager.get_workspace_path(project_id)
    tools = FileTools(workspace_path)
    try:
        files = tools.list_dir(".")
    except ValueError:
        files = []
    return {"files": files}
