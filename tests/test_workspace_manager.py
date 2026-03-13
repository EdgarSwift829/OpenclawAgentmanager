"""Tests for WorkspaceManager core functionality."""

import json
from pathlib import Path

import pytest

from mado.backend.orchestrator.workspace_manager import WorkspaceManager


class TestWorkspaceCreation:
    def test_create_workspace_creates_dirs(self, tmp_path):
        wm = WorkspaceManager(str(tmp_path))
        result = wm.create_workspace("my-project")
        workspace = Path(result)
        assert workspace.exists()
        assert workspace.name == "workspace"
        assert (tmp_path / "my-project" / "config.json").exists()

    def test_create_workspace_initializes_config(self, tmp_path):
        wm = WorkspaceManager(str(tmp_path))
        wm.create_workspace("proj")
        config = json.loads((tmp_path / "proj" / "config.json").read_text("utf-8"))
        assert config["project_id"] == "proj"
        assert config["status"] == "initialized"
        assert config["parent_id"] is None

    def test_create_workspace_with_display_name(self, tmp_path):
        wm = WorkspaceManager(str(tmp_path))
        wm.create_workspace("proj", display_name="My Project")
        config = json.loads((tmp_path / "proj" / "config.json").read_text("utf-8"))
        assert config["display_name"] == "My Project"

    def test_create_workspace_idempotent(self, tmp_path):
        wm = WorkspaceManager(str(tmp_path))
        wm.create_workspace("proj")
        # Write something into workspace
        (tmp_path / "proj" / "workspace" / "file.txt").write_text("hello")
        # Create again should not overwrite config
        wm.create_workspace("proj")
        assert (tmp_path / "proj" / "workspace" / "file.txt").read_text() == "hello"

    def test_create_workspace_initializes_memory(self, tmp_path):
        wm = WorkspaceManager(str(tmp_path))
        wm.create_workspace("proj")
        memory = tmp_path / "proj" / "project_memory.md"
        assert memory.exists()
        assert "Project Memory" in memory.read_text("utf-8")


class TestParentChild:
    def test_create_child_project(self, tmp_path):
        wm = WorkspaceManager(str(tmp_path))
        wm.create_workspace("parent")
        wm.create_workspace("child", parent_id="parent")

        child_config = wm.get_project_config("child")
        assert child_config["parent_id"] == "parent"

        parent_config = wm.get_project_config("parent")
        assert "child" in parent_config["children"]

    def test_list_children(self, tmp_path):
        wm = WorkspaceManager(str(tmp_path))
        wm.create_workspace("parent")
        wm.create_workspace("c1", parent_id="parent")
        wm.create_workspace("c2", parent_id="parent")
        assert set(wm.list_children("parent")) == {"c1", "c2"}

    def test_remove_child_from_parent(self, tmp_path):
        wm = WorkspaceManager(str(tmp_path))
        wm.create_workspace("parent")
        wm.create_workspace("child", parent_id="parent")
        wm._remove_child_from_parent("parent", "child")
        assert "child" not in wm.get_project_config("parent").get("children", [])

    def test_add_child_to_nonexistent_parent_auto_creates(self, tmp_path):
        wm = WorkspaceManager(str(tmp_path))
        wm.create_workspace("child", parent_id="auto-parent")
        config = wm.get_project_config("auto-parent")
        assert "child" in config["children"]


class TestProjectConfig:
    def test_get_project_config(self, tmp_path):
        wm = WorkspaceManager(str(tmp_path))
        wm.create_workspace("proj")
        config = wm.get_project_config("proj")
        assert config["project_id"] == "proj"

    def test_get_project_config_nonexistent(self, tmp_path):
        wm = WorkspaceManager(str(tmp_path))
        assert wm.get_project_config("nope") == {}

    def test_update_project_config(self, tmp_path):
        wm = WorkspaceManager(str(tmp_path))
        wm.create_workspace("proj")
        wm.update_project_config("proj", {"goal": "Build something"})
        config = wm.get_project_config("proj")
        assert config["goal"] == "Build something"

    def test_config_migration_adds_missing_fields(self, tmp_path):
        """Old configs without parent_id/children/goal should be migrated."""
        wm = WorkspaceManager(str(tmp_path))
        project_dir = tmp_path / "old-proj"
        project_dir.mkdir()
        (project_dir / "config.json").write_text(
            json.dumps({"project_id": "old-proj", "status": "initialized"}),
            encoding="utf-8",
        )
        config = wm.get_project_config("old-proj")
        assert config["parent_id"] is None
        assert config["children"] == []
        assert config["goal"] == ""


class TestListProjects:
    def test_list_projects_empty(self, tmp_path):
        wm = WorkspaceManager(str(tmp_path))
        assert wm.list_projects() == []

    def test_list_projects_returns_all(self, tmp_path):
        wm = WorkspaceManager(str(tmp_path))
        wm.create_workspace("a")
        wm.create_workspace("b")
        projects = wm.list_projects()
        assert set(projects) == {"a", "b"}

    def test_list_projects_auto_initializes_dirs(self, tmp_path):
        """Directories without config.json are auto-initialized."""
        wm = WorkspaceManager(str(tmp_path))
        (tmp_path / "bare-dir").mkdir()
        projects = wm.list_projects()
        assert "bare-dir" in projects
        assert (tmp_path / "bare-dir" / "config.json").exists()

    def test_list_projects_nonexistent_root(self, tmp_path):
        wm = WorkspaceManager(str(tmp_path / "nonexistent"))
        assert wm.list_projects() == []


class TestProjectTree:
    def test_get_project_tree(self, tmp_path):
        wm = WorkspaceManager(str(tmp_path))
        wm.create_workspace("proj", display_name="My Project")
        tree = wm.get_project_tree()
        assert len(tree) == 1
        assert tree[0]["project_id"] == "proj"
        assert tree[0]["display_name"] == "My Project"

    def test_project_tree_includes_hierarchy(self, tmp_path):
        wm = WorkspaceManager(str(tmp_path))
        wm.create_workspace("parent")
        wm.create_workspace("child", parent_id="parent")
        tree = wm.get_project_tree()
        parent_node = next(t for t in tree if t["project_id"] == "parent")
        assert "child" in parent_node["children"]


class TestPathValidation:
    def test_validate_path_within_workspace(self, tmp_path):
        wm = WorkspaceManager(str(tmp_path))
        wm.create_workspace("proj")
        workspace = tmp_path / "proj" / "workspace"
        assert wm.validate_path("proj", str(workspace / "file.txt")) is True

    def test_validate_path_outside_workspace(self, tmp_path):
        wm = WorkspaceManager(str(tmp_path))
        wm.create_workspace("proj")
        assert wm.validate_path("proj", "/etc/passwd") is False

    def test_validate_path_traversal(self, tmp_path):
        wm = WorkspaceManager(str(tmp_path))
        wm.create_workspace("proj")
        workspace = tmp_path / "proj" / "workspace"
        assert wm.validate_path("proj", str(workspace / ".." / ".." / "etc")) is False


class TestBackup:
    def test_backup_and_restore(self, tmp_path):
        wm = WorkspaceManager(str(tmp_path))
        wm.create_workspace("proj")
        # Write a file in workspace
        ws = tmp_path / "proj" / "workspace"
        (ws / "code.py").write_text("print('hello')")

        backup_path = wm.backup_project("proj", "test-backup")
        assert Path(backup_path).exists()

        # Modify workspace
        (ws / "code.py").write_text("print('changed')")

        # Restore
        backups = wm.list_backups("proj")
        assert len(backups) == 1
        assert wm.restore_backup("proj", backups[0]["backup_name"]) is True
        assert (ws / "code.py").read_text() == "print('hello')"

    def test_backup_nonexistent_project(self, tmp_path):
        wm = WorkspaceManager(str(tmp_path))
        with pytest.raises(FileNotFoundError):
            wm.backup_project("nonexistent")

    def test_restore_nonexistent_backup(self, tmp_path):
        wm = WorkspaceManager(str(tmp_path))
        wm.create_workspace("proj")
        assert wm.restore_backup("proj", "no-such-backup") is False

    def test_restore_path_traversal_blocked(self, tmp_path):
        wm = WorkspaceManager(str(tmp_path))
        wm.create_workspace("proj")
        assert wm.restore_backup("proj", "../../etc") is False


class TestTopLevelOrder:
    def test_update_and_get_order(self, tmp_path):
        wm = WorkspaceManager(str(tmp_path))
        wm.update_top_level_order(["b", "a", "c"])
        assert wm.get_top_level_order() == ["b", "a", "c"]

    def test_get_order_default_empty(self, tmp_path):
        wm = WorkspaceManager(str(tmp_path))
        assert wm.get_top_level_order() == []
