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

    def create_workspace(self, project_id: str, parent_id: str = None) -> str:
        """Create isolated workspace for a project."""
        project_dir = self.projects_root / project_id
        workspace_dir = project_dir / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)

        # Initialize config
        config_path = project_dir / "config.json"
        if not config_path.exists():
            config = {
                "project_id": project_id,
                "created": True,
                "agents": [],
                "status": "initialized",
                "parent_id": parent_id,
                "children": [],
            }
            config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False))

        # Register as child in parent's config
        if parent_id:
            self._add_child_to_parent(parent_id, project_id)

        # Initialize project memory
        memory_path = project_dir / "project_memory.md"
        if not memory_path.exists():
            memory_path.write_text(f"# Project Memory: {project_id}\n\n## Goal\n\n## Architecture\n\n## Key Modules\n\n## Coding Rules\n\n")

        return str(workspace_dir)

    def _add_child_to_parent(self, parent_id: str, child_id: str):
        """Register a child project in the parent's config.json."""
        config_path = self.projects_root / parent_id / "config.json"
        if not config_path.exists():
            # Auto-create minimal config for parent
            config = {
                "project_id": parent_id,
                "status": "initialized",
                "parent_id": None,
                "children": [child_id],
                "goal": "",
            }
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False))
            return
        config = json.loads(config_path.read_text(encoding="utf-8"))
        # Ensure children field exists
        if "children" not in config:
            config["children"] = []
        if child_id not in config["children"]:
            config["children"].append(child_id)
            config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False))

    def _remove_child_from_parent(self, parent_id: str, child_id: str):
        """Remove a child project from the parent's config.json."""
        config_path = self.projects_root / parent_id / "config.json"
        if not config_path.exists():
            return
        config = json.loads(config_path.read_text(encoding="utf-8"))
        children = config.get("children", [])
        if child_id in children:
            children.remove(child_id)
            config["children"] = children
            config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False))

    def get_project_config(self, project_id: str) -> dict:
        """Read a project's config.json, migrating old configs if needed."""
        config_path = self.projects_root / project_id / "config.json"
        if not config_path.exists():
            return {}
        config = json.loads(config_path.read_text(encoding="utf-8"))
        # Migrate old configs missing required fields
        migrated = False
        for key, default in [
            ("parent_id", None),
            ("children", []),
            ("goal", ""),
        ]:
            if key not in config:
                config[key] = default
                migrated = True
        if migrated:
            config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False))
        return config

    def update_project_config(self, project_id: str, updates: dict):
        """Merge updates into a project's config.json."""
        config_path = self.projects_root / project_id / "config.json"
        if not config_path.exists():
            return
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config.update(updates)
        config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False))

    def list_children(self, parent_id: str) -> list:
        """List child project IDs for a parent."""
        config = self.get_project_config(parent_id)
        return config.get("children", [])

    def get_project_tree(self) -> list:
        """Return hierarchical project list with full config data."""
        all_projects = self.list_projects()
        tree = []
        for pid in all_projects:
            config = self.get_project_config(pid)
            tree.append({
                "project_id": pid,
                "parent_id": config.get("parent_id"),
                "children": config.get("children", []),
                "status": config.get("status", "initialized"),
                "goal": config.get("goal", ""),
                "overview": config.get("overview", ""),
                "policy": config.get("policy", ""),
                "roadmap": config.get("roadmap", ""),
                "description": config.get("description", ""),
                "deadline": config.get("deadline"),
                "tasks": config.get("tasks", []),
            })
        return tree

    def get_workspace_path(self, project_id: str) -> str:
        """Return workspace path for a project."""
        return str(self.projects_root / project_id / "workspace")

    def validate_path(self, project_id: str, target_path: str) -> bool:
        """Ensure target_path is within the project workspace (sandbox enforcement)."""
        workspace = Path(self.get_workspace_path(project_id)).resolve()
        target = Path(target_path).resolve()
        return str(target).startswith(str(workspace))

    def backup_project(self, project_id: str, reason: str = "manual") -> str:
        """Create a timestamped backup of a project's workspace and config.

        Backups are stored under <project_dir>/backups/<timestamp>_<reason>/
        Returns the backup directory path.
        """
        import shutil
        from datetime import datetime

        project_dir = self.projects_root / project_id
        if not project_dir.exists():
            raise FileNotFoundError(f"Project not found: {project_id}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_reason = reason.replace(" ", "_").replace("/", "_")[:20]
        backup_name = f"{timestamp}_{safe_reason}"
        backup_dir = project_dir / "backups" / backup_name
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Backup config.json
        config_path = project_dir / "config.json"
        if config_path.exists():
            shutil.copy2(str(config_path), str(backup_dir / "config.json"))

        # Backup workspace directory
        workspace_dir = project_dir / "workspace"
        if workspace_dir.exists():
            shutil.copytree(
                str(workspace_dir),
                str(backup_dir / "workspace"),
                dirs_exist_ok=True,
            )

        # Backup project memory
        memory_path = project_dir / "project_memory.md"
        if memory_path.exists():
            shutil.copy2(str(memory_path), str(backup_dir / "project_memory.md"))

        # Write backup metadata
        meta = {
            "project_id": project_id,
            "reason": reason,
            "timestamp": timestamp,
            "backup_name": backup_name,
        }
        (backup_dir / "backup_meta.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False)
        )

        return str(backup_dir)

    def list_backups(self, project_id: str) -> list:
        """List available backups for a project, newest first."""
        backup_root = self.projects_root / project_id / "backups"
        if not backup_root.exists():
            return []
        backups = []
        for d in sorted(backup_root.iterdir(), reverse=True):
            if d.is_dir():
                meta_path = d / "backup_meta.json"
                if meta_path.exists():
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    meta["path"] = str(d)
                    backups.append(meta)
                else:
                    backups.append({"backup_name": d.name, "path": str(d)})
        return backups

    def restore_backup(self, project_id: str, backup_name: str) -> bool:
        """Restore a project from a named backup."""
        import shutil

        backup_dir = self.projects_root / project_id / "backups" / backup_name
        if not backup_dir.exists():
            return False

        project_dir = self.projects_root / project_id

        # Restore config.json
        backup_config = backup_dir / "config.json"
        if backup_config.exists():
            shutil.copy2(str(backup_config), str(project_dir / "config.json"))

        # Restore workspace
        backup_workspace = backup_dir / "workspace"
        if backup_workspace.exists():
            target_workspace = project_dir / "workspace"
            if target_workspace.exists():
                shutil.rmtree(str(target_workspace))
            shutil.copytree(str(backup_workspace), str(target_workspace))

        # Restore project memory
        backup_memory = backup_dir / "project_memory.md"
        if backup_memory.exists():
            shutil.copy2(str(backup_memory), str(project_dir / "project_memory.md"))

        return True

    def list_projects(self) -> list:
        """List all existing projects.

        Directories with config.json are listed directly.
        Directories without config.json but with a workspace/ subdirectory
        are auto-initialized (config.json created) and then listed.
        """
        if not self.projects_root.exists():
            return []
        projects = []
        for d in self.projects_root.iterdir():
            if not d.is_dir():
                continue
            config_path = d / "config.json"
            if config_path.exists():
                projects.append(d.name)
            elif (d / "workspace").exists() or any(d.iterdir()):
                # Directory exists with content but no config.json - auto-initialize
                try:
                    config = {
                        "project_id": d.name,
                        "created": True,
                        "agents": [],
                        "status": "initialized",
                        "parent_id": None,
                        "children": [],
                    }
                    config_path.write_text(
                        json.dumps(config, indent=2, ensure_ascii=False)
                    )
                    # Also ensure workspace directory exists
                    (d / "workspace").mkdir(exist_ok=True)
                    projects.append(d.name)
                except Exception:
                    # If we can't write config, skip this directory
                    pass
        return projects
