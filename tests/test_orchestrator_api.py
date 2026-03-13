"""Tests for orchestrator API routes."""


import pytest


@pytest.fixture
def api(orchestrator_api_client):
    """Alias for shared orchestrator_api_client fixture."""
    yield orchestrator_api_client


class TestStartRun:
    def test_start_run(self, api):
        client, wm = api
        wm.create_workspace("proj")
        resp = client.post("/api/orchestrator/run", json={
            "project_id": "proj",
            "goal": "Build something",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "started"

    def test_start_run_duplicate(self, api):
        """Cannot start a run when one is already running."""
        client, wm = api
        import mado.backend.api.routes.orchestrator as orch_mod
        wm.create_workspace("proj")
        orch_mod._runs["proj"] = {"status": "running", "iteration": 0, "max_iterations": 30}
        resp = client.post("/api/orchestrator/run", json={
            "project_id": "proj",
            "goal": "test",
        })
        assert resp.status_code == 409

    def test_start_run_custom_max_iterations(self, api):
        client, wm = api
        import mado.backend.api.routes.orchestrator as orch_mod
        wm.create_workspace("proj")
        resp = client.post("/api/orchestrator/run", json={
            "project_id": "proj",
            "goal": "test",
            "max_iterations": 10,
        })
        assert resp.status_code == 200
        assert orch_mod._runs["proj"]["max_iterations"] == 10

    def test_child_cannot_start_without_parent(self, api):
        """Child project cannot start if parent is not running."""
        client, wm = api
        wm.create_workspace("parent")
        wm.create_workspace("child", parent_id="parent")
        resp = client.post("/api/orchestrator/run", json={
            "project_id": "child",
            "goal": "test",
        })
        assert resp.status_code == 409
        assert "parent" in resp.json()["detail"].lower()

    def test_child_can_start_when_parent_running(self, api):
        """Child project can start when parent is running."""
        client, wm = api
        import mado.backend.api.routes.orchestrator as orch_mod
        wm.create_workspace("parent")
        wm.create_workspace("child", parent_id="parent")
        orch_mod._runs["parent"] = {"status": "running", "iteration": 1, "max_iterations": 30}
        resp = client.post("/api/orchestrator/run", json={
            "project_id": "child",
            "goal": "do work",
        })
        assert resp.status_code == 200


class TestGetRunStatus:
    def test_get_status(self, api):
        client, wm = api
        import mado.backend.api.routes.orchestrator as orch_mod
        orch_mod._runs["proj"] = {
            "status": "completed",
            "iteration": 5,
            "max_iterations": 30,
            "result": "done",
        }
        resp = client.get("/api/orchestrator/run/proj")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["iteration"] == 5

    def test_get_status_not_found(self, api):
        client, wm = api
        resp = client.get("/api/orchestrator/run/nonexistent")
        assert resp.status_code == 404


class TestStopRun:
    def test_stop_running(self, api):
        client, wm = api
        import mado.backend.api.routes.orchestrator as orch_mod
        wm.create_workspace("proj")
        orch_mod._runs["proj"] = {"status": "running", "iteration": 3, "max_iterations": 30}
        resp = client.post("/api/orchestrator/run/proj/stop")
        assert resp.status_code == 200
        assert resp.json()["status"] == "stopped"
        assert orch_mod._runs["proj"]["status"] == "stopped"

    def test_stop_not_running(self, api):
        client, wm = api
        resp = client.post("/api/orchestrator/run/proj/stop")
        assert resp.status_code == 404

    def test_stop_cascades_to_children(self, api):
        """Stopping a parent should also stop running children."""
        client, wm = api
        import mado.backend.api.routes.orchestrator as orch_mod
        wm.create_workspace("parent")
        wm.create_workspace("child1", parent_id="parent")
        wm.create_workspace("child2", parent_id="parent")
        orch_mod._runs["parent"] = {"status": "running", "iteration": 1, "max_iterations": 30}
        orch_mod._runs["child1"] = {"status": "running", "iteration": 2, "max_iterations": 30}
        orch_mod._runs["child2"] = {"status": "completed", "iteration": 5, "max_iterations": 30}

        resp = client.post("/api/orchestrator/run/parent/stop")
        assert resp.status_code == 200
        data = resp.json()
        assert "child1" in data["stopped_children"]
        # child2 was completed, not stopped
        assert "child2" not in data["stopped_children"]
        assert orch_mod._runs["child1"]["status"] == "stopped"


class TestPauseRun:
    def test_pause_running(self, api):
        client, wm = api
        import mado.backend.api.routes.orchestrator as orch_mod
        wm.create_workspace("proj")
        orch_mod._runs["proj"] = {"status": "running", "iteration": 2, "max_iterations": 30}
        resp = client.post("/api/orchestrator/run/proj/pause")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "paused"
        assert data["iteration"] == 2

    def test_pause_not_running(self, api):
        client, wm = api
        resp = client.post("/api/orchestrator/run/proj/pause")
        assert resp.status_code == 404


class TestDispatchChild:
    def test_dispatch_child(self, api):
        client, wm = api
        wm.create_workspace("parent")
        wm.create_workspace("child", parent_id="parent")
        wm.update_project_config("child", {"goal": "child goal"})
        resp = client.post("/api/orchestrator/dispatch-child", json={
            "parent_id": "parent",
            "child_id": "child",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "started"
        assert data["inherited"] is True

    def test_dispatch_child_not_a_child(self, api):
        client, wm = api
        wm.create_workspace("a")
        wm.create_workspace("b")
        resp = client.post("/api/orchestrator/dispatch-child", json={
            "parent_id": "a",
            "child_id": "b",
        })
        assert resp.status_code == 400

    def test_dispatch_child_parent_not_found(self, api):
        client, wm = api
        resp = client.post("/api/orchestrator/dispatch-child", json={
            "parent_id": "nope",
            "child_id": "also-nope",
        })
        assert resp.status_code == 404

    def test_dispatch_child_already_running(self, api):
        client, wm = api
        import mado.backend.api.routes.orchestrator as orch_mod
        wm.create_workspace("parent")
        wm.create_workspace("child", parent_id="parent")
        orch_mod._runs["child"] = {"status": "running", "iteration": 0, "max_iterations": 30}
        resp = client.post("/api/orchestrator/dispatch-child", json={
            "parent_id": "parent",
            "child_id": "child",
        })
        assert resp.status_code == 409


class TestDispatchAllChildren:
    def test_dispatch_all(self, api):
        client, wm = api
        wm.create_workspace("parent")
        wm.create_workspace("c1", parent_id="parent")
        wm.create_workspace("c2", parent_id="parent")
        wm.update_project_config("c1", {"goal": "g1"})
        wm.update_project_config("c2", {"goal": "g2"})
        resp = client.post("/api/orchestrator/dispatch-children", json={
            "parent_id": "parent",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert set(data["started"]) == {"c1", "c2"}

    def test_dispatch_skips_already_running(self, api):
        client, wm = api
        import mado.backend.api.routes.orchestrator as orch_mod
        wm.create_workspace("parent")
        wm.create_workspace("c1", parent_id="parent")
        wm.create_workspace("c2", parent_id="parent")
        orch_mod._runs["c1"] = {"status": "running", "iteration": 0, "max_iterations": 30}
        resp = client.post("/api/orchestrator/dispatch-children", json={
            "parent_id": "parent",
        })
        data = resp.json()
        assert "c1" in data["skipped"]
        assert "c2" in data["started"]


class TestListRuns:
    def test_list_runs_empty(self, api):
        client, wm = api
        resp = client.get("/api/orchestrator/runs")
        assert resp.status_code == 200
        assert resp.json()["runs"] == {}

    def test_list_runs_with_data(self, api):
        client, wm = api
        import mado.backend.api.routes.orchestrator as orch_mod
        orch_mod._runs["a"] = {"status": "running", "iteration": 1, "max_iterations": 30}
        orch_mod._runs["b"] = {"status": "completed", "iteration": 5, "max_iterations": 30}
        resp = client.get("/api/orchestrator/runs")
        runs = resp.json()["runs"]
        assert runs["a"]["status"] == "running"
        assert runs["b"]["status"] == "completed"


class TestGetRunState:
    def test_get_state_from_runs(self, api):
        client, wm = api
        import mado.backend.api.routes.orchestrator as orch_mod
        orch_mod._runs["proj"] = {"status": "completed", "iteration": 3, "max_iterations": 30}
        resp = client.get("/api/orchestrator/run/proj/state")
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_get_state_not_found(self, api):
        client, wm = api
        resp = client.get("/api/orchestrator/run/nope/state")
        assert resp.status_code == 404


class TestGetTaskStates:
    def test_tasks_no_orchestrator(self, api):
        client, wm = api
        resp = client.get("/api/orchestrator/run/proj/tasks")
        assert resp.status_code == 200
        assert resp.json()["tasks"] == {}


class TestInheritParentContext:
    def test_inherits_agent_profiles(self, api):
        client, wm = api
        from mado.backend.api.routes.orchestrator import _inherit_parent_context
        wm.create_workspace("parent")
        wm.create_workspace("child", parent_id="parent")
        wm.update_project_config("parent", {
            "agent_profiles": {
                "cto": {"title": "CTO", "personality": "strict"},
            },
        })
        _inherit_parent_context("parent", "child")
        child_config = wm.get_project_config("child")
        assert "cto" in child_config.get("agent_profiles", {})

    def test_inherits_project_memory(self, api):
        client, wm = api
        from mado.backend.api.routes.orchestrator import _inherit_parent_context
        wm.create_workspace("parent")
        wm.create_workspace("child", parent_id="parent")
        parent_memory = wm.projects_root / "parent" / "project_memory.md"
        parent_memory.write_text("# Parent Knowledge\nImportant info", encoding="utf-8")
        _inherit_parent_context("parent", "child")
        child_memory = wm.projects_root / "child" / "project_memory.md"
        content = child_memory.read_text(encoding="utf-8")
        assert "Inherited from parent: parent" in content
        assert "Important info" in content

    def test_inherits_rules(self, api):
        client, wm = api
        from mado.backend.api.routes.orchestrator import _inherit_parent_context
        wm.create_workspace("parent")
        wm.create_workspace("child", parent_id="parent")
        wm.update_project_config("parent", {
            "rules_must": "Always test",
            "rules_forbidden": "No shortcuts",
        })
        _inherit_parent_context("parent", "child")
        child_config = wm.get_project_config("child")
        assert child_config["rules_must"] == "Always test"
        assert child_config["rules_forbidden"] == "No shortcuts"

    def test_child_rules_not_overwritten(self, api):
        """Child's existing rules should not be overwritten by parent."""
        client, wm = api
        from mado.backend.api.routes.orchestrator import _inherit_parent_context
        wm.create_workspace("parent")
        wm.create_workspace("child", parent_id="parent")
        wm.update_project_config("parent", {"rules_must": "parent rule"})
        wm.update_project_config("child", {"rules_must": "child rule"})
        _inherit_parent_context("parent", "child")
        child_config = wm.get_project_config("child")
        assert child_config["rules_must"] == "child rule"
