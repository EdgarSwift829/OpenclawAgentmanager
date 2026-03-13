"""Tests for parallel orchestration, message bus, model routing, and tiering."""

from unittest.mock import MagicMock, patch

import pytest

from mado.backend.models.router import _call_with_retry, route_inference
from mado.backend.orchestrator.message_bus import Message, MessageBus
from mado.backend.orchestrator.orchestrator import Orchestrator

# ============================================================
# MessageBus tests
# ============================================================

class TestMessageBus:
    @pytest.fixture
    def bus(self):
        return MessageBus()

    def test_register_agent(self, bus):
        bus.register("engineer")
        assert "engineer" in bus._queues

    def test_register_idempotent(self, bus):
        bus.register("engineer")
        bus.register("engineer")
        assert len(bus._queues) == 1

    @pytest.mark.asyncio
    async def test_send_direct_message(self, bus):
        bus.register("engineer")
        bus.register("reviewer")

        msg = Message(sender="reviewer", recipient="engineer", msg_type="result", payload="ok")
        await bus.send(msg)

        received = await bus.receive("engineer")
        assert received is not None
        assert received.sender == "reviewer"
        assert received.payload == "ok"

    @pytest.mark.asyncio
    async def test_broadcast_message(self, bus):
        bus.register("engineer")
        bus.register("tester")
        bus.register("reviewer")

        msg = Message(sender="cto", recipient="*", msg_type="plan", payload="build it")
        await bus.send(msg)

        # All agents except sender should receive
        for role in ["engineer", "tester", "reviewer"]:
            received = await bus.receive(role)
            assert received is not None
            assert received.payload == "build it"

    @pytest.mark.asyncio
    async def test_receive_empty_queue(self, bus):
        bus.register("engineer")
        received = await bus.receive("engineer")
        assert received is None

    @pytest.mark.asyncio
    async def test_external_listener(self, bus):
        bus.register("engineer")
        events = []

        async def listener(msg):
            events.append(msg)

        bus.add_listener(listener)
        msg = Message(sender="cto", recipient="engineer", msg_type="task", payload="code")
        await bus.send(msg)

        assert len(events) == 1
        assert events[0].payload == "code"

    def test_history(self, bus):
        assert bus.get_history() == []

    @pytest.mark.asyncio
    async def test_history_records_messages(self, bus):
        bus.register("a")
        await bus.send(Message(sender="x", recipient="a", msg_type="t", payload="p"))
        history = bus.get_history()
        assert len(history) == 1
        assert history[0]["sender"] == "x"


# ============================================================
# Orchestrator parallel execution tests
# ============================================================

class TestOrchestratorParallel:
    def _mock_agent(self, role, delay=0):
        agent = MagicMock()
        agent.role = role

        def execute(task):
            if delay:
                import time
                time.sleep(delay)
            return {"role": role, "result": f"{role} done"}

        agent.execute = execute
        return agent

    @pytest.mark.asyncio
    async def test_execute_parallel_tasks(self):
        orch = Orchestrator("test-project")
        orch.agents = {
            "engineer": self._mock_agent("engineer"),
            "tester": self._mock_agent("tester"),
            "researcher": self._mock_agent("researcher"),
        }
        orch.message_bus.register("engineer")
        orch.message_bus.register("tester")
        orch.message_bus.register("researcher")

        tasks = [
            {"description": "write code", "assigned_to": "engineer"},
            {"description": "write tests", "assigned_to": "tester"},
            {"description": "research", "assigned_to": "researcher"},
        ]

        results = await orch._execute_parallel(tasks)
        assert len(results) == 3
        roles = {r["role"] for r in results}
        assert roles == {"engineer", "tester", "researcher"}

    @pytest.mark.asyncio
    async def test_parallel_faster_than_sequential(self):
        """Parallel execution of 3 tasks with 0.1s each should be ~0.1s, not ~0.3s."""
        orch = Orchestrator("test-speed")
        for role in ["engineer", "tester", "researcher"]:
            orch.agents[role] = self._mock_agent(role, delay=0.1)
            orch.message_bus.register(role)

        tasks = [
            {"description": "t1", "assigned_to": "engineer"},
            {"description": "t2", "assigned_to": "tester"},
            {"description": "t3", "assigned_to": "researcher"},
        ]

        import time
        start = time.time()
        results = await orch._execute_parallel(tasks)
        elapsed = time.time() - start

        assert len(results) == 3
        # Parallel should be significantly faster than 0.3s sequential
        assert elapsed < 0.25, f"Parallel took {elapsed:.2f}s, expected < 0.25s"

    @pytest.mark.asyncio
    async def test_classify_tasks(self):
        orch = Orchestrator("test-classify")
        tasks = [
            {"description": "independent", "assigned_to": "engineer"},
            {"description": "depends on above", "assigned_to": "tester", "depends_on": "engineer"},
            {"description": "also independent", "assigned_to": "researcher"},
        ]

        parallel, sequential = orch._classify_tasks_simple(tasks)
        assert len(parallel) == 2
        assert len(sequential) == 1
        assert sequential[0]["assigned_to"] == "tester"

    @pytest.mark.asyncio
    async def test_cancel_stops_execution(self):
        orch = Orchestrator("test-cancel")
        orch.cancel()
        assert orch._cancel_event.is_set()

    @pytest.mark.asyncio
    async def test_execute_single_missing_agent(self):
        orch = Orchestrator("test-missing")
        result = await orch._execute_single({"assigned_to": "nonexistent"})
        assert result.get("error") is True

    @pytest.mark.asyncio
    async def test_execute_parallel_handles_errors(self):
        orch = Orchestrator("test-errors")

        error_agent = MagicMock()
        error_agent.role = "engineer"
        error_agent.execute = MagicMock(side_effect=RuntimeError("boom"))

        ok_agent = self._mock_agent("tester")

        orch.agents = {"engineer": error_agent, "tester": ok_agent}
        orch.message_bus.register("engineer")
        orch.message_bus.register("tester")

        tasks = [
            {"description": "fail", "assigned_to": "engineer"},
            {"description": "ok", "assigned_to": "tester"},
        ]

        results = await orch._execute_parallel(tasks)
        assert len(results) == 2
        # One should be error, one should be ok
        errors = [r for r in results if r.get("error")]
        assert len(errors) == 1

    @pytest.mark.asyncio
    async def test_event_callback_called(self):
        orch = Orchestrator("test-events")
        events = []

        async def handler(event):
            events.append(event)

        orch.on_event(handler)
        await orch._emit("test_event", {"key": "value"})
        assert len(events) == 1
        assert events[0]["type"] == "test_event"


# ============================================================
# Router retry & fallback tests
# ============================================================

class TestRouterRetry:
    def test_retry_on_failure(self):
        """Should retry on exception and eventually succeed."""
        call_count = 0

        def mock_ollama(model, prompt, sys, timeout):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("connection refused")
            return "success"

        with patch("mado.backend.models.router._call_ollama", side_effect=mock_ollama):
            result = _call_with_retry("ollama", "test-model", "hello", None, 3, 120)

        assert result == "success"
        assert call_count == 3

    def test_retry_exhausted(self):
        """Should return error after all retries exhausted."""
        def always_fail(model, prompt, sys, timeout):
            raise ConnectionError("down")

        with patch("mado.backend.models.router._call_ollama", side_effect=always_fail):
            with patch("mado.backend.models.router.DEFAULT_BASE_DELAY", 0.01):
                result = _call_with_retry("ollama", "m", "p", None, 2, 10)

        assert result.startswith("[LLM Error]")
        assert "2 attempts" in result

    def test_fallback_model(self):
        """Should try fallback when primary fails."""
        def fail_primary(model, prompt, sys, timeout):
            if model == "primary":
                raise ConnectionError("primary down")
            return "fallback ok"

        with patch("mado.backend.models.router._call_ollama", side_effect=fail_primary):
            with patch("mado.backend.models.router.DEFAULT_BASE_DELAY", 0.01):
                model = {
                    "name": "primary",
                    "provider": "ollama",
                    "fallback": {"name": "backup", "provider": "ollama"},
                }
                result = route_inference(model, "test", max_retries=1)

        assert result == "fallback ok"


# ============================================================
# Model tiering config tests
# ============================================================

class TestModelTiering:
    def test_config_has_tiers(self):
        from pathlib import Path

        import yaml

        config_path = Path(__file__).resolve().parents[1] / "config" / "models.yaml"
        if not config_path.exists():
            pytest.skip("models.yaml not found")

        with open(config_path) as f:
            data = yaml.safe_load(f)

        models = data.get("models", {})
        for name, config in models.items():
            assert "tier" in config, f"Model {name} missing 'tier' field"

    def test_high_tier_for_planning_roles(self):
        from pathlib import Path

        import yaml

        config_dir = Path(__file__).resolve().parents[1] / "config"
        models_path = config_dir / "models.yaml"
        agents_path = config_dir / "agents.yaml"

        if not models_path.exists() or not agents_path.exists():
            pytest.skip("Config files not found")

        with open(models_path) as f:
            models_data = yaml.safe_load(f).get("models", {})

        with open(agents_path) as f:
            agents_data = yaml.safe_load(f) or {}

        # CTO and reviewer should use high-tier models
        for role in ["cto", "reviewer"]:
            model_name = agents_data.get(role)
            if model_name and model_name in models_data:
                tier = models_data[model_name].get("tier")
                assert tier == "high", f"{role} should use high-tier model, got {tier}"

    def test_fallback_configured(self):
        from pathlib import Path

        import yaml

        config_path = Path(__file__).resolve().parents[1] / "config" / "models.yaml"
        if not config_path.exists():
            pytest.skip("models.yaml not found")

        with open(config_path) as f:
            data = yaml.safe_load(f)

        models = data.get("models", {})
        # At least one model should have fallback configured
        has_fallback = any(
            "fallback" in config for config in models.values()
        )
        assert has_fallback, "At least one model should have a fallback configured"
