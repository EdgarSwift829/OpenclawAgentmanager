"""Project management API routes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from mado.backend.orchestrator.workspace_manager import WorkspaceManager

router = APIRouter()
workspace_manager = WorkspaceManager()


class ProjectCreate(BaseModel):
    project_id: str
    goal: Optional[str] = ""
    parent_id: Optional[str] = None


class ProjectResponse(BaseModel):
    project_id: str
    status: str
    workspace_path: str


class ProjectsRootUpdate(BaseModel):
    projects_root: str


@router.get("/")
async def list_projects():
    """List all projects with hierarchy info."""
    tree = workspace_manager.get_project_tree()
    # Also return flat list for backward compatibility
    projects = [p["project_id"] for p in tree]
    return {
        "projects": projects,
        "tree": tree,
        "projects_root": workspace_manager.get_projects_root(),
    }


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
    """Create a new project workspace (optionally as a child of parent_id)."""
    from pathlib import Path

    # Validate project_id
    pid = data.project_id.strip()
    if not pid:
        raise HTTPException(status_code=400, detail="Project ID cannot be empty")

    # Reject IDs with path-unsafe characters
    unsafe_chars = set('/\\:*?"<>|')
    if any(c in unsafe_chars for c in pid):
        raise HTTPException(status_code=400, detail=f"Project ID contains invalid characters: {pid}")

    # Ensure projects root exists and is writable
    projects_root = Path(workspace_manager.projects_root)
    try:
        projects_root.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        raise HTTPException(status_code=500, detail=f"Cannot write to projects folder: {projects_root}")

    # Check for duplicate
    project_path = projects_root / pid
    if project_path.exists():
        raise HTTPException(status_code=409, detail=f"Project already exists: {pid}")

    if data.parent_id:
        parent_path = projects_root / data.parent_id
        if not parent_path.exists():
            raise HTTPException(status_code=404, detail=f"Parent project not found: {data.parent_id}")
        parent_config = parent_path / "config.json"
        if not parent_config.exists():
            raise HTTPException(status_code=404, detail=f"Parent project config missing: {data.parent_id}")

    try:
        workspace_path = workspace_manager.create_workspace(pid, parent_id=data.parent_id)
    except PermissionError:
        raise HTTPException(status_code=500, detail=f"Permission denied creating project workspace")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create project: {e}")

    return ProjectResponse(
        project_id=pid,
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


class TaskItem(BaseModel):
    id: str
    title: str
    description: Optional[str] = ""
    status: Optional[str] = "pending"  # pending | in_progress | done
    deadline: Optional[str] = None  # ISO date string
    priority: Optional[str] = "medium"  # low | medium | high


class ProjectConfigUpdate(BaseModel):
    status: Optional[str] = None
    goal: Optional[str] = None
    # Parent project fields
    overview: Optional[str] = None
    policy: Optional[str] = None
    roadmap: Optional[str] = None
    # Child project fields
    description: Optional[str] = None
    deadline: Optional[str] = None
    tasks: Optional[List[TaskItem]] = None


@router.put("/{project_id}/config")
async def update_project_config(project_id: str, data: ProjectConfigUpdate):
    """Update project config fields."""
    from pathlib import Path

    project_path = Path(workspace_manager.projects_root) / project_id
    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    raw = data.model_dump(exclude_none=True)
    # Convert tasks (list of TaskItem) to plain dicts for JSON
    if "tasks" in raw:
        raw["tasks"] = [t if isinstance(t, dict) else t for t in raw["tasks"]]
    if not raw:
        raise HTTPException(status_code=400, detail="No fields to update")

    workspace_manager.update_project_config(project_id, raw)
    return workspace_manager.get_project_config(project_id)


class ProjectRename(BaseModel):
    new_id: str


@router.put("/{project_id}/rename")
async def rename_project(project_id: str, data: ProjectRename):
    """Rename a project."""
    from pathlib import Path

    new_id = data.new_id.strip()
    if not new_id:
        raise HTTPException(status_code=400, detail="New name cannot be empty")

    old_path = Path(workspace_manager.projects_root) / project_id
    new_path = Path(workspace_manager.projects_root) / new_id

    if not old_path.exists():
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    if new_path.exists():
        raise HTTPException(status_code=409, detail=f"Project already exists: {new_id}")

    # Read config before rename to get parent/children info
    import json
    old_config_path = old_path / "config.json"
    old_config = {}
    if old_config_path.exists():
        old_config = json.loads(old_config_path.read_text(encoding="utf-8"))

    old_path.rename(new_path)

    # Update config.json
    config_path = new_path / "config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["project_id"] = new_id
        config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False))

    # Update parent's children list
    parent_id = old_config.get("parent_id")
    if parent_id:
        workspace_manager._remove_child_from_parent(parent_id, project_id)
        workspace_manager._add_child_to_parent(parent_id, new_id)

    # Update children's parent_id references
    for child_id in old_config.get("children", []):
        child_config = workspace_manager.get_project_config(child_id)
        if child_config.get("parent_id") == project_id:
            workspace_manager.update_project_config(child_id, {"parent_id": new_id})

    return {"old_id": project_id, "new_id": new_id}


@router.delete("/{project_id}")
async def delete_project(project_id: str):
    """Delete a project (removes workspace). Unlinks from parent if applicable."""
    import shutil
    from pathlib import Path

    project_path = Path(workspace_manager.projects_root) / project_id
    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    # Remove from parent's children list
    config = workspace_manager.get_project_config(project_id)
    parent_id = config.get("parent_id")
    if parent_id:
        workspace_manager._remove_child_from_parent(parent_id, project_id)

    # Orphan children (set their parent_id to None)
    for child_id in config.get("children", []):
        workspace_manager.update_project_config(child_id, {"parent_id": None})

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


@router.get("/{project_id}/children")
async def list_children(project_id: str):
    """List child projects with their status/progress."""
    from pathlib import Path

    project_path = Path(workspace_manager.projects_root) / project_id
    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    children_ids = workspace_manager.list_children(project_id)
    children = []
    for cid in children_ids:
        config = workspace_manager.get_project_config(cid)
        children.append({
            "project_id": cid,
            "status": config.get("status", "initialized"),
            "goal": config.get("goal", ""),
            "children": config.get("children", []),
        })
    return {"parent_id": project_id, "children": children}


@router.get("/{project_id}/progress")
async def get_project_progress(project_id: str):
    """Get aggregated progress for a parent project including all children."""
    from pathlib import Path

    project_path = Path(workspace_manager.projects_root) / project_id
    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    config = workspace_manager.get_project_config(project_id)
    children_ids = config.get("children", [])

    # Gather run statuses from orchestrator
    from mado.backend.api.routes.orchestrator import _runs

    child_progress = []
    for cid in children_ids:
        child_config = workspace_manager.get_project_config(cid)
        run = _runs.get(cid, {})
        child_progress.append({
            "project_id": cid,
            "config_status": child_config.get("status", "initialized"),
            "run_status": run.get("status", "idle"),
            "iteration": run.get("iteration", 0),
            "max_iterations": run.get("max_iterations", 0),
            "error": run.get("error"),
        })

    # Summary
    total = len(child_progress)
    running = sum(1 for c in child_progress if c["run_status"] == "running")
    completed = sum(1 for c in child_progress if c["run_status"] == "completed")
    errored = sum(1 for c in child_progress if c["run_status"] == "error")

    return {
        "project_id": project_id,
        "total_children": total,
        "summary": {
            "running": running,
            "completed": completed,
            "error": errored,
            "idle": total - running - completed - errored,
        },
        "children": child_progress,
    }


@router.get("/{project_id}/backups")
async def list_backups(project_id: str):
    """List available backups for a project."""
    from pathlib import Path

    project_path = Path(workspace_manager.projects_root) / project_id
    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    backups = workspace_manager.list_backups(project_id)
    return {"project_id": project_id, "backups": backups}


class BackupRestore(BaseModel):
    backup_name: str


@router.post("/{project_id}/backups/restore")
async def restore_backup(project_id: str, data: BackupRestore):
    """Restore a project from a named backup."""
    from pathlib import Path

    project_path = Path(workspace_manager.projects_root) / project_id
    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    success = workspace_manager.restore_backup(project_id, data.backup_name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Backup not found: {data.backup_name}")

    return {"status": "restored", "project_id": project_id, "backup_name": data.backup_name}
