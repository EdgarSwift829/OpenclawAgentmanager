"""Tests for WebSocket endpoint."""

import json
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from mado.backend.api.main import app


@pytest.fixture
def ws_client():
    """TestClient with websocket support."""
    return TestClient(app)


class TestWebSocketEndpoint:
    def test_connect_receives_confirmation(self, ws_client):
        with ws_client.websocket_connect("/api/ws/test-project") as ws:
            msg = json.loads(ws.receive_text())
            assert msg["type"] == "connected"
            assert msg["project_id"] == "test-project"

    def test_ping_pong(self, ws_client):
        with ws_client.websocket_connect("/api/ws/test-project") as ws:
            ws.receive_text()  # skip connected message
            ws.send_text(json.dumps({"type": "ping"}))
            msg = json.loads(ws.receive_text())
            assert msg["type"] == "pong"

    def test_invalid_json(self, ws_client):
        with ws_client.websocket_connect("/api/ws/test-project") as ws:
            ws.receive_text()  # skip connected
            ws.send_text("not json at all")
            msg = json.loads(ws.receive_text())
            assert msg["type"] == "error"
            assert "Invalid JSON" in msg["detail"]

    def test_unknown_message_type(self, ws_client):
        with ws_client.websocket_connect("/api/ws/test-project") as ws:
            ws.receive_text()  # skip connected
            ws.send_text(json.dumps({"type": "foobar"}))
            msg = json.loads(ws.receive_text())
            assert msg["type"] == "error"
            assert "Unknown" in msg["detail"]

    def test_get_history_empty(self, ws_client):
        with ws_client.websocket_connect("/api/ws/hist-project") as ws:
            ws.receive_text()  # skip connected
            ws.send_text(json.dumps({"type": "get_history", "since_seq": 0}))
            msg = json.loads(ws.receive_text())
            assert msg["type"] == "history_replay"
            assert isinstance(msg["events"], list)

    def test_stop_no_orchestrator(self, ws_client):
        with ws_client.websocket_connect("/api/ws/no-orch") as ws:
            ws.receive_text()  # skip connected
            ws.send_text(json.dumps({"type": "stop"}))
            msg = json.loads(ws.receive_text())
            assert msg["type"] == "error"
            assert "No active" in msg["detail"]

    def test_stop_with_orchestrator(self, ws_client):
        from mado.backend.api.routes.orchestrator import _orchestrators
        from unittest.mock import MagicMock

        mock_orch = MagicMock()
        _orchestrators["stop-proj"] = mock_orch
        try:
            with ws_client.websocket_connect("/api/ws/stop-proj") as ws:
                ws.receive_text()  # skip connected
                ws.send_text(json.dumps({"type": "stop"}))
                msg = json.loads(ws.receive_text())
                assert msg["type"] == "stop_acknowledged"
                mock_orch.cancel.assert_called_once()
        finally:
            _orchestrators.pop("stop-proj", None)
