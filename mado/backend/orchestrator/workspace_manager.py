"""WorkspaceManager - Project workspace isolation and management."""

import os
import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SETTINGS_PATH = REPO_ROOT / "config" / "settings.yaml"
DEFAULT_PROJECTS_ROOT = REPO_ROOT / "projects"


def _load_projects_root() -> Path:
    """Load projects_root from config/settings.yaml, fall back to default."""
    try:
        if SETTINGS_PATH.exists():
            data = yaml.safe_load(SETTINGS_PATH.read_text(encoding="utf-8")) or {}
            root = data.get("projects_root", "")
            if root and root.strip():
                return Path(root.strip())
    except Exception:
        pass
    return DEFAULT_PROJECTS_ROOT


def _save_projects_root(new_root: str):
    """Persist projects_root to config/settings.yaml."""
    data: dict = {}
    try:
        if SETTINGS_PATH.exists():
            data = yaml.safe_load(SETTINGS_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        data = {}
    data["projects_root"] = new_root
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )


class WorkspaceManager:
    """Create, validate, and enforce filesystem boundaries for project workspaces."""

    def __init__(self, projects_root: str = None):
        if projects_root:
            self.projects_root = Path(projects_root)
        else:
            self.projects_root = _load_projects_root()

    def reload_root(self):
        """Re-read projects_root from settings file."""
        self.projects_root = _load_projects_root()

    def get_projects_root(self) -> str:
        """Return current projects root path."""
        return str(self.projects_root)

    def set_projects_root(self, new_root: str):
        """Update projects root path and persist to config."""
        path = Path(new_root)
        path.mkdir(parents=True, exist_ok=True)
        _save_projects_root(new_root)
        self.projects_root = path

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
