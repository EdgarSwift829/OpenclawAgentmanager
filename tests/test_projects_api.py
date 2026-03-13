"""Tests for projects API routes, including path traversal validation."""

import pytest


@pytest.fixture
def api(api_client):
    """Alias for shared api_client fixture."""
    yield api_client


class TestCreateProject:
    def test_create_project(self, api):
        client, wm = api
        resp = client.post("/api/projects/", json={"project_id": "test-proj"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == "test-proj"
        assert data["status"] == "initialized"

    def test_create_project_duplicate(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "dup"})
        resp = client.post("/api/projects/", json={"project_id": "dup"})
        assert resp.status_code == 409

    def test_create_project_empty_id(self, api):
        client, wm = api
        resp = client.post("/api/projects/", json={"project_id": "  "})
        assert resp.status_code == 400

    def test_create_project_unsafe_chars(self, api):
        client, wm = api
        resp = client.post("/api/projects/", json={"project_id": "bad/name"})
        assert resp.status_code == 400

    def test_create_child_project(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "parent"})
        resp = client.post("/api/projects/", json={
            "project_id": "child", "parent_id": "parent"
        })
        assert resp.status_code == 200

    def test_create_child_nonexistent_parent(self, api):
        client, wm = api
        resp = client.post("/api/projects/", json={
            "project_id": "orphan", "parent_id": "no-such-parent"
        })
        assert resp.status_code == 404


class TestListProjects:
    def test_list_empty(self, api):
        client, wm = api
        resp = client.get("/api/projects/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["projects"] == []
        assert data["tree"] == []

    def test_list_returns_created(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "a"})
        client.post("/api/projects/", json={"project_id": "b"})
        resp = client.get("/api/projects/")
        assert set(resp.json()["projects"]) == {"a", "b"}


class TestGetProject:
    def test_get_existing(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "proj"})
        resp = client.get("/api/projects/proj")
        assert resp.status_code == 200
        assert resp.json()["project_id"] == "proj"

    def test_get_nonexistent(self, api):
        client, wm = api
        resp = client.get("/api/projects/nonexistent")
        assert resp.status_code == 404


class TestPathTraversal:
    """Security tests: path traversal attempts must be blocked."""

    def test_get_project_with_dotdot(self, api):
        client, wm = api
        resp = client.get("/api/projects/../etc")
        # URL normalization may resolve ../ before reaching the handler,
        # so either 400 (validation) or 404 (not found) is acceptable
        assert resp.status_code in (400, 404)

    def test_get_project_with_slash(self, api):
        client, wm = api
        # URL-encoded forward slash in project_id
        resp = client.get("/api/projects/a%2F..%2Fetc")
        # FastAPI may handle this differently, but should not succeed
        assert resp.status_code in (400, 404, 422)

    def test_delete_with_traversal(self, api):
        client, wm = api
        resp = client.delete("/api/projects/..%2F..%2Fetc")
        assert resp.status_code in (400, 404, 422)

    def test_config_update_with_traversal(self, api):
        client, wm = api
        resp = client.put("/api/projects/../evil/config", json={"goal": "hack"})
        assert resp.status_code in (400, 404, 422)


class TestUpdateConfig:
    def test_update_goal(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "proj"})
        resp = client.put("/api/projects/proj/config", json={"goal": "Build X"})
        assert resp.status_code == 200
        assert resp.json()["goal"] == "Build X"

    def test_update_no_fields(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "proj"})
        resp = client.put("/api/projects/proj/config", json={})
        assert resp.status_code == 400

    def test_update_nonexistent(self, api):
        client, wm = api
        resp = client.put("/api/projects/nope/config", json={"goal": "X"})
        assert resp.status_code == 404


class TestRenameProject:
    def test_rename(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "old"})
        resp = client.put("/api/projects/old/rename", json={"new_id": "new"})
        assert resp.status_code == 200
        assert resp.json()["new_id"] == "new"
        # Old should not exist
        assert client.get("/api/projects/old").status_code == 404
        assert client.get("/api/projects/new").status_code == 200

    def test_rename_to_existing(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "a"})
        client.post("/api/projects/", json={"project_id": "b"})
        resp = client.put("/api/projects/a/rename", json={"new_id": "b"})
        assert resp.status_code == 409


class TestDeleteProject:
    def test_delete(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "del-me"})
        resp = client.delete("/api/projects/del-me")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == "del-me"
        assert client.get("/api/projects/del-me").status_code == 404

    def test_delete_nonexistent(self, api):
        client, wm = api
        resp = client.delete("/api/projects/nope")
        assert resp.status_code == 404

    def test_delete_unlinks_from_parent(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "parent"})
        client.post("/api/projects/", json={"project_id": "child", "parent_id": "parent"})
        client.delete("/api/projects/child")
        parent = client.get("/api/projects/parent").json()
        assert "child" not in parent.get("children", [])


class TestMoveProject:
    def test_move_to_parent(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "a"})
        client.post("/api/projects/", json={"project_id": "b"})
        resp = client.put("/api/projects/b/move", json={"new_parent_id": "a"})
        assert resp.status_code == 200
        assert resp.json()["parent_id"] == "a"

    def test_move_self_parent(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "x"})
        resp = client.put("/api/projects/x/move", json={"new_parent_id": "x"})
        assert resp.status_code == 400

    def test_move_circular(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "a"})
        client.post("/api/projects/", json={"project_id": "b", "parent_id": "a"})
        # Try to make a the child of b (circular)
        resp = client.put("/api/projects/a/move", json={"new_parent_id": "b"})
        assert resp.status_code == 400


class TestReorderProjects:
    def test_reorder_top_level(self, api):
        client, wm = api
        client.post("/api/projects/", json={"project_id": "a"})
        client.post("/api/projects/", json={"project_id": "b"})
        resp = client.put("/api/projects/reorder", json={"order": ["b", "a"]})
        assert resp.status_code == 200
