"""WorkspaceManager - Project workspace isolation and management."""

import os
import json
from pathlib import Path

PROJECTS_ROOT = Path(__file__).resolve().parents[3] / "projects"


class WorkspaceManager:
    """Create, validate, and enforce filesystem boundaries for project workspaces."""

    def __init__(self, projects_root: str = None):
        self.projects_root = Path(projects_root) if projects_root else PROJECTS_ROOT

    def create_workspace(self, project_id: str) -> str:
        """Create isolated workspace for a project."""
        project_dir = self.projects_root / project_id
        workspace_dir = project_dir / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)

        # Initialize config
        config_path = project_dir / "config.json"
        if not config_path.exists():
            config_path.write_text(json.dumps({
                "project_id": project_id,
                "created": True,
                "agents": [],
                "status": "initialized",
            }, indent=2))

        # Initialize project memory
        memory_path = project_dir / "project_memory.md"
        if not memory_path.exists():
            memory_path.write_text(f"# Project Memory: {project_id}\n\n## Goal\n\n## Architecture\n\n## Key Modules\n\n## Coding Rules\n\n")

        return str(workspace_dir)

    def get_workspace_path(self, project_id: str) -> str:
        """Return workspace path for a project."""
        return str(self.projects_root / project_id / "workspace")

    def validate_path(self, project_id: str, target_path: str) -> bool:
        """Ensure target_path is within the project workspace (sandbox enforcement)."""
        workspace = Path(self.get_workspace_path(project_id)).resolve()
        target = Path(target_path).resolve()
        return str(target).startswith(str(workspace))

    def list_projects(self) -> list:
        """List all existing projects."""
        if not self.projects_root.exists():
            return []
        return [d.name for d in self.projects_root.iterdir() if d.is_dir()]
