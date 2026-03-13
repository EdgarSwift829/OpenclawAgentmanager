"""WebSocket endpoint for real-time agent activity streaming.

Features:
- Structured event broadcasting from orchestrator
- Client commands: ping, subscribe/unsubscribe, get_history
- Connection tracking with metadata
- Graceful disconnect handling
"""

import json
import logging
from datetime import datetime
from typing import Dict, Optional, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()

# Connected clients per project
_connections: Dict[str, Set[WebSocket]] = {}

# Per-project event history buffer (ring buffer, max 200 events)
_event_history: Dict[str, list] = {}
_MAX_HISTORY = 200


class EventBroadcaster:
    """Broadcast structured events to connected WebSocket clients."""

    @staticmethod
    async def broadcast(project_id: str, event: dict):
        """Send an event to all clients watching a project.

        Automatically adds sequence number and timestamp if not present.
        Stores event in history buffer for late-joining clients.
        """
        # Enrich event
        if "timestamp" not in event:
            event["timestamp"] = datetime.utcnow().isoformat()

        # Store in history
        if project_id not in _event_history:
            _event_history[project_id] = []
        history = _event_history[project_id]
        event["seq"] = len(history)
        history.append(event)
        if len(history) > _MAX_HISTORY:
            _event_history[project_id] = history[-_MAX_HISTORY:]

        # Broadcast to connected clients
        if project_id in _connections:
            message = json.dumps(event)
            disconnected = set()
            for ws in _connections[project_id]:
                try:
                    await ws.send_text(message)
                except Exception:
                    disconnected.add(ws)
            _connections[project_id] -= disconnected

    @staticmethod
    def get_history(project_id: str, since_seq: int = 0) -> list:
        """Get events since a given sequence number (for reconnection catch-up)."""
        history = _event_history.get(project_id, [])
        return [e for e in history if e.get("seq", 0) >= since_seq]

    @staticmethod
    def get_connection_count(project_id: Optional[str] = None) -> dict:
        """Get number of connected clients per project or for a specific project."""
        if project_id:
            return {project_id: len(_connections.get(project_id, set()))}
        return {pid: len(clients) for pid, clients in _connections.items()}


broadcaster = EventBroadcaster()


@router.websocket("/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    """WebSocket connection for real-time project updates.

    Client can send:
      {"type": "ping"}                          -> pong response
      {"type": "get_history", "since_seq": N}   -> replay missed events
      {"type": "stop"}                          -> request orchestration stop
    """
    await websocket.accept()

    if project_id not in _connections:
        _connections[project_id] = set()
    _connections[project_id].add(websocket)

    logger.info(f"WebSocket connected: project={project_id}")

    try:
        # Send connection confirmation with current state
        await websocket.send_text(json.dumps({
            "type": "connected",
            "project_id": project_id,
            "history_available": len(_event_history.get(project_id, [])),
        }))

        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error", "detail": "Invalid JSON",
                }))
                continue

            msg_type = msg.get("type")

            if msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

            elif msg_type == "get_history":
                # Replay events since a sequence number (for reconnection)
                since = msg.get("since_seq", 0)
                events = broadcaster.get_history(project_id, since_seq=since)
                await websocket.send_text(json.dumps({
                    "type": "history_replay",
                    "events": events,
                    "count": len(events),
                }))

            elif msg_type == "stop":
                # Forward stop request to orchestrator via API internals
                from mado.backend.api.routes.orchestrator import _orchestrators
                orch = _orchestrators.get(project_id)
                if orch:
                    orch.cancel()
                    await websocket.send_text(json.dumps({
                        "type": "stop_acknowledged",
                        "project_id": project_id,
                    }))
                else:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "detail": "No active orchestration to stop",
                    }))

            else:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "detail": f"Unknown message type: {msg_type}",
                }))

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: project={project_id}")
        _connections[project_id].discard(websocket)
        if not _connections[project_id]:
            del _connections[project_id]
