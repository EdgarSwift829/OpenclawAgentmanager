"""Tests for WebSocket broadcasting (C) and lifecycle management (E)."""

import time
from unittest.mock import MagicMock

import pytest

from mado.backend.api.routes.websocket import EventBroadcaster, _event_history
from mado.backend.orchestrator.orchestrator import AgentState, Orchestrator

# ============================================================
# AgentState tests
# ============================================================

class TestAgentState:
    def test_initial_state(self):
        state = AgentState("engineer")
        assert state.role == "engineer"
        assert state.status == "idle"
        assert state.tasks_completed == 0
        assert state.tasks_failed == 0
        assert state.error is None

    def test_activate(self):
        state = AgentState("engineer")
        state.activate()
        assert state.status == "active"
        assert state.last_active is not None

    def test_complete_task(self):
        state = AgentState("engineer")
        state.activate()
        state.complete_task()
        assert state.status == "idle"
        assert state.tasks_completed == 1

    def test_fail_task(self):
        state = AgentState("engineer")
        state.activate()
        state.fail_task("timeout")
        assert state.status == "error"
        assert state.tasks_failed == 1
        assert state.error == "timeout"

    def test_to_dict(self):
        state = AgentState("tester")
        state.activate()
        state.complete_task()
        d = state.to_dict()
        assert d["role"] == "tester"
        assert d["tasks_completed"] == 1
        assert d["status"] == "idle"

    def test_multiple_tasks(self):
        state = AgentState("engineer")
        for _ in range(3):
            state.activate()
            state.complete_task()
        state.activate()
        state.fail_task("boom")
        assert state.tasks_completed == 3
        assert state.tasks_failed == 1


# ============================================================
# Orchestrator lifecycle tests
# ============================================================

class TestOrchestratorLifecycle:
    def _mock_agent(self, role, delay=0, fail=False):
        agent = MagicMock()
        agent.role = role

        def execute(task):
            if delay:
                time.sleep(delay)
            if fail:
                raise RuntimeError(f"{role} failed")
            return {"role": role, "result": f"{role} done"}

        agent.execute = execute
        return agent

    def test_initial_status(self):
        orch = Orchestrator("test")
        assert orch.status == "idle"

    def test_elapsed_none_before_start(self):
        orch = Orchestrator("test")
        assert orch.elapsed_seconds is None

    def test_get_state(self):
        orch = Orchestrator("test")
        state = orch.get_state()
        assert state["project_id"] == "test"
        assert state["status"] == "idle"
        assert state["agents"] == {}

    @pytest.mark.asyncio
    async def test_cancel_sets_status(self):
        orch = Orchestrator("test")
        orch.cancel()
        assert orch.status == "cancelled"
        assert orch._cancel_event.is_set()

    @pytest.mark.asyncio
    async def test_agent_state_tracked_on_execute(self):
        orch = Orchestrator("test")
        orch.agents["engineer"] = self._mock_agent("engineer")
        orch.agent_states["engineer"] = AgentState("engineer")
        orch.message_bus.register("engineer")

        result = await orch._execute_single({"assigned_to": "engineer", "description": "test"})
        assert result["role"] == "engineer"
        assert orch.agent_states["engineer"].tasks_completed == 1
        assert orch.agent_states["engineer"].status == "idle"

    @pytest.mark.asyncio
    async def test_agent_state_error_on_failure(self):
        orch = Orchestrator("test")
        orch.agents["engineer"] = self._mock_agent("engineer", fail=True)
        orch.agent_states["engineer"] = AgentState("engineer")
        orch.message_bus.register("engineer")

        result = await orch._execute_single({"assigned_to": "engineer", "description": "test"})
        assert result.get("error") is True
        assert orch.agent_states["engineer"].tasks_failed == 1
        assert orch.agent_states["engineer"].status == "error"

    @pytest.mark.asyncio
    async def test_task_timeout(self):
        orch = Orchestrator("test")
        orch.task_timeout = 0.1  # 100ms timeout
        orch.agents["engineer"] = self._mock_agent("engineer", delay=1.0)
        orch.agent_states["engineer"] = AgentState("engineer")
        orch.message_bus.register("engineer")

        result = await orch._execute_single({"assigned_to": "engineer", "description": "slow"})
        assert result.get("error") is True
        assert "timed out" in result["result"]
        assert orch.agent_states["engineer"].tasks_failed == 1

    @pytest.mark.asyncio
    async def test_cleanup_resets_active_agents(self):
        orch = Orchestrator("test")
        orch.agent_states["engineer"] = AgentState("engineer")
        orch.agent_states["engineer"].activate()
        assert orch.agent_states["engineer"].status == "active"

        await orch._cleanup()
        assert orch.agent_states["engineer"].status == "idle"

    @pytest.mark.asyncio
    async def test_elapsed_time_tracked(self):
        orch = Orchestrator("test")
        orch._start_time = time.time() - 5.0  # Simulate 5 seconds ago
        assert orch.elapsed_seconds >= 5.0

    @pytest.mark.asyncio
    async def test_event_emits_agent_list_on_start(self):
        events = []

        async def handler(event):
            events.append(event)

        orch = Orchestrator("test")
        orch.on_event(handler)
        await orch._emit("run_started", {"agents": ["cto", "engineer"]})

        assert len(events) == 1
        assert "agents" in events[0]


# ============================================================
# EventBroadcaster tests
# ============================================================

class TestEventBroadcaster:
    def setup_method(self):
        # Clear history between tests
        _event_history.clear()

    @pytest.mark.asyncio
    async def test_broadcast_stores_history(self):
        await EventBroadcaster.broadcast("proj1", {"type": "test", "data": "hello"})
        history = EventBroadcaster.get_history("proj1")
        assert len(history) == 1
        assert history[0]["type"] == "test"
        assert "seq" in history[0]
        assert "timestamp" in history[0]

    @pytest.mark.asyncio
    async def test_history_sequence_numbers(self):
        for i in range(5):
            await EventBroadcaster.broadcast("proj1", {"type": "test", "index": i})
        history = EventBroadcaster.get_history("proj1")
        seqs = [e["seq"] for e in history]
        assert seqs == [0, 1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_history_since_seq(self):
        for i in range(5):
            await EventBroadcaster.broadcast("proj1", {"type": "test", "index": i})
        history = EventBroadcaster.get_history("proj1", since_seq=3)
        assert len(history) == 2
        assert history[0]["seq"] == 3

    @pytest.mark.asyncio
    async def test_history_empty_project(self):
        history = EventBroadcaster.get_history("nonexistent")
        assert history == []

    def test_connection_count_empty(self):
        counts = EventBroadcaster.get_connection_count()
        assert counts == {}

    def test_connection_count_specific_empty(self):
        counts = EventBroadcaster.get_connection_count("proj1")
        assert counts == {"proj1": 0}

    @pytest.mark.asyncio
    async def test_history_ring_buffer(self):
        """History should not exceed _MAX_HISTORY."""
        from mado.backend.api.routes.websocket import _MAX_HISTORY

        for i in range(_MAX_HISTORY + 50):
            await EventBroadcaster.broadcast("proj1", {"type": "test", "index": i})

        history = EventBroadcaster.get_history("proj1")
        assert len(history) <= _MAX_HISTORY
