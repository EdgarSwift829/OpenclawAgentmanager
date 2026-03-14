"""WorkspaceManager - Project workspace isolation and management."""

import json
import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


def _read_json(path: Path) -> dict:
    """Read a JSON file with encoding fallback.

    Tries UTF-8 first, then UTF-8 with BOM, then falls back to
    reading raw bytes via common Japanese encodings.

    When a non-UTF-8 encoding is detected the file is re-written as
    proper UTF-8 so that subsequent reads are fast. A WARNING-level
    log message is emitted for every re-write.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        pass
    # Try UTF-8 with BOM
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        pass
    # Last resort: read bytes, decode with replacement, fix file
    logger.warning("Config file %s has encoding issues, attempting recovery", path)
    raw = path.read_bytes()
    # Try common encodings
    for enc in ("cp932", "shift_jis", "euc-jp", "latin-1"):
        try:
            text = raw.decode(enc)
            data = json.loads(text)
            # Re-write as proper UTF-8
            path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            logger.warning("Re-wrote %s as UTF-8 (original encoding: %s)", path, enc)
            return data
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    # Final fallback with replacement characters
    logger.warning("All encoding attempts failed for %s, using lossy UTF-8 decode", path)
    text = raw.decode("utf-8", errors="replace")
    data = json.loads(text)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return data


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
                loaded = Path(root.strip())
                logger.info("Loaded projects_root from settings: %s", loaded)
                return loaded
    except Exception as e:
        logger.error("Failed to load settings.yaml: %s", e)
    logger.info("Using default projects_root: %s", DEFAULT_PROJECTS_ROOT)
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
    logger.info("Saved projects_root to %s: %s", SETTINGS_PATH, new_root)


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

    def create_workspace(self, project_id: str, parent_id: str = None,
                         display_name: str = None) -> str:
        """Create isolated workspace for a project."""
        project_dir = self.projects_root / project_id
        workspace_dir = project_dir / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)

        # Initialize config
        config_path = project_dir / "config.json"
        if not config_path.exists():
            config = {
                "project_id": project_id,
                "display_name": display_name or project_id,
                "created": True,
                "agents": [],
                "status": "initialized",
                "parent_id": parent_id,
                "children": [],
            }
            config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

        # Register as child in parent's config
        if parent_id:
            self._add_child_to_parent(parent_id, project_id)

        # Initialize project memory
        memory_path = project_dir / "project_memory.md"
        if not memory_path.exists():
            memory_path.write_text(f"# Project Memory: {project_id}\n\n## Goal\n\n## Architecture\n\n## Key Modules\n\n## Coding Rules\n\n", encoding="utf-8")

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
            config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
            return
        config = _read_json(config_path)
        # Ensure children field exists
        if "children" not in config:
            config["children"] = []
        if child_id not in config["children"]:
            config["children"].append(child_id)
            config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    def _remove_child_from_parent(self, parent_id: str, child_id: str):
        """Remove a child project from the parent's config.json."""
        config_path = self.projects_root / parent_id / "config.json"
        if not config_path.exists():
            return
        config = _read_json(config_path)
        children = config.get("children", [])
        if child_id in children:
            children.remove(child_id)
            config["children"] = children
            config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    def get_project_config(self, project_id: str) -> dict:
        """Read a project's config.json, migrating old configs if needed."""
        config_path = self.projects_root / project_id / "config.json"
        if not config_path.exists():
            return {}
        config = _read_json(config_path)
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
            config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
        return config

    def update_project_config(self, project_id: str, updates: dict):
        """Merge updates into a project's config.json."""
        config_path = self.projects_root / project_id / "config.json"
        if not config_path.exists():
            return
        config = _read_json(config_path)
        config.update(updates)
        config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    def list_children(self, parent_id: str) -> list:
        """List child project IDs for a parent."""
        config = self.get_project_config(parent_id)
        return config.get("children", [])

    def update_top_level_order(self, order: list):
        """Save the display order for top-level projects."""
        order_path = self.projects_root / ".project_order.json"
        order_path.write_text(json.dumps(order, ensure_ascii=False), encoding="utf-8")

    def get_top_level_order(self) -> list:
        """Load the saved display order for top-level projects."""
        order_path = self.projects_root / ".project_order.json"
        if order_path.exists():
            try:
                return json.loads(order_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning("Failed to read project order: %s", e)
        return []

    def get_project_tree(self) -> list:
        """Return hierarchical project list with full config data."""
        all_projects = self.list_projects()
        # Apply saved top-level order
        saved_order = self.get_top_level_order()
        if saved_order:
            order_map = {pid: i for i, pid in enumerate(saved_order)}
            all_projects.sort(key=lambda pid: order_map.get(pid, len(saved_order)))
        logger.info("list_projects returned %d projects from %s: %s",
                     len(all_projects), self.projects_root, all_projects)
        tree = []
        for pid in all_projects:
            try:
                config = self.get_project_config(pid)
                tree.append({
                    "project_id": pid,
                    "display_name": config.get("display_name", pid),
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
                    "rules_must": config.get("rules_must", ""),
                    "rules_forbidden": config.get("rules_forbidden", ""),
                    "agent_profiles": config.get("agent_profiles", {}),
                })
            except Exception as e:
                logger.error("Failed to load config for project '%s': %s", pid, e)
                tree.append({
                    "project_id": pid,
                    "display_name": pid,
                    "parent_id": None,
                    "children": [],
                    "status": "initialized",
                    "goal": "",
                    "overview": "",
                    "policy": "",
                    "roadmap": "",
                    "description": "",
                    "deadline": None,
                    "tasks": [],
                })
        return tree

    def get_workspace_path(self, project_id: str) -> str:
        """Return workspace path for a project."""
        return str(self.projects_root / project_id / "workspace")

    def validate_path(self, project_id: str, target_path: str) -> bool:
        """Ensure target_path is within the project workspace (sandbox enforcement)."""
        workspace = Path(self.get_workspace_path(project_id)).resolve()
        target = Path(target_path).resolve()
        try:
            target.relative_to(workspace)
            return True
        except ValueError:
            return False

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
            json.dumps(meta, indent=2, ensure_ascii=False),
            encoding="utf-8",
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
                    meta = _read_json(meta_path)
                    meta["path"] = str(d)
                    backups.append(meta)
                else:
                    backups.append({"backup_name": d.name, "path": str(d)})
        return backups

    def restore_backup(self, project_id: str, backup_name: str) -> bool:
        """Restore a project from a named backup."""
        import shutil

        # Validate backup_name is within expected directory
        backup_dir = self.projects_root / project_id / "backups" / backup_name
        expected_parent = (self.projects_root / project_id / "backups").resolve()
        if not str(backup_dir.resolve()).startswith(str(expected_parent)):
            logger.warning("Path traversal attempt in restore_backup: %s", backup_name)
            return False
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
            logger.warning("projects_root does not exist: %s", self.projects_root)
            return []
        projects = []
        for d in self.projects_root.iterdir():
            if not d.is_dir():
                continue
            config_path = d / "config.json"
            if config_path.exists():
                projects.append(d.name)
            else:
                # Directory exists but no config.json - auto-initialize
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
                        json.dumps(config, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    # Also ensure workspace directory exists
                    (d / "workspace").mkdir(exist_ok=True)
                    projects.append(d.name)
                except Exception as e:
                    logger.warning("Failed to auto-init project dir '%s': %s", d.name, e)
        return projects

    # ------------------------------------------------------------------
    # Global Agent Profiles (cross-project, stored in config/)
    # ------------------------------------------------------------------
    _PROFILES_PATH = REPO_ROOT / "config" / "agent_profiles.json"

    def _load_profiles(self) -> dict:
        """Load global agent profiles from config/agent_profiles.json.

        Automatically seeds preset profiles from DEFAULT_AGENT_PROFILES
        if they don't exist yet.
        """
        data: dict = {}
        if self._PROFILES_PATH.exists():
            try:
                data = _read_json(self._PROFILES_PATH)
            except Exception as e:
                logger.error("Failed to load agent profiles: %s", e)

        # Auto-seed presets from DEFAULT_AGENT_PROFILES
        from mado.backend.agents.base_agent import DEFAULT_AGENT_PROFILES
        changed = False
        for role, defaults in DEFAULT_AGENT_PROFILES.items():
            role_profiles = data.get(role, [])
            has_preset = any(p.get("is_preset") for p in role_profiles)
            if not has_preset:
                preset = {
                    "id": "preset",
                    "name": defaults.get("title", role),
                    "additional_prompt": "",
                    "is_preset": True,
                    "created_from": None,
                }
                role_profiles.insert(0, preset)
                data[role] = role_profiles
                changed = True
        if changed:
            self._save_profiles(data)
        return data

    def _save_profiles(self, data: dict):
        """Persist global agent profiles to config/agent_profiles.json."""
        self._PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._PROFILES_PATH.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def get_all_profiles(self) -> dict:
        """Return all profiles grouped by role.

        Returns: { "cto": [ {id, name, additional_prompt, is_preset, base_prompt}, ... ], ... }
        """
        from mado.backend.agents.base_agent import DEFAULT_AGENT_PROFILES
        data = self._load_profiles()
        # Inject base_prompt (personality) from DEFAULT_AGENT_PROFILES into each profile
        for role, profiles in data.items():
            defaults = DEFAULT_AGENT_PROFILES.get(role, {})
            base_prompt = defaults.get("personality", "")
            for p in profiles:
                p["base_prompt"] = base_prompt
        return data

    def get_role_profiles(self, role: str) -> list:
        """Return profiles for a specific role."""
        data = self._load_profiles()
        return data.get(role, [])

    def create_profile(self, role: str, name: str, additional_prompt: str,
                       base_prompt: str = "",
                       clone_from: str | None = None) -> dict:
        """Create a new named profile under a role.

        If clone_from is given, copy that profile's additional_prompt as base.
        Returns the newly created profile dict.
        """
        import uuid

        data = self._load_profiles()
        role_profiles = data.get(role, [])

        # If cloning, find source
        if clone_from:
            source = next((p for p in role_profiles if p["id"] == clone_from), None)
            if source and not additional_prompt:
                additional_prompt = source.get("additional_prompt", "")

        profile = {
            "id": str(uuid.uuid4())[:8],
            "name": name,
            "additional_prompt": additional_prompt,
            "base_prompt": base_prompt,
            "is_preset": False,
            "created_from": clone_from,
        }
        role_profiles.append(profile)
        data[role] = role_profiles
        self._save_profiles(data)
        return profile

    def update_profile(self, role: str, profile_id: str, updates: dict) -> dict | None:
        """Update a non-preset profile's fields (name, additional_prompt).

        Returns updated profile or None if not found / is_preset.
        """
        data = self._load_profiles()
        role_profiles = data.get(role, [])
        for p in role_profiles:
            if p["id"] == profile_id:
                if p.get("is_preset"):
                    return None  # preset is immutable
                if "name" in updates:
                    p["name"] = updates["name"]
                if "additional_prompt" in updates:
                    p["additional_prompt"] = updates["additional_prompt"]
                if "base_prompt" in updates:
                    p["base_prompt"] = updates["base_prompt"]
                self._save_profiles(data)
                return p
        return None

    def delete_profile(self, role: str, profile_id: str) -> bool:
        """Delete a non-preset profile. Returns True if deleted."""
        data = self._load_profiles()
        role_profiles = data.get(role, [])
        for i, p in enumerate(role_profiles):
            if p["id"] == profile_id:
                if p.get("is_preset"):
                    return False  # cannot delete preset
                role_profiles.pop(i)
                data[role] = role_profiles
                self._save_profiles(data)
                return True
        return False


# ---------------------------------------------------------------------------
# Shared singleton instance
# ---------------------------------------------------------------------------
_shared_instance: WorkspaceManager | None = None


def get_workspace_manager() -> WorkspaceManager:
    """Return a process-wide shared WorkspaceManager instance.

    All modules that need a WorkspaceManager should call this function
    instead of constructing their own instance, so that set_projects_root()
    changes are visible everywhere.
    """
    global _shared_instance
    if _shared_instance is None:
        _shared_instance = WorkspaceManager()
    return _shared_instance
