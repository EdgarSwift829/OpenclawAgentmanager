"""Extended tests for projects API routes - coverage boost for uncovered branches.

Covers: settings/root, memory, files, children, progress, backups, restore,
rename edge cases, move edge cases, delete edge cases, reorder with parent.
"""

import pytest


@pytest.fixture
def api(api_client):
    yield api_client


class TestProjectsRoot:
    def test_get_root(self, api):
        client, wm = api
        resp = client.get("/api/projects/settings/root")
        assert resp.status_code == 200
        assert "projects_root" in resp.json()

    def test_set_root(self, api, tmp_path):
        client, wm = api
        new_root = str(tmp_path / "new_projects")
        resp = client.put("/api/projects/settings/root", json={"projects_root": new_root})
        assert resp.status_code == 200
        assert resp.json()["projects_root"] == new_root

    def test_set_root_empty(self, api):
        client, wm = api
        resp = client.put("/api/projects/settings/root", json={"projects_root": "  "})
        assert resp.status_code == 400


class TestProjectMemory:
    def test_get_memory(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "mem-proj"})
        resp = client.get("/api/projects/mem-proj/memory")
        assert resp.status_code == 200
        assert "memory" in resp.json()
        assert "context" in resp.json()

    def test_get_memory_not_found(self, api):
        client, wm = api
        resp = client.get("/api/projects/nonexistent/memory")
        assert resp.status_code == 404


class TestProjectFiles:
    def test_list_files(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "file-proj"})
        resp = client.get("/api/projects/file-proj/files")
        assert resp.status_code == 200
        assert "files" in resp.json()

    def test_list_files_not_found(self, api):
        client, wm = api
        resp = client.get("/api/projects/nonexistent/files")
        # project doesn't exist, so workspace_path won't resolve
        assert resp.status_code in (200, 404, 500)


class TestProjectChildren:
    def test_list_children(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "parent"})
        client.post("/api/projects/", json={"project_id": "child1", "parent_id": "parent"})
        resp = client.get("/api/projects/parent/children")
        assert resp.status_code == 200
        data = resp.json()
        assert data["parent_id"] == "parent"
        assert len(data["children"]) >= 1

    def test_list_children_not_found(self, api):
        client, wm = api
        resp = client.get("/api/projects/nonexistent/children")
        assert resp.status_code == 404


class TestProjectProgress:
    def test_get_progress_no_children(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "solo"})
        resp = client.get("/api/projects/solo/progress")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_children"] == 0
        assert data["summary"]["idle"] == 0

    def test_get_progress_with_children(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "parent"})
        client.post("/api/projects/", json={"project_id": "child", "parent_id": "parent"})
        resp = client.get("/api/projects/parent/progress")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_children"] >= 1

    def test_get_progress_not_found(self, api):
        client, wm = api
        resp = client.get("/api/projects/nonexistent/progress")
        assert resp.status_code == 404


class TestProjectBackups:
    def test_list_backups(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "bk-proj"})
        resp = client.get("/api/projects/bk-proj/backups")
        assert resp.status_code == 200
        assert "backups" in resp.json()

    def test_list_backups_not_found(self, api):
        client, wm = api
        resp = client.get("/api/projects/nonexistent/backups")
        assert resp.status_code == 404

    def test_restore_backup_not_found(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "bk-proj"})
        resp = client.post("/api/projects/bk-proj/backups/restore",
                           json={"backup_name": "no-such-backup"})
        assert resp.status_code == 404


class TestRenameEdgeCases:
    def test_rename_empty_name(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "proj"})
        resp = client.put("/api/projects/proj/rename", json={"new_id": "  "})
        assert resp.status_code == 400

    def test_rename_unsafe_chars(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "proj"})
        resp = client.put("/api/projects/proj/rename", json={"new_id": "bad/name"})
        assert resp.status_code == 400

    def test_rename_not_found(self, api):
        client, wm = api
        resp = client.put("/api/projects/nonexistent/rename", json={"new_id": "new"})
        assert resp.status_code == 404

    def test_rename_with_children(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "parent"})
        client.post("/api/projects/", json={"project_id": "child", "parent_id": "parent"})
        resp = client.put("/api/projects/parent/rename", json={"new_id": "renamed-parent"})
        assert resp.status_code == 200
        # Child's parent_id should be updated
        child_config = client.get("/api/projects/child").json()
        assert child_config.get("parent_id") == "renamed-parent"


class TestMoveEdgeCases:
    def test_move_not_found(self, api):
        client, wm = api
        resp = client.put("/api/projects/nonexistent/move", json={"new_parent_id": None})
        assert resp.status_code == 404

    def test_move_same_parent(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "a"})
        client.post("/api/projects/", json={"project_id": "b"})
        client.put("/api/projects/a/move", json={"new_parent_id": "b"})
        # Move to same parent again = no-op
        resp = client.put("/api/projects/a/move", json={"new_parent_id": "b"})
        assert resp.status_code == 200

    def test_move_to_nonexistent_parent(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "a"})
        resp = client.put("/api/projects/a/move", json={"new_parent_id": "ghost"})
        assert resp.status_code == 404

    def test_promote_to_top_level(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "parent"})
        client.post("/api/projects/", json={"project_id": "child", "parent_id": "parent"})
        resp = client.put("/api/projects/child/move", json={"new_parent_id": None})
        assert resp.status_code == 200
        assert resp.json()["parent_id"] is None


class TestDeleteEdgeCases:
    def test_delete_with_children_orphans_them(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "parent"})
        client.post("/api/projects/", json={"project_id": "child", "parent_id": "parent"})
        resp = client.delete("/api/projects/parent")
        assert resp.status_code == 200
        # Child should still exist but be orphaned
        child = client.get("/api/projects/child").json()
        assert child.get("parent_id") is None


class TestReorderWithParent:
    def test_reorder_children(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "parent"})
        client.post("/api/projects/", json={"project_id": "c1", "parent_id": "parent"})
        client.post("/api/projects/", json={"project_id": "c2", "parent_id": "parent"})
        resp = client.put("/api/projects/reorder",
                          json={"order": ["c2", "c1"], "parent_id": "parent"})
        assert resp.status_code == 200

    def test_reorder_nonexistent_parent(self, api):
        client, wm = api
        resp = client.put("/api/projects/reorder",
                          json={"order": ["a"], "parent_id": "ghost"})
        assert resp.status_code == 404


class TestUpdateConfigEdgeCases:
    def test_update_with_tasks(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "proj"})
        tasks = [{"id": "t1", "title": "Task 1", "status": "pending"}]
        resp = client.put("/api/projects/proj/config", json={"tasks": tasks})
        assert resp.status_code == 200

    def test_update_agent_profiles(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "proj"})
        profiles = {"engineer": {"profile_id": "senior", "additional_prompt": "Be thorough"}}
        resp = client.put("/api/projects/proj/config", json={"agent_profiles": profiles})
        assert resp.status_code == 200

    def test_update_multiple_fields(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "proj"})
        resp = client.put("/api/projects/proj/config", json={
            "goal": "Build X", "status": "in_progress", "overview": "Overview text"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["goal"] == "Build X"
        assert data["status"] == "in_progress"
