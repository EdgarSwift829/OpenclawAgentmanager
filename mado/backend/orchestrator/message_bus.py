"""MessageBus - Async message passing between agents."""

import asyncio
from typing import Any, Callable, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Message:
    """A message passed between agents or broadcast to all."""
    sender: str
    recipient: str  # agent role or "*" for broadcast
    msg_type: str   # "result", "request", "status", "error"
    payload: Any
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class MessageBus:
    """Async message bus for inter-agent communication.

    Features:
    - Per-agent inbox queues
    - Broadcast to all agents
    - Event listeners for external consumers (e.g. WebSocket)
    """

    def __init__(self):
        self._queues: dict[str, asyncio.Queue] = {}
        self._listeners: list[Callable] = []
        self._history: list[Message] = []

    def register(self, agent_role: str) -> None:
        """Register an agent's inbox."""
        if agent_role not in self._queues:
            self._queues[agent_role] = asyncio.Queue()

    def add_listener(self, callback: Callable) -> None:
        """Add an external listener (e.g. WebSocket broadcaster)."""
        self._listeners.append(callback)

    async def send(self, message: Message) -> None:
        """Send a message to a specific agent or broadcast."""
        self._history.append(message)

        if message.recipient == "*":
            for role, queue in self._queues.items():
                if role != message.sender:
                    await queue.put(message)
        elif message.recipient in self._queues:
            await self._queues[message.recipient].put(message)

        # Notify external listeners
        for listener in self._listeners:
            try:
                await listener(message)
            except Exception:
                pass

    async def receive(self, agent_role: str, timeout: float = None) -> Optional[Message]:
        """Receive the next message for an agent. Returns None on timeout."""
        if agent_role not in self._queues:
            return None
        try:
            if timeout:
                return await asyncio.wait_for(self._queues[agent_role].get(), timeout=timeout)
            return self._queues[agent_role].get_nowait()
        except (asyncio.TimeoutError, asyncio.QueueEmpty):
            return None

    def get_history(self, limit: int = 50) -> list[dict]:
        """Get recent message history as dicts."""
        return [
            {
                "sender": m.sender,
                "recipient": m.recipient,
                "type": m.msg_type,
                "payload": str(m.payload)[:500],
                "timestamp": m.timestamp,
            }
            for m in self._history[-limit:]
        ]
