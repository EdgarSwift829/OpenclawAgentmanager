"""Tests for tool auto-binding (F) and task dependency graph DAG (H)."""

import asyncio
import time
import pytest
from unittest.mock import MagicMock

from mado.backend.orchestrator.agent_factory import AgentFactory, ROLE_TOOLS, _create_tools
from mado.backend.orchestrator.task_graph import TaskGraph
from mado.backend.orchestrator.orchestrator import Orchestrator
from mado.backend.models.model_manager import ModelManager


# ============================================================
# F. Tool auto-binding tests
# ============================================================

class TestToolAutoBinding:
    def test_role_tools_mapping_exists(self):
        """All agent roles should have a tool mapping."""
        from mado.backend.orchestrator.agent_factory import AGENT_CLASSES
        for role in AGENT_CLASSES:
            assert role in ROLE_TOOLS, f"Missing tool mapping for role: {role}"

    def test_engineer_has_exec_tools(self):
        assert "exec" in ROLE_TOOLS["engineer"]
        assert "file" in ROLE_TOOLS["engineer"]

    def test_researcher_has_web_tools(self):
        assert "web" in ROLE_TOOLS["researcher"]

    def test_cto_no_exec_tools(self):
        assert "exec" not in ROLE_TOOLS["cto"]

    def test_documenter_no_exec_tools(self):
        assert "exec" not in ROLE_TOOLS["documenter"]

    def test_create_tools_file(self, tmp_path):
        tools = _create_tools(["file"], str(tmp_path))
        assert len(tools) == 1
        assert type(tools[0]).__name__ == "FileTools"

    def test_create_tools_multiple(self, tmp_path):
        tools = _create_tools(["file", "exec", "memory"], str(tmp_path))
        assert len(tools) == 3
        names = {type(t).__name__ for t in tools}
        assert names == {"FileTools", "ExecTools", "MemoryTools"}

    def test_create_tools_web(self, tmp_path):
        tools = _create_tools(["web"], str(tmp_path))
        assert len(tools) == 1
        assert type(tools[0]).__name__ == "WebTools"

    def test_create_tools_empty(self, tmp_path):
        tools = _create_tools([], str(tmp_path))
        assert tools == []

    def test_factory_attaches_tools(self, tmp_path):
        """AgentFactory.create() should auto-attach tools to the agent."""
        mm = ModelManager()
        factory = AgentFactory(mm)
        agent = factory.create("engineer", str(tmp_path))
        assert len(agent.tools) > 0
        tool_names = {type(t).__name__ for t in agent.tools}
        assert "FileTools" in tool_names
        assert "ExecTools" in tool_names

    def test_factory_get_tool_mapping(self, tmp_path):
        mm = ModelManager()
        factory = AgentFactory(mm)
        factory.create("engineer", str(tmp_path))
        factory.create("cto", str(tmp_path))
        mapping = factory.get_tool_mapping()
        assert "engineer" in mapping
        assert "cto" in mapping
        assert "ExecTools" in mapping["engineer"]
        assert "ExecTools" not in mapping["cto"]


# ============================================================
# H. TaskGraph (DAG) tests
# ============================================================

class TestTaskGraph:
    def test_empty_graph(self):
        g = TaskGraph()
        layers = g.get_execution_layers()
        assert layers == []

    def test_single_task(self):
        g = TaskGraph()
        g.add_task({"task_id": "a", "assigned_to": "engineer"})
        layers = g.get_execution_layers()
        assert len(layers) == 1
        assert layers[0][0]["task_id"] == "a"

    def test_two_independent_tasks(self):
        g = TaskGraph()
        g.add_tasks([
            {"task_id": "a", "assigned_to": "engineer"},
            {"task_id": "b", "assigned_to": "tester"},
        ])
        layers = g.get_execution_layers()
        assert len(layers) == 1  # Both in same layer (parallel)
        assert len(layers[0]) == 2

    def test_linear_chain(self):
        g = TaskGraph()
        g.add_tasks([
            {"task_id": "a", "assigned_to": "cto"},
            {"task_id": "b", "assigned_to": "engineer", "depends_on": ["a"]},
            {"task_id": "c", "assigned_to": "tester", "depends_on": ["b"]},
        ])
        layers = g.get_execution_layers()
        assert len(layers) == 3
        assert layers[0][0]["task_id"] == "a"
        assert layers[1][0]["task_id"] == "b"
        assert layers[2][0]["task_id"] == "c"

    def test_diamond_pattern(self):
        """Diamond: A -> B,C -> D (B and C are parallel)."""
        g = TaskGraph()
        g.add_tasks([
            {"task_id": "a", "assigned_to": "cto"},
            {"task_id": "b", "assigned_to": "engineer", "depends_on": ["a"]},
            {"task_id": "c", "assigned_to": "tester", "depends_on": ["a"]},
            {"task_id": "d", "assigned_to": "reviewer", "depends_on": ["b", "c"]},
        ])
        layers = g.get_execution_layers()
        assert len(layers) == 3
        # Layer 0: a
        assert len(layers[0]) == 1
        # Layer 1: b and c (parallel)
        assert len(layers[1]) == 2
        layer1_ids = {t["task_id"] for t in layers[1]}
        assert layer1_ids == {"b", "c"}
        # Layer 2: d
        assert len(layers[2]) == 1

    def test_cycle_detection(self):
        g = TaskGraph()
        g.add_tasks([
            {"task_id": "a", "depends_on": ["b"]},
            {"task_id": "b", "depends_on": ["a"]},
        ])
        errors = g.validate()
        assert any("Circular" in e for e in errors)

    def test_missing_dependency(self):
        g = TaskGraph()
        g.add_task({"task_id": "a", "depends_on": ["nonexistent"]})
        errors = g.validate()
        assert any("unknown" in e for e in errors)

    def test_auto_generate_task_id(self):
        g = TaskGraph()
        g.add_task({"assigned_to": "engineer", "description": "code"})
        assert g.task_count == 1
        assert g.task_ids[0].startswith("engineer_")

    def test_depends_on_string(self):
        """depends_on can be a single string instead of a list."""
        g = TaskGraph()
        g.add_tasks([
            {"task_id": "a", "assigned_to": "cto"},
            {"task_id": "b", "assigned_to": "engineer", "depends_on": "a"},
        ])
        layers = g.get_execution_layers()
        assert len(layers) == 2

    def test_get_task(self):
        g = TaskGraph()
        g.add_task({"task_id": "x", "assigned_to": "eng", "description": "hello"})
        task = g.get_task("x")
        assert task["description"] == "hello"
        assert g.get_task("nonexistent") is None

    def test_complex_dag(self):
        """
        A ---> B ---> E
        |             ^
        +---> C --+   |
        |         +-> D
        +---> F (independent)
        """
        g = TaskGraph()
        g.add_tasks([
            {"task_id": "A", "assigned_to": "cto"},
            {"task_id": "B", "assigned_to": "engineer", "depends_on": ["A"]},
            {"task_id": "C", "assigned_to": "researcher", "depends_on": ["A"]},
            {"task_id": "F", "assigned_to": "documenter", "depends_on": ["A"]},
            {"task_id": "D", "assigned_to": "tester", "depends_on": ["C"]},
            {"task_id": "E", "assigned_to": "reviewer", "depends_on": ["B", "D"]},
        ])
        layers = g.get_execution_layers()
        assert len(layers) == 4
        # Layer 0: A
        assert {t["task_id"] for t in layers[0]} == {"A"}
        # Layer 1: B, C, F (all depend only on A)
        assert {t["task_id"] for t in layers[1]} == {"B", "C", "F"}
        # Layer 2: D (depends on C)
        assert {t["task_id"] for t in layers[2]} == {"D"}
        # Layer 3: E (depends on B and D)
        assert {t["task_id"] for t in layers[3]} == {"E"}

    def test_invalid_graph_raises_on_execution(self):
        g = TaskGraph()
        g.add_tasks([
            {"task_id": "a", "depends_on": ["b"]},
            {"task_id": "b", "depends_on": ["a"]},
        ])
        with pytest.raises(ValueError, match="Circular"):
            g.get_execution_layers()


# ============================================================
# DAG integration with Orchestrator
# ============================================================

class TestOrchestratorDAG:
    def _mock_agent(self, role, delay=0):
        agent = MagicMock()
        agent.role = role

        def execute(task):
            if delay:
                time.sleep(delay)
            return {"role": role, "result": f"{role} done", "task_id": task.get("task_id")}

        agent.execute = execute
        return agent

    @pytest.mark.asyncio
    async def test_dag_execution_order(self):
        """Tasks with task_id and depends_on should execute in DAG order."""
        orch = Orchestrator("test-dag")
        for role in ["cto", "engineer", "tester", "reviewer"]:
            orch.agents[role] = self._mock_agent(role)
            orch.agent_states[role] = MagicMock()
            orch.agent_states[role].activate = MagicMock()
            orch.agent_states[role].complete_task = MagicMock()
            orch.message_bus.register(role)

        tasks = [
            {"task_id": "design", "assigned_to": "cto", "description": "design"},
            {"task_id": "impl", "assigned_to": "engineer", "depends_on": ["design"], "description": "impl"},
            {"task_id": "test", "assigned_to": "tester", "depends_on": ["impl"], "description": "test"},
        ]

        results = await orch._execute_task_graph(tasks)
        assert len(results) == 3
        # Verify order: design before impl before test
        task_ids = [r.get("task_id") for r in results]
        assert task_ids.index("design") < task_ids.index("impl")
        assert task_ids.index("impl") < task_ids.index("test")

    @pytest.mark.asyncio
    async def test_dag_parallel_layer(self):
        """Independent tasks in DAG should run in parallel."""
        orch = Orchestrator("test-dag-parallel")
        for role in ["cto", "engineer", "tester"]:
            orch.agents[role] = self._mock_agent(role, delay=0.1)
            orch.agent_states[role] = MagicMock()
            orch.agent_states[role].activate = MagicMock()
            orch.agent_states[role].complete_task = MagicMock()
            orch.message_bus.register(role)

        tasks = [
            {"task_id": "a", "assigned_to": "cto", "description": "a"},
            {"task_id": "b", "assigned_to": "engineer", "depends_on": ["a"], "description": "b"},
            {"task_id": "c", "assigned_to": "tester", "depends_on": ["a"], "description": "c"},
        ]

        start = time.time()
        results = await orch._execute_task_graph(tasks)
        elapsed = time.time() - start

        assert len(results) == 3
        # b and c should run in parallel (~0.1s), not sequential (~0.2s)
        # Total: ~0.2s (a sequential + b,c parallel), not ~0.3s
        assert elapsed < 0.35, f"DAG took {elapsed:.2f}s, expected < 0.35s"

    @pytest.mark.asyncio
    async def test_fallback_to_simple_classification(self):
        """Tasks without task_id should fall back to simple parallel/sequential."""
        orch = Orchestrator("test-fallback")
        for role in ["engineer", "tester"]:
            orch.agents[role] = self._mock_agent(role)
            orch.agent_states[role] = MagicMock()
            orch.agent_states[role].activate = MagicMock()
            orch.agent_states[role].complete_task = MagicMock()
            orch.message_bus.register(role)

        tasks = [
            {"assigned_to": "engineer", "description": "code"},
            {"assigned_to": "tester", "description": "test"},
        ]

        results = await orch._execute_task_graph(tasks)
        assert len(results) == 2
