"""Tests for logs API routes."""

import pytest


@pytest.fixture
def api(api_client):
    yield api_client


class TestLogsAPI:
    def test_get_logs(self, api):
        client, wm = api
        # Create a project first to have a valid project_id
        client.post("/api/projects/", json={"project_id": "log-proj"})
        resp = client.get("/api/logs/log-proj")
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == "log-proj"
        assert "logs" in data

    def test_get_logs_with_type(self, api):
        client, wm = api
        resp = client.get("/api/logs/some-proj?log_type=agent")
        assert resp.status_code == 200

    def test_get_logs_with_limit(self, api):
        client, wm = api
        resp = client.get("/api/logs/some-proj?limit=10")
        assert resp.status_code == 200

    def test_get_logs_limit_clamped(self, api):
        client, wm = api
        # Limit > 1000 should be clamped
        resp = client.get("/api/logs/some-proj?limit=9999")
        assert resp.status_code == 200

    def test_get_logs_path_traversal(self, api):
        client, wm = api
        resp = client.get("/api/logs/../etc")
        assert resp.status_code in (400, 404)
