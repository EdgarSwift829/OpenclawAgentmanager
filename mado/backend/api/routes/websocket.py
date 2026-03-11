"""WebSocket endpoint for real-time agent activity streaming."""

import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Set

router = APIRouter()

# Connected clients per project
_connections: Dict[str, Set[WebSocket]] = {}


class EventBroadcaster:
    """Broadcast events to connected WebSocket clients."""

    @staticmethod
    async def broadcast(project_id: str, event: dict):
        """Send an event to all clients watching a project."""
        if project_id in _connections:
            message = json.dumps(event)
            disconnected = set()
            for ws in _connections[project_id]:
                try:
                    await ws.send_text(message)
                except Exception:
                    disconnected.add(ws)
            _connections[project_id] -= disconnected


broadcaster = EventBroadcaster()


@router.websocket("/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    """WebSocket connection for real-time project updates."""
    await websocket.accept()

    if project_id not in _connections:
        _connections[project_id] = set()
    _connections[project_id].add(websocket)

    try:
        await websocket.send_text(json.dumps({
            "type": "connected",
            "project_id": project_id,
        }))

        while True:
            # Keep connection alive, receive client messages
            data = await websocket.receive_text()
            msg = json.loads(data)

            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        _connections[project_id].discard(websocket)
        if not _connections[project_id]:
            del _connections[project_id]
