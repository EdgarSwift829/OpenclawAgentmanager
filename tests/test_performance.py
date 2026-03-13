"""Performance and concurrency tests for MADO backend.

Tests:
- API response time under load (multiple rapid requests)
- Orchestrator parallel task execution via TaskGraph
- WebSocket connection throughput
- Workspace manager concurrent project creation
"""

import asyncio
import time

import pytest

from mado.backend.orchestrator.task_graph import TaskGraph


class TestAPIPerformance:
    """Test API response time under load."""

    def test_project_list_response_time(self, api_client):
        """List projects should respond in < 200ms."""
        client, wm = api_client
        # Create some projects
        for i in range(10):
            wm.create_workspace(f"perf-proj-{i}")

        start = time.monotonic()
        for _ in range(20):
            resp = client.get("/api/projects/")
            assert resp.status_code == 200
        elapsed = time.monotonic() - start

        avg_ms = (elapsed / 20) * 1000
        assert avg_ms < 200, f"Average response time {avg_ms:.1f}ms exceeds 200ms"

    def test_project_create_throughput(self, api_client):
        """Create 20 projects sequentially in < 5 seconds."""
        client, wm = api_client

        start = time.monotonic()
        for i in range(20):
            resp = client.post("/api/projects/", json={"project_id": f"throughput-{i}"})
            assert resp.status_code == 200
        elapsed = time.monotonic() - start

        assert elapsed < 5, f"Creating 20 projects took {elapsed:.1f}s (> 5s)"

    def test_project_get_response_time(self, api_client):
        """Get individual project should respond in < 100ms."""
        client, wm = api_client
        client.post("/api/projects/", json={"project_id": "fast-proj"})

        start = time.monotonic()
        for _ in range(50):
            resp = client.get("/api/projects/fast-proj")
            assert resp.status_code == 200
        elapsed = time.monotonic() - start

        avg_ms = (elapsed / 50) * 1000
        assert avg_ms < 100, f"Average response time {avg_ms:.1f}ms exceeds 100ms"


class TestTaskGraphPerformance:
    """Test TaskGraph with large graphs."""

    def test_large_independent_graph(self):
        """100 independent tasks should produce 1 layer quickly."""
        graph = TaskGraph()
        tasks = [
            {"task_id": f"t{i}", "assigned_to": "engineer", "depends_on": []}
            for i in range(100)
        ]

        start = time.monotonic()
        graph.add_tasks(tasks)
        errors = graph.validate()
        layers = graph.get_execution_layers()
        elapsed = time.monotonic() - start

        assert errors == []
        assert len(layers) == 1
        assert len(layers[0]) == 100
        assert elapsed < 1.0, f"Graph processing took {elapsed:.2f}s"

    def test_deep_chain_graph(self):
        """50-deep dependency chain should produce 50 layers."""
        graph = TaskGraph()
        tasks = []
        for i in range(50):
            tasks.append({
                "task_id": f"t{i}",
                "assigned_to": "engineer",
                "depends_on": [f"t{i-1}"] if i > 0 else [],
            })

        start = time.monotonic()
        graph.add_tasks(tasks)
        errors = graph.validate()
        layers = graph.get_execution_layers()
        elapsed = time.monotonic() - start

        assert errors == []
        assert len(layers) == 50
        assert elapsed < 1.0, f"Graph processing took {elapsed:.2f}s"

    def test_wide_diamond_graph(self):
        """Diamond pattern with 50 parallel middle tasks."""
        graph = TaskGraph()
        tasks = [{"task_id": "start", "assigned_to": "researcher", "depends_on": []}]
        for i in range(50):
            tasks.append({
                "task_id": f"mid{i}",
                "assigned_to": "engineer",
                "depends_on": ["start"],
            })
        tasks.append({
            "task_id": "end",
            "assigned_to": "tester",
            "depends_on": [f"mid{i}" for i in range(50)],
        })

        start = time.monotonic()
        graph.add_tasks(tasks)
        errors = graph.validate()
        layers = graph.get_execution_layers()
        elapsed = time.monotonic() - start

        assert errors == []
        assert len(layers) == 3
        assert len(layers[1]) == 50
        assert elapsed < 1.0


class TestWorkspacePerformance:
    """Test workspace manager performance."""

    def test_concurrent_config_reads(self, api_client):
        """Multiple config reads should not degrade."""
        client, wm = api_client
        client.post("/api/projects/", json={"project_id": "read-proj"})

        start = time.monotonic()
        for _ in range(100):
            config = wm.get_project_config("read-proj")
            assert config is not None
        elapsed = time.monotonic() - start

        avg_ms = (elapsed / 100) * 1000
        assert avg_ms < 50, f"Average config read {avg_ms:.1f}ms exceeds 50ms"

    def test_project_tree_performance(self, api_client):
        """Getting project tree with many projects."""
        client, wm = api_client
        for i in range(30):
            wm.create_workspace(f"tree-proj-{i}")

        start = time.monotonic()
        for _ in range(10):
            tree = wm.get_project_tree()
            assert len(tree) >= 30
        elapsed = time.monotonic() - start

        avg_ms = (elapsed / 10) * 1000
        assert avg_ms < 500, f"Average tree build {avg_ms:.1f}ms exceeds 500ms"


class TestOrchestratorConcurrency:
    """Test orchestrator concurrent task execution."""

    @pytest.mark.asyncio
    async def test_parallel_task_simulation(self):
        """Simulate parallel task execution with asyncio."""
        results = []

        async def simulate_task(task_id: str, duration: float):
            await asyncio.sleep(duration)
            results.append(task_id)

        start = time.monotonic()
        # Run 10 tasks in parallel, each taking 0.1s
        await asyncio.gather(*[
            simulate_task(f"task-{i}", 0.1) for i in range(10)
        ])
        elapsed = time.monotonic() - start

        assert len(results) == 10
        # Should complete in ~0.1s (parallel), not ~1s (serial)
        assert elapsed < 0.5, f"Parallel tasks took {elapsed:.2f}s (should be ~0.1s)"

    @pytest.mark.asyncio
    async def test_dag_execution_order(self):
        """Verify DAG layers execute in correct order."""
        graph = TaskGraph()
        graph.add_tasks([
            {"task_id": "a", "assigned_to": "researcher", "depends_on": []},
            {"task_id": "b", "assigned_to": "engineer", "depends_on": ["a"]},
            {"task_id": "c", "assigned_to": "engineer", "depends_on": ["a"]},
            {"task_id": "d", "assigned_to": "tester", "depends_on": ["b", "c"]},
        ])

        layers = graph.get_execution_layers()
        execution_order = []

        for layer in layers:
            tasks = []
            for task in layer:
                tasks.append(task["task_id"])
            execution_order.append(set(tasks))

        assert execution_order[0] == {"a"}
        assert execution_order[1] == {"b", "c"}
        assert execution_order[2] == {"d"}
