"""Tests for models, agents, and logs API routes."""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def api(api_client):
    """Alias for shared api_client fixture."""
    yield api_client


# ============================================================
# Models API
# ============================================================

class TestModelsAPI:
    def test_list_models(self, api):
        client, wm = api
        resp = client.get("/api/models/")
        assert resp.status_code == 200
        assert "models" in resp.json()

    def test_get_assignments(self, api):
        client, wm = api
        resp = client.get("/api/models/assignments")
        assert resp.status_code == 200
        assert "assignments" in resp.json()

    def test_register_model(self, api):
        client, wm = api
        resp = client.post("/api/models/register", json={
            "name": "test-model",
            "provider": "ollama",
            "context": 8192,
            "capabilities": ["chat"],
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "registered"

    def test_switch_model(self, api):
        client, wm = api
        # Get current assignments to find a valid role
        assignments = client.get("/api/models/assignments").json()["assignments"]
        if assignments:
            role = list(assignments.keys())[0]
            # Register a model first
            client.post("/api/models/register", json={
                "name": "switch-target",
                "provider": "ollama",
            })
            resp = client.put("/api/models/switch", json={
                "role": role,
                "new_model": "switch-target",
            })
            # Either success or validation error
            assert resp.status_code in (200, 400)

    def test_reload_models(self, api):
        client, wm = api
        resp = client.post("/api/models/reload")
        assert resp.status_code == 200
        assert resp.json()["status"] == "reloaded"

    def test_reorder_roles(self, api):
        client, wm = api
        assignments = client.get("/api/models/assignments").json()["assignments"]
        if len(assignments) >= 2:
            roles = list(assignments.keys())
            reversed_roles = list(reversed(roles))
            resp = client.put("/api/models/reorder", json={"roles": reversed_roles})
            assert resp.status_code == 200

    def test_reorder_unknown_role(self, api):
        client, wm = api
        resp = client.put("/api/models/reorder", json={"roles": ["nonexistent_role"]})
        assert resp.status_code == 400


# ============================================================
# Agents API
# ============================================================

class TestAgentsAPI:
    def test_list_agents_empty(self, api):
        client, wm = api
        resp = client.get("/api/agents/some-project")
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == "some-project"
        assert data["agents"] == []

    def test_list_agents_with_session(self, api):
        client, wm = api
        from mado.backend.api.routes.agents import register_session

        # Create mock agents
        mock_agent = MagicMock()
        mock_agent.model = {"name": "test-model"}
        register_session("proj", {"engineer": mock_agent})

        resp = client.get("/api/agents/proj")
        assert resp.status_code == 200
        agents = resp.json()["agents"]
        assert len(agents) == 1
        assert agents[0]["role"] == "engineer"

    def test_get_agent_not_found(self, api):
        client, wm = api
        from mado.backend.api.routes.agents import _active_sessions
        _active_sessions.pop("proj", None)
        resp = client.get("/api/agents/proj/engineer")
        assert resp.status_code == 404

    def test_get_agent_with_session(self, api):
        client, wm = api
        from mado.backend.api.routes.agents import register_session

        mock_agent = MagicMock()
        mock_agent.model = {"name": "test-model"}
        mock_agent.workspace_path = "/tmp/test"
        mock_agent.tools = []
        register_session("proj", {"engineer": mock_agent})

        resp = client.get("/api/agents/proj/engineer")
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "engineer"


# ============================================================
# Logs API
# ============================================================

class TestLogsAPI:
    def test_get_logs_path_traversal(self, api):
        client, wm = api
        resp = client.get("/api/logs/../etc")
        # URL normalization may resolve ../ before reaching handler
        assert resp.status_code in (400, 404)

    def test_get_logs_backslash_traversal(self, api):
        client, wm = api
        resp = client.get("/api/logs/..%5Cetc")
        # %5C = backslash
        assert resp.status_code in (400, 404, 422)
