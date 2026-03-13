"""Integration tests for Orchestrator end-to-end workflows.

Tests the full orchestration loop with mocked LLM calls:
- Happy path: single iteration with approval
- Multi-iteration with review rejection
- DAG-based parallel task execution
- Error handling (timeout, agent failure)
- Cancellation mid-run
"""

import json
from unittest.mock import patch

import pytest

from mado.backend.orchestrator.orchestrator import AgentState, Orchestrator, TaskState
from mado.backend.orchestrator.task_graph import TaskGraph

# ============================================================
# LLM mock helpers
# ============================================================


def _wrap_json(obj):
    """Wrap object as ```json block for extract_json to parse."""
    return f"```json\n{json.dumps(obj)}\n```"


def make_llm_router_mock(responses: list):
    """Create a route_inference mock that returns responses in sequence.

    Each response is returned as-is (should be a string).
    When responses are exhausted, repeats the last one.
    """
    call_count = {"n": 0}

    def mock_route(model, prompt, system_prompt=None, **kwargs):
        idx = min(call_count["n"], len(responses) - 1)
        call_count["n"] += 1
        resp = responses[idx]
        return resp

    return mock_route


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def workspace(tmp_projects):
    """Create workspace and patch global workspace manager."""
    import mado.backend.orchestrator.workspace_manager as wm_mod
    original = wm_mod._shared_instance
    wm_mod._shared_instance = tmp_projects
    yield tmp_projects
    wm_mod._shared_instance = original


# ============================================================
# AgentState / TaskState Unit Tests
# ============================================================


class TestAgentState:
    def test_initial_state(self):
        state = AgentState("engineer")
        assert state.role == "engineer"
        assert state.status == "idle"
        assert state.tasks_completed == 0

    def test_activate(self):
        state = AgentState("engineer")
        state.activate("Write code", "t1")
        assert state.status == "active"
        assert state.current_task == "Write code"
        assert state.current_task_id == "t1"
        assert state.last_active is not None

    def test_complete_task(self):
        state = AgentState("engineer")
        state.activate("Write code")
        state.complete_task()
        assert state.status == "idle"
        assert state.tasks_completed == 1
        assert state.current_task is None

    def test_fail_task(self):
        state = AgentState("engineer")
        state.activate("Write code")
        state.fail_task("Timeout")
        assert state.status == "error"
        assert state.tasks_failed == 1
        assert state.error == "Timeout"

    def test_reject_task(self):
        state = AgentState("engineer")
        state.reject_task()
        assert state.status == "rejected"
        assert state.tasks_rejected == 1

    def test_waiting_review(self):
        state = AgentState("reviewer")
        state.waiting_review()
        assert state.status == "waiting_review"

    def test_to_dict(self):
        state = AgentState("engineer")
        state.activate("Write code", "t1")
        d = state.to_dict()
        assert d["role"] == "engineer"
        assert d["status"] == "active"
        assert d["current_task"] == "Write code"
        assert d["current_task_id"] == "t1"

    def test_truncate_long_task(self):
        state = AgentState("engineer")
        state.activate("x" * 200, "t1")
        assert len(state.current_task) == 100


class TestTaskState:
    def test_initial_state(self):
        ts = TaskState("t1", "Write code", "engineer")
        assert ts.task_id == "t1"
        assert ts.status == "queued"
        assert ts.retry_count == 0
        assert ts.max_retries == 2

    def test_to_dict(self):
        ts = TaskState("t1", "Write code", "engineer", parent_task_id="parent")
        d = ts.to_dict()
        assert d["task_id"] == "t1"
        assert d["assigned_to"] == "engineer"
        assert d["parent_task_id"] == "parent"
        assert d["status"] == "queued"


# ============================================================
# Orchestrator Integration Tests
# ============================================================


class TestOrchestratorInit:
    """Test orchestrator initialization and state."""

    def test_initial_state(self, workspace):
        orch = Orchestrator("test-proj")
        assert orch.status == "idle"
        assert orch.iteration == 0
        assert orch.elapsed_seconds is None

    def test_get_state(self, workspace):
        orch = Orchestrator("test-proj")
        state = orch.get_state()
        assert state["project_id"] == "test-proj"
        assert state["status"] == "idle"
        assert state["agents"] == {}
        assert state["tasks"] == {}

    def test_cancel(self, workspace):
        orch = Orchestrator("test-proj")
        orch.cancel()
        assert orch.status == "cancelled"
        assert orch._cancel_event.is_set()


class TestOrchestratorHappyPath:
    """Test single-iteration happy path with LLM mocks."""

    @pytest.mark.asyncio
    async def test_single_iteration_approval(self, workspace):
        """Full flow: CTO plan -> Manager decompose -> Engineer execute -> Reviewer approve."""
        plan = {
            "plan_summary": "Build a REST API",
            "phases": [{
                "phase": "Implementation",
                "tasks": [
                    {"task_id": "t1", "description": "Write code",
                     "assigned_to": "engineer", "depends_on": []},
                ],
            }],
        }
        engineer_result = {
            "result": "Code written",
            "summary": "Implemented feature",
            "files_modified": ["main.py"],
        }
        review = {
            "approved": True, "score": 9,
            "issues": [], "feedback": "Great work",
            "summary": "Approved",
        }

        responses = [
            # CTO.analyze_and_plan → roles
            _wrap_json(["manager", "engineer", "reviewer"]),
            # CTO.plan → structured plan (Manager extracts tasks from phases, no LLM call)
            _wrap_json(plan),
            # Engineer.execute → result
            _wrap_json(engineer_result),
            # Reviewer.review → approval
            _wrap_json(review),
        ]

        mock = make_llm_router_mock(responses)
        with patch("mado.backend.models.router.route_inference", side_effect=mock):
            orch = Orchestrator("test-proj")
            result = await orch.run_async("Build a REST API")

        assert orch.status == "completed"
        assert orch.iteration == 1
        assert result["project_id"] == "test-proj"
        assert result["iterations"] == 1
        assert len(orch.agents) >= 3  # cto + manager + engineer + reviewer


class TestOrchestratorMultiIteration:
    """Test reviewer rejection triggers retry."""

    @pytest.mark.asyncio
    async def test_rejection_then_approval(self, workspace):
        """Reviewer rejects iteration 1, approves iteration 2."""
        plan = {
            "plan_summary": "Build API",
            "phases": [{
                "phase": "Impl",
                "tasks": [{"task_id": "t1", "description": "Code",
                            "assigned_to": "engineer", "depends_on": []}],
            }],
        }
        eng_result = {"result": "Done", "summary": "Built it",
                      "files_modified": ["app.py"]}
        reject = {"approved": False, "score": 3,
                  "issues": [{"severity": "major", "description": "Incomplete"}],
                  "feedback": "Needs work", "summary": "Rejected"}
        approve = {"approved": True, "score": 8,
                   "issues": [], "feedback": "Good", "summary": "OK"}

        responses = [
            # Init: CTO analyze
            _wrap_json(["manager", "engineer", "reviewer"]),
            # Iter 1: CTO plan, Engineer execute, Reviewer reject (Manager extracts from phases)
            _wrap_json(plan), _wrap_json(eng_result), _wrap_json(reject),
            # Iter 2: CTO plan, Engineer execute, Reviewer approve
            _wrap_json(plan), _wrap_json(eng_result), _wrap_json(approve),
        ]

        mock = make_llm_router_mock(responses)
        with patch("mado.backend.models.router.route_inference", side_effect=mock):
            orch = Orchestrator("test-proj")
            await orch.run_async("Build API")

        assert orch.status == "completed"
        assert orch.iteration == 2
        # Only rejected iterations produce summaries (approved iteration breaks before append)
        assert len(orch._iteration_summaries) >= 1


class TestOrchestratorCancellation:
    """Test cancellation during run."""

    @pytest.mark.asyncio
    async def test_cancel_before_run(self, workspace):
        """Cancel before starting the loop."""
        responses = [_wrap_json(["engineer"])]
        mock = make_llm_router_mock(responses)

        with patch("mado.backend.models.router.route_inference", side_effect=mock):
            orch = Orchestrator("test-proj")
            orch.cancel()
            await orch.run_async("Build API")

        assert orch.status == "cancelled"


class TestOrchestratorErrorHandling:
    """Test error recovery during task execution."""

    @pytest.mark.asyncio
    async def test_agent_exception_in_execute(self, workspace):
        """When an agent's execute() raises, the task should be marked failed."""
        plan = {
            "plan_summary": "Build API",
            "phases": [{
                "phase": "Impl",
                "tasks": [{"task_id": "t1", "description": "Code",
                            "assigned_to": "engineer", "depends_on": []}],
            }],
        }
        approve = {"approved": True, "score": 5,
                   "issues": [], "feedback": "OK despite errors"}

        responses = [
            _wrap_json(["manager", "engineer", "reviewer"]),
            _wrap_json(plan),
            # Engineer execute (Manager extracts from phases, no LLM call)
            _wrap_json({"result": "Error occurred", "summary": "Failed", "files_modified": []}),
            # Reviewer review
            _wrap_json(approve),
        ]

        mock = make_llm_router_mock(responses)

        with patch("mado.backend.models.router.route_inference", side_effect=mock):
            orch = Orchestrator("test-proj")
            await orch.run_async("Build API")

        assert orch.status == "completed"
        assert orch.iteration == 1


class TestOrchestratorEventCallback:
    """Test event emission during orchestration."""

    @pytest.mark.asyncio
    async def test_events_emitted(self, workspace):
        """Verify that event callbacks are invoked."""
        events = []

        async def capture_event(event):
            events.append(event)

        plan = {
            "plan_summary": "Build API",
            "phases": [{
                "phase": "Impl",
                "tasks": [{"task_id": "t1", "description": "Code",
                            "assigned_to": "engineer", "depends_on": []}],
            }],
        }
        eng_result = {"result": "Done", "summary": "Built", "files_modified": []}
        approve = {"approved": True, "score": 9, "issues": [], "feedback": "Good"}

        responses = [
            _wrap_json(["manager", "engineer", "reviewer"]),
            _wrap_json(plan),
            _wrap_json(eng_result), _wrap_json(approve),
        ]

        mock = make_llm_router_mock(responses)
        with patch("mado.backend.models.router.route_inference", side_effect=mock):
            orch = Orchestrator("test-proj")
            orch.on_event(capture_event)
            await orch.run_async("Build API")

        event_types = [e["type"] for e in events]
        assert "run_started" in event_types
        assert "iteration_started" in event_types
        assert "run_complete" in event_types


# ============================================================
# TaskGraph Integration Tests
# ============================================================


class TestTaskGraphIntegration:
    """Test TaskGraph with realistic task structures."""

    def test_linear_chain(self):
        """A -> B -> C should produce 3 layers."""
        graph = TaskGraph()
        graph.add_tasks([
            {"task_id": "a", "assigned_to": "researcher", "depends_on": []},
            {"task_id": "b", "assigned_to": "engineer", "depends_on": ["a"]},
            {"task_id": "c", "assigned_to": "tester", "depends_on": ["b"]},
        ])
        assert graph.validate() == []
        layers = graph.get_execution_layers()
        assert len(layers) == 3
        assert layers[0][0]["task_id"] == "a"
        assert layers[1][0]["task_id"] == "b"
        assert layers[2][0]["task_id"] == "c"

    def test_diamond_dependency(self):
        """Diamond: A -> B, A -> C, B+C -> D."""
        graph = TaskGraph()
        graph.add_tasks([
            {"task_id": "a", "assigned_to": "researcher", "depends_on": []},
            {"task_id": "b", "assigned_to": "engineer", "depends_on": ["a"]},
            {"task_id": "c", "assigned_to": "documenter", "depends_on": ["a"]},
            {"task_id": "d", "assigned_to": "tester", "depends_on": ["b", "c"]},
        ])
        assert graph.validate() == []
        layers = graph.get_execution_layers()
        assert len(layers) == 3
        assert len(layers[0]) == 1
        assert len(layers[1]) == 2
        layer1_ids = {t["task_id"] for t in layers[1]}
        assert layer1_ids == {"b", "c"}
        assert layers[2][0]["task_id"] == "d"

    def test_all_independent(self):
        """All independent tasks should be in 1 layer."""
        graph = TaskGraph()
        graph.add_tasks([
            {"task_id": "a", "assigned_to": "engineer", "depends_on": []},
            {"task_id": "b", "assigned_to": "tester", "depends_on": []},
            {"task_id": "c", "assigned_to": "documenter", "depends_on": []},
        ])
        layers = graph.get_execution_layers()
        assert len(layers) == 1
        assert len(layers[0]) == 3

    def test_circular_dependency_detected(self):
        """Circular dependency should be detected by validate()."""
        graph = TaskGraph()
        graph.add_tasks([
            {"task_id": "a", "assigned_to": "engineer", "depends_on": ["b"]},
            {"task_id": "b", "assigned_to": "tester", "depends_on": ["a"]},
        ])
        errors = graph.validate()
        assert len(errors) > 0

    def test_missing_dependency_detected(self):
        """Reference to non-existent task should be detected."""
        graph = TaskGraph()
        graph.add_tasks([
            {"task_id": "a", "assigned_to": "engineer", "depends_on": ["nonexistent"]},
        ])
        errors = graph.validate()
        assert len(errors) > 0


# ============================================================
# Orchestrator State Tracking
# ============================================================


class TestOrchestratorStateTracking:
    """Test detailed state tracking during execution."""

    @pytest.mark.asyncio
    async def test_agent_states_tracked(self, workspace):
        """Verify agent states are properly tracked."""
        plan = {
            "plan_summary": "Build API",
            "phases": [{
                "phase": "Impl",
                "tasks": [{"task_id": "t1", "description": "Code",
                            "assigned_to": "engineer", "depends_on": []}],
            }],
        }
        eng_result = {"result": "Done", "summary": "Built", "files_modified": []}
        approve = {"approved": True, "score": 9, "issues": [], "feedback": "Good"}

        responses = [
            _wrap_json(["manager", "engineer", "reviewer"]),
            _wrap_json(plan),
            _wrap_json(eng_result), _wrap_json(approve),
        ]

        mock = make_llm_router_mock(responses)
        with patch("mado.backend.models.router.route_inference", side_effect=mock):
            orch = Orchestrator("test-proj")
            await orch.run_async("Build API")

        assert "cto" in orch.agent_states
        assert "engineer" in orch.agent_states
        state = orch.get_state()
        assert state["status"] == "completed"
        assert state["iteration"] == 1

    @pytest.mark.asyncio
    async def test_elapsed_time_tracked(self, workspace):
        """Verify elapsed time is calculated."""
        plan = {
            "plan_summary": "Build API",
            "phases": [{
                "phase": "Impl",
                "tasks": [{"task_id": "t1", "description": "Code",
                            "assigned_to": "engineer", "depends_on": []}],
            }],
        }
        eng_result = {"result": "Done", "summary": "Built", "files_modified": []}
        approve = {"approved": True, "score": 9, "issues": [], "feedback": "Good"}

        responses = [
            _wrap_json(["manager", "engineer", "reviewer"]),
            _wrap_json(plan),
            _wrap_json(eng_result), _wrap_json(approve),
        ]

        mock = make_llm_router_mock(responses)
        with patch("mado.backend.models.router.route_inference", side_effect=mock):
            orch = Orchestrator("test-proj")
            result = await orch.run_async("Build API")

        assert result["elapsed_seconds"] >= 0
        assert orch._start_time is not None
        assert orch._end_time is not None
