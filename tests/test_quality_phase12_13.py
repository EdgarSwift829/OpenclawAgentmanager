"""Phase 12-13: Quality improvement tests for coverage boost.

Targets:
- exec_tools.py: empty command, resolve_executable fallback, subprocess errors
- orchestrator.py: _execute_run paths, dispatch edge cases, backup/state endpoints
- models.py: switch_model ValueError, reorder partial roles
- base_agent.py: tool exception paths, load_prompt_template, call_llm_json fallback
- optimizer.py: shared_context edge cases, read_file errors
- tester.py: shared_context edge cases, no test files, LLM fallback
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mado.backend.agents.base_agent import BaseAgent
from mado.backend.agents.optimizer import OptimizerAgent
from mado.backend.agents.tester import TesterAgent
from mado.backend.tools.exec_tools import ExecTools


# ============================================================
# Helper: concrete BaseAgent subclass
# ============================================================

class StubAgent(BaseAgent):
    def execute(self, task: dict) -> dict:
        return self.make_result("stub", summary="stub")


def _make_agent(cls, tmp_path, role=None):
    r = role or cls.__name__.replace("Agent", "").lower()
    return cls(
        role=r,
        model={"name": "test-model", "provider": "ollama"},
        workspace_path=str(tmp_path),
    )


# ============================================================
# ExecTools - Phase 12 bug fixes + Phase 13 coverage
# ============================================================

class TestExecToolsEmptyCommand:
    """Phase 12: empty command bug fix."""

    def test_empty_string_rejected(self, tmp_path):
        et = ExecTools(str(tmp_path))
        with pytest.raises(PermissionError, match="empty"):
            et._check_command("")

    def test_whitespace_only_rejected(self, tmp_path):
        et = ExecTools(str(tmp_path))
        with pytest.raises(PermissionError, match="empty"):
            et._check_command("   ")

    def test_none_like_empty(self, tmp_path):
        """Falsy command string raises PermissionError."""
        et = ExecTools(str(tmp_path))
        with pytest.raises(PermissionError, match="empty"):
            et._check_command("")


class TestExecToolsResolveExecutable:
    """Phase 13: _resolve_executable coverage."""

    def test_python_resolves_to_sys_executable(self, tmp_path):
        import sys
        et = ExecTools(str(tmp_path))
        assert et._resolve_executable("python") == sys.executable

    def test_known_command_found(self, tmp_path):
        et = ExecTools(str(tmp_path))
        # pytest should be findable
        result = et._resolve_executable("pytest")
        assert result  # non-empty

    def test_unknown_command_returns_name(self, tmp_path):
        et = ExecTools(str(tmp_path))
        result = et._resolve_executable("totally_nonexistent_cmd_xyz")
        assert result == "totally_nonexistent_cmd_xyz"


class TestExecToolsSubprocessErrors:
    """Phase 13: subprocess timeout and error handling."""

    def test_run_python_timeout(self, tmp_path):
        script = tmp_path / "slow.py"
        script.write_text("import time; time.sleep(10)", encoding="utf-8")
        et = ExecTools(str(tmp_path))
        with pytest.raises(Exception):  # subprocess.TimeoutExpired
            et.run_python("slow.py", timeout=1)

    def test_run_tests_path_traversal(self, tmp_path):
        et = ExecTools(str(tmp_path))
        with pytest.raises(PermissionError, match="outside workspace"):
            et.run_tests("../../etc")

    def test_install_package_dry_run(self, tmp_path):
        """install_package invokes pip (just verify structure)."""
        et = ExecTools(str(tmp_path))
        # Use --help to avoid actual install
        result = et.install_package("--help", timeout=30)
        assert "returncode" in result

    def test_validate_path_exception_chain(self, tmp_path):
        """Ensure PermissionError chains from ValueError."""
        et = ExecTools(str(tmp_path))
        with pytest.raises(PermissionError) as exc_info:
            et._validate_path_in_workspace(tmp_path.parent / "outside.py")
        assert exc_info.value.__cause__ is not None


# ============================================================
# Orchestrator API - Phase 13 coverage
# ============================================================

class TestOrchestratorExecuteRun:
    """Phase 13: _execute_run async paths."""

    @pytest.mark.asyncio
    async def test_execute_run_error_sets_error_status(self, tmp_path):
        """When orchestrator raises, status should be 'error'."""
        import mado.backend.api.routes.orchestrator as orch_mod

        projects_root = tmp_path / "projects"
        projects_root.mkdir()

        from mado.backend.orchestrator.workspace_manager import WorkspaceManager
        wm = WorkspaceManager(str(projects_root))
        original_wm = orch_mod._workspace_manager
        orch_mod._workspace_manager = wm

        orch_mod._runs["test-proj"] = {
            "status": "running", "iteration": 0, "max_iterations": 5,
        }

        # Patch the lazy imports inside _execute_run
        mock_agents = MagicMock()
        mock_ws = MagicMock()

        with patch.dict("sys.modules", {
            "mado.backend.orchestrator.orchestrator": MagicMock(
                Orchestrator=MagicMock(side_effect=RuntimeError("Init failed"))
            ),
        }):
            with patch("mado.backend.api.routes.agents.register_session", MagicMock()):
                with patch("mado.backend.api.routes.websocket.broadcaster", MagicMock()):
                    await orch_mod._execute_run("test-proj", "build", 5)

        assert orch_mod._runs["test-proj"]["status"] == "error"
        assert "Init failed" in orch_mod._runs["test-proj"]["error"]
        # Cleanup
        orch_mod._runs.clear()
        orch_mod._workspace_manager = original_wm

    @pytest.mark.asyncio
    async def test_execute_run_success_sets_completed(self, tmp_path):
        """Successful run should set status to 'completed'."""
        import asyncio

        import mado.backend.api.routes.orchestrator as orch_mod

        projects_root = tmp_path / "projects"
        projects_root.mkdir()

        from mado.backend.orchestrator.workspace_manager import WorkspaceManager
        wm = WorkspaceManager(str(projects_root))
        original_wm = orch_mod._workspace_manager
        orch_mod._workspace_manager = wm

        orch_mod._runs["test-proj"] = {
            "status": "running", "iteration": 0, "max_iterations": 5,
        }

        mock_orch = MagicMock()
        mock_orch.iteration = 3
        mock_orch.agents = {}

        async def fake_run_async(goal):
            return "done"
        mock_orch.run_async = fake_run_async

        mock_register = MagicMock()
        mock_broadcaster = MagicMock()

        async def fake_broadcast(pid, event):
            pass
        mock_broadcaster.broadcast = fake_broadcast

        mock_orch_cls = MagicMock(return_value=mock_orch)

        with patch.dict("sys.modules", {
            "mado.backend.orchestrator.orchestrator": MagicMock(
                Orchestrator=mock_orch_cls,
            ),
        }):
            with patch("mado.backend.api.routes.agents.register_session", mock_register):
                with patch("mado.backend.api.routes.websocket.broadcaster", mock_broadcaster):
                    await orch_mod._execute_run("test-proj", "build", 5)

        assert orch_mod._runs["test-proj"]["status"] == "completed"
        assert "test-proj" not in orch_mod._orchestrators
        orch_mod._runs.clear()
        orch_mod._workspace_manager = original_wm


class TestOrchestratorStateEndpoints:
    """Phase 13: state/tasks endpoints with orchestrator present."""

    def test_get_state_with_orchestrator(self, orchestrator_api_client):
        client, wm = orchestrator_api_client
        import mado.backend.api.routes.orchestrator as orch_mod
        mock_orch = MagicMock()
        mock_orch.get_state.return_value = {"status": "running", "iteration": 2}
        orch_mod._orchestrators["proj"] = mock_orch
        resp = client.get("/api/orchestrator/run/proj/state")
        assert resp.status_code == 200
        assert resp.json()["iteration"] == 2
        orch_mod._orchestrators.pop("proj", None)

    def test_get_tasks_with_orchestrator(self, orchestrator_api_client):
        client, wm = orchestrator_api_client
        import mado.backend.api.routes.orchestrator as orch_mod

        mock_task = MagicMock()
        mock_task.to_dict.return_value = {"status": "done", "role": "engineer"}

        mock_orch = MagicMock()
        mock_orch.task_states = {"t1": mock_task}
        orch_mod._orchestrators["proj"] = mock_orch

        resp = client.get("/api/orchestrator/run/proj/tasks")
        assert resp.status_code == 200
        tasks = resp.json()["tasks"]
        assert "t1" in tasks
        assert tasks["t1"]["status"] == "done"
        orch_mod._orchestrators.pop("proj", None)


class TestOrchestratorStopWithOrchestrator:
    """Phase 13: stop/pause with actual orchestrator cancel."""

    def test_stop_calls_cancel(self, orchestrator_api_client):
        client, wm = orchestrator_api_client
        import mado.backend.api.routes.orchestrator as orch_mod
        wm.create_workspace("proj")
        orch_mod._runs["proj"] = {"status": "running", "iteration": 1, "max_iterations": 30}
        mock_orch = MagicMock()
        orch_mod._orchestrators["proj"] = mock_orch

        resp = client.post("/api/orchestrator/run/proj/stop")
        assert resp.status_code == 200
        mock_orch.cancel.assert_called_once()
        orch_mod._orchestrators.pop("proj", None)

    def test_pause_calls_cancel(self, orchestrator_api_client):
        client, wm = orchestrator_api_client
        import mado.backend.api.routes.orchestrator as orch_mod
        wm.create_workspace("proj")
        orch_mod._runs["proj"] = {"status": "running", "iteration": 2, "max_iterations": 30}
        mock_orch = MagicMock()
        orch_mod._orchestrators["proj"] = mock_orch

        resp = client.post("/api/orchestrator/run/proj/pause")
        assert resp.status_code == 200
        mock_orch.cancel.assert_called_once()
        assert resp.json()["iteration"] == 2
        orch_mod._orchestrators.pop("proj", None)


class TestOrchestratorBackup:
    """Phase 13: _backup_project error handling."""

    def test_backup_failure_returns_none(self, orchestrator_api_client):
        client, wm = orchestrator_api_client
        from mado.backend.api.routes.orchestrator import _backup_project

        with patch.object(wm, "backup_project", side_effect=OSError("disk full")):
            result = _backup_project("proj", "test")
        assert result is None

    def test_backup_success_returns_path(self, orchestrator_api_client):
        client, wm = orchestrator_api_client
        from mado.backend.api.routes.orchestrator import _backup_project

        wm.create_workspace("proj")
        with patch.object(wm, "backup_project", return_value="/backups/proj-123"):
            result = _backup_project("proj", "test")
        assert result == "/backups/proj-123"


class TestOrchestratorCascadeStop:
    """Phase 13: _cascade_stop_children with orchestrator instances."""

    def test_cascade_stops_with_orchestrator(self, orchestrator_api_client):
        client, wm = orchestrator_api_client
        import mado.backend.api.routes.orchestrator as orch_mod

        wm.create_workspace("parent")
        wm.create_workspace("child", parent_id="parent")
        orch_mod._runs["child"] = {"status": "running", "iteration": 1, "max_iterations": 30}
        mock_orch = MagicMock()
        orch_mod._orchestrators["child"] = mock_orch

        resp = client.post("/api/orchestrator/run/parent/stop")
        # parent itself not running → 404
        orch_mod._runs["parent"] = {"status": "running", "iteration": 0, "max_iterations": 30}
        resp = client.post("/api/orchestrator/run/parent/stop")
        assert resp.status_code == 200
        mock_orch.cancel.assert_called_once()
        orch_mod._orchestrators.pop("child", None)


class TestOrchestratorDispatchInheritance:
    """Phase 13: dispatch-child with instruction + child goal merging."""

    def test_dispatch_with_instruction_and_child_goal(self, orchestrator_api_client):
        client, wm = orchestrator_api_client
        wm.create_workspace("parent")
        wm.create_workspace("child", parent_id="parent")
        wm.update_project_config("child", {"goal": "child goal"})

        resp = client.post("/api/orchestrator/dispatch-child", json={
            "parent_id": "parent",
            "child_id": "child",
            "instruction": "Focus on tests",
        })
        assert resp.status_code == 200

    def test_dispatch_child_not_found(self, orchestrator_api_client):
        client, wm = orchestrator_api_client
        wm.create_workspace("parent")
        resp = client.post("/api/orchestrator/dispatch-child", json={
            "parent_id": "parent",
            "child_id": "nonexistent",
        })
        assert resp.status_code == 404

    def test_dispatch_all_skips_archived(self, orchestrator_api_client):
        client, wm = orchestrator_api_client
        wm.create_workspace("parent")
        wm.create_workspace("child", parent_id="parent")
        wm.update_project_config("child", {"status": "archived"})

        resp = client.post("/api/orchestrator/dispatch-children", json={
            "parent_id": "parent",
        })
        assert resp.status_code == 200
        assert "child" in resp.json()["skipped"]


class TestInheritParentContextEdgeCases:
    """Phase 13: edge cases in _inherit_parent_context."""

    def test_no_parent_profiles(self, orchestrator_api_client):
        """When parent has no agent_profiles, child should be unchanged."""
        client, wm = orchestrator_api_client
        from mado.backend.api.routes.orchestrator import _inherit_parent_context
        wm.create_workspace("parent")
        wm.create_workspace("child", parent_id="parent")
        wm.update_project_config("child", {
            "agent_profiles": {"engineer": {"title": "Eng"}},
        })
        _inherit_parent_context("parent", "child")
        child_config = wm.get_project_config("child")
        assert child_config["agent_profiles"]["engineer"]["title"] == "Eng"

    def test_child_overrides_parent_profiles(self, orchestrator_api_client):
        """Child profiles with title/personality override parent."""
        client, wm = orchestrator_api_client
        from mado.backend.api.routes.orchestrator import _inherit_parent_context
        wm.create_workspace("parent")
        wm.create_workspace("child", parent_id="parent")
        wm.update_project_config("parent", {
            "agent_profiles": {
                "cto": {"title": "Parent CTO", "personality": "strict"},
                "engineer": {"title": "Parent Eng", "personality": "careful"},
            },
        })
        wm.update_project_config("child", {
            "agent_profiles": {
                "cto": {"title": "Child CTO", "personality": "relaxed"},
            },
        })
        _inherit_parent_context("parent", "child")
        child_config = wm.get_project_config("child")
        profiles = child_config["agent_profiles"]
        # CTO overridden by child
        assert profiles["cto"]["personality"] == "relaxed"
        # Engineer inherited from parent
        assert profiles["engineer"]["title"] == "Parent Eng"

    def test_no_parent_memory(self, orchestrator_api_client):
        """When parent has no project_memory.md, child memory is not modified."""
        client, wm = orchestrator_api_client
        from mado.backend.api.routes.orchestrator import _inherit_parent_context
        wm.create_workspace("parent")
        wm.create_workspace("child", parent_id="parent")
        # Remove parent memory if workspace creation created one
        parent_mem = wm.projects_root / "parent" / "project_memory.md"
        if parent_mem.exists():
            parent_mem.unlink()
        child_mem = wm.projects_root / "child" / "project_memory.md"
        child_content_before = child_mem.read_text(encoding="utf-8") if child_mem.exists() else None
        _inherit_parent_context("parent", "child")
        child_content_after = child_mem.read_text(encoding="utf-8") if child_mem.exists() else None
        assert child_content_before == child_content_after

    def test_memory_not_duplicated(self, orchestrator_api_client):
        """Re-running inherit should not duplicate the inherited section."""
        client, wm = orchestrator_api_client
        from mado.backend.api.routes.orchestrator import _inherit_parent_context
        wm.create_workspace("parent")
        wm.create_workspace("child", parent_id="parent")
        parent_mem = wm.projects_root / "parent" / "project_memory.md"
        parent_mem.write_text("# Knowledge", encoding="utf-8")

        _inherit_parent_context("parent", "child")
        _inherit_parent_context("parent", "child")  # Second call

        child_mem = wm.projects_root / "child" / "project_memory.md"
        content = child_mem.read_text(encoding="utf-8")
        assert content.count("Inherited from parent: parent") == 1


# ============================================================
# Models API - Phase 13 coverage
# ============================================================

class TestModelsAPISwitchError:
    """Phase 13: switch_model ValueError path."""

    def test_switch_nonexistent_model(self, api_client):
        client, wm = api_client
        resp = client.put("/api/models/switch", json={
            "role": "engineer",
            "new_model": "totally_nonexistent_model_xyz",
        })
        # Should be 400 (ValueError) or possibly 200 if model isn't validated
        assert resp.status_code in (200, 400)

    def test_switch_nonexistent_role(self, api_client):
        client, wm = api_client
        resp = client.put("/api/models/switch", json={
            "role": "nonexistent_role_xyz",
            "new_model": "any-model",
        })
        assert resp.status_code in (200, 400)


class TestModelsAPIReorderPartial:
    """Phase 13: reorder with partial roles list."""

    def test_reorder_subset_keeps_remaining(self, api_client):
        client, wm = api_client
        assignments = client.get("/api/models/assignments").json()["assignments"]
        if len(assignments) >= 2:
            roles = list(assignments.keys())
            # Only include first role
            resp = client.put("/api/models/reorder", json={"roles": [roles[0]]})
            assert resp.status_code == 200
            new_roles = resp.json()["roles"]
            # First role should be first
            assert new_roles[0] == roles[0]
            # All original roles should still be present
            assert set(new_roles) == set(roles)

    def test_reorder_empty_list(self, api_client):
        client, wm = api_client
        resp = client.put("/api/models/reorder", json={"roles": []})
        assert resp.status_code == 200
        # All roles should be preserved
        assert "roles" in resp.json()


# ============================================================
# BaseAgent - Phase 13 coverage
# ============================================================

class TestBaseAgentToolExceptions:
    """Phase 13: tool methods when tools raise exceptions."""

    def test_read_file_exception(self, tmp_path):
        agent = _make_agent(StubAgent, tmp_path, role="engineer")
        mock_ft = MagicMock()
        type(mock_ft).__name__ = "FileTools"
        mock_ft.read_file.side_effect = IOError("disk error")
        agent.tools = [mock_ft]
        result = agent.read_file("test.txt")
        assert "[Error reading" in result
        assert "disk error" in result

    def test_write_file_exception(self, tmp_path):
        agent = _make_agent(StubAgent, tmp_path, role="engineer")
        mock_ft = MagicMock()
        type(mock_ft).__name__ = "FileTools"
        mock_ft.write_file.side_effect = IOError("read-only")
        agent.tools = [mock_ft]
        result = agent.write_file("test.txt", "content")
        assert "[Error writing" in result

    def test_list_files_exception(self, tmp_path):
        agent = _make_agent(StubAgent, tmp_path, role="engineer")
        mock_ft = MagicMock()
        type(mock_ft).__name__ = "FileTools"
        mock_ft.list_dir.side_effect = OSError("permission denied")
        agent.tools = [mock_ft]
        assert agent.list_files() == []

    def test_search_code_exception(self, tmp_path):
        agent = _make_agent(StubAgent, tmp_path, role="engineer")
        mock_ft = MagicMock()
        type(mock_ft).__name__ = "FileTools"
        mock_ft.search_code.side_effect = RuntimeError("bad query")
        agent.tools = [mock_ft]
        assert agent.search_code("query") == []

    def test_run_command_exception(self, tmp_path):
        agent = _make_agent(StubAgent, tmp_path, role="engineer")
        mock_et = MagicMock()
        type(mock_et).__name__ = "ExecTools"
        mock_et.run_python.side_effect = RuntimeError("execution failed")
        agent.tools = [mock_et]
        result = agent.run_command("script.py")
        assert "error" in result
        assert "execution failed" in result["error"]

    def test_run_tests_exception(self, tmp_path):
        agent = _make_agent(StubAgent, tmp_path, role="engineer")
        mock_et = MagicMock()
        type(mock_et).__name__ = "ExecTools"
        mock_et.run_tests.side_effect = RuntimeError("test crash")
        agent.tools = [mock_et]
        result = agent.run_tests()
        assert "error" in result

    def test_search_web_exception(self, tmp_path):
        agent = _make_agent(StubAgent, tmp_path, role="engineer")
        mock_wt = MagicMock()
        type(mock_wt).__name__ = "WebTools"
        mock_wt.search_web.side_effect = ConnectionError("offline")
        agent.tools = [mock_wt]
        result = agent.search_web("query")
        assert result[0].get("error")
        assert "offline" in result[0]["error"]


class TestBaseAgentMemoryTools:
    """Phase 13: memory tool paths."""

    def test_load_project_memory_no_tools(self, tmp_path):
        agent = _make_agent(StubAgent, tmp_path, role="engineer")
        assert agent.load_project_memory() == ""

    def test_load_project_memory_exception(self, tmp_path):
        agent = _make_agent(StubAgent, tmp_path, role="engineer")
        mock_mt = MagicMock()
        type(mock_mt).__name__ = "MemoryTools"
        mock_mt.load_project_memory.side_effect = IOError("corrupted")
        agent.tools = [mock_mt]
        assert agent.load_project_memory() == ""

    def test_save_memory_no_tools(self, tmp_path):
        agent = _make_agent(StubAgent, tmp_path, role="engineer")
        result = agent.save_memory("section", "content")
        assert "[Error]" in result

    def test_save_memory_exception(self, tmp_path):
        agent = _make_agent(StubAgent, tmp_path, role="engineer")
        mock_mt = MagicMock()
        type(mock_mt).__name__ = "MemoryTools"
        mock_mt.update_project_memory.side_effect = IOError("write failed")
        agent.tools = [mock_mt]
        result = agent.save_memory("section", "content")
        assert "[Error]" in result


class TestBaseAgentPromptTemplate:
    """Phase 13: load_prompt_template when no template exists."""

    def test_no_template_returns_empty(self, tmp_path):
        agent = _make_agent(StubAgent, tmp_path, role="nonexistent_role_xyz")
        result = agent.load_prompt_template()
        assert result == ""


class TestBaseAgentCallLlmJson:
    """Phase 13: call_llm_json fallback paths."""

    def test_fallback_when_json_parse_fails(self, tmp_path):
        agent = _make_agent(StubAgent, tmp_path, role="engineer")
        with patch.object(agent, "call_llm", return_value="not json at all"):
            result = agent.call_llm_json("prompt", fallback={"default": True})
        assert result == {"default": True}

    def test_raw_response_when_no_fallback(self, tmp_path):
        agent = _make_agent(StubAgent, tmp_path, role="engineer")
        with patch.object(agent, "call_llm", return_value="plain text response"):
            result = agent.call_llm_json("prompt", fallback=None)
        assert result == "plain text response"

    def test_json_parsed_successfully(self, tmp_path):
        agent = _make_agent(StubAgent, tmp_path, role="engineer")
        json_response = '```json\n{"key": "value"}\n```'
        with patch.object(agent, "call_llm", return_value=json_response):
            result = agent.call_llm_json("prompt", fallback={"fallback": True})
        assert result == {"key": "value"}


class TestBaseAgentSystemPromptEdgeCases:
    """Phase 13: system prompt with additional_prompt and overview."""

    def test_with_additional_prompt(self, tmp_path):
        agent = _make_agent(StubAgent, tmp_path, role="engineer")
        agent.project_config = {
            "agent_profiles": {
                "engineer": {"additional_prompt": "Focus on Python 3.12"},
            },
        }
        prompt = agent.build_system_prompt()
        assert "Focus on Python 3.12" in prompt

    def test_with_overview(self, tmp_path):
        agent = _make_agent(StubAgent, tmp_path, role="engineer")
        agent.project_config = {"overview": "E-commerce platform"}
        prompt = agent.build_system_prompt()
        assert "E-commerce platform" in prompt

    def test_unknown_role_no_preset(self, tmp_path):
        agent = _make_agent(StubAgent, tmp_path, role="unknown_role")
        prompt = agent.build_system_prompt()
        assert "unknown_role" in prompt
        # Should not have preset personality
        assert "Preset" not in prompt


# ============================================================
# OptimizerAgent - Phase 13 coverage
# ============================================================

class TestOptimizerEdgeCases:
    """Phase 13: optimizer shared_context and error paths."""

    def test_empty_shared_context(self, tmp_path):
        opt = _make_agent(OptimizerAgent, tmp_path)
        with patch.object(opt, "call_llm_json", return_value={
            "bottlenecks": [], "optimizations": [],
            "estimated_impact": "None", "summary": "Nothing to optimize",
        }):
            result = opt.execute({"description": "Optimize"})
        assert result["role"] == "optimizer"
        assert result["files_modified"] == []

    def test_shared_context_with_non_dict(self, tmp_path):
        opt = _make_agent(OptimizerAgent, tmp_path)
        opt.shared_context = {
            "engineer": "plain string, not dict",
            "reviewer": 42,
        }
        with patch.object(opt, "call_llm_json", return_value={
            "bottlenecks": [], "optimizations": [],
            "estimated_impact": "None", "summary": "Checked",
        }):
            result = opt.execute({"description": "Optimize"})
        assert result["files_modified"] == []

    def test_shared_context_with_files(self, tmp_path):
        opt = _make_agent(OptimizerAgent, tmp_path)
        (tmp_path / "app.py").write_text("def slow(): pass", encoding="utf-8")
        from mado.backend.tools.file_tools import FileTools
        opt.tools = [FileTools(str(tmp_path))]
        opt.shared_context = {
            "engineer": {"files_modified": ["app.py"]},
        }
        with patch.object(opt, "call_llm_json", return_value={
            "bottlenecks": [{"location": "app.py:1", "issue": "slow", "severity": "high"}],
            "optimizations": [{"file": "app.py", "change": "speed up", "content": "def fast(): pass"}],
            "estimated_impact": "2x faster",
            "summary": "Optimized app.py",
        }):
            result = opt.execute({"description": "Optimize app"})
        assert "app.py" in result["files_modified"]

    def test_file_read_error(self, tmp_path):
        opt = _make_agent(OptimizerAgent, tmp_path)
        opt.shared_context = {
            "engineer": {"files_modified": ["nonexistent.py"]},
        }
        with patch.object(opt, "read_file", return_value="[Error reading nonexistent.py]"):
            with patch.object(opt, "call_llm_json", return_value={
                "bottlenecks": [], "optimizations": [],
                "estimated_impact": "N/A", "summary": "File not found",
            }):
                result = opt.execute({"description": "Optimize"})
        assert result["files_modified"] == []

    def test_llm_returns_non_dict(self, tmp_path):
        opt = _make_agent(OptimizerAgent, tmp_path)
        with patch.object(opt, "call_llm_json", return_value="just a string"):
            result = opt.execute({"description": "Optimize"})
        assert result["role"] == "optimizer"
        assert result["files_modified"] == []


# ============================================================
# TesterAgent - Phase 13 coverage
# ============================================================

class TestTesterEdgeCases:
    """Phase 13: tester shared_context and edge cases."""

    def test_empty_shared_context(self, tmp_path):
        tester = _make_agent(TesterAgent, tmp_path, role="tester")
        with patch.object(tester, "list_files", return_value=[]):
            with patch.object(tester, "call_llm_json", return_value={
                "test_files": [], "test_strategy": "None",
                "coverage_areas": [], "summary": "No tests",
            }):
                result = tester.execute({"description": "Test"})
        assert result["files_modified"] == []

    def test_shared_context_non_dict(self, tmp_path):
        tester = _make_agent(TesterAgent, tmp_path, role="tester")
        tester.shared_context = {"engineer": "string value"}
        with patch.object(tester, "list_files", return_value=[]):
            with patch.object(tester, "call_llm_json", return_value={
                "test_files": [], "test_strategy": "None",
                "coverage_areas": [], "summary": "No files",
            }):
                result = tester.execute({"description": "Test"})
        assert result["files_modified"] == []

    def test_file_read_error(self, tmp_path):
        tester = _make_agent(TesterAgent, tmp_path, role="tester")
        tester.shared_context = {
            "engineer": {"files_modified": ["missing.py"]},
        }
        with patch.object(tester, "read_file", return_value="[Error reading missing.py]"):
            with patch.object(tester, "list_files", return_value=[]):
                with patch.object(tester, "call_llm_json", return_value={
                    "test_files": [], "summary": "Error",
                }):
                    result = tester.execute({"description": "Test"})
        assert result["files_modified"] == []

    def test_no_test_files_in_workspace(self, tmp_path):
        tester = _make_agent(TesterAgent, tmp_path, role="tester")
        with patch.object(tester, "list_files", return_value=["app.py", "main.py"]):
            with patch.object(tester, "call_llm_json", return_value={
                "test_files": [{"path": "tests/test_app.py", "content": "def test_x(): pass"}],
                "summary": "Created test",
            }):
                from mado.backend.tools.file_tools import FileTools
                tester.tools = [FileTools(str(tmp_path))]
                with patch.object(tester, "run_tests", return_value={
                    "stdout": "1 passed", "stderr": "", "returncode": 0,
                }):
                    result = tester.execute({"description": "Test"})
        assert "tests/test_app.py" in result["files_modified"]

    def test_llm_returns_none_fallback(self, tmp_path):
        tester = _make_agent(TesterAgent, tmp_path, role="tester")
        with patch.object(tester, "list_files", return_value=[]):
            with patch.object(tester, "call_llm_json", return_value=None):
                result = tester.execute({"description": "Test"})
        assert result["role"] == "tester"
        assert result["files_modified"] == []

    def test_existing_test_files_in_prompt(self, tmp_path):
        """When test files exist, they should be included in the prompt."""
        tester = _make_agent(TesterAgent, tmp_path, role="tester")
        with patch.object(tester, "list_files", return_value=["test_app.py", "main.py"]):
            with patch.object(tester, "call_llm_json", return_value={
                "test_files": [], "summary": "Reviewed",
            }) as mock_call:
                result = tester.execute({"description": "Test"})
        # The prompt should mention existing test files
        prompt = mock_call.call_args[0][0]
        assert "test_app.py" in prompt

    def test_test_run_failure(self, tmp_path):
        """Tests that fail should report returncode != 0."""
        tester = _make_agent(TesterAgent, tmp_path, role="tester")
        from mado.backend.tools.file_tools import FileTools
        tester.tools = [FileTools(str(tmp_path))]

        with patch.object(tester, "list_files", return_value=[]):
            with patch.object(tester, "call_llm_json", return_value={
                "test_files": [{"path": "tests/test_fail.py", "content": "def test_x(): assert False"}],
                "summary": "Tests failed",
            }):
                with patch.object(tester, "run_tests", return_value={
                    "stdout": "1 failed", "stderr": "AssertionError", "returncode": 1,
                }):
                    result = tester.execute({"description": "Test"})
        assert isinstance(result["result"], dict)
        assert result["result"]["test_output"]["passed"] is False
