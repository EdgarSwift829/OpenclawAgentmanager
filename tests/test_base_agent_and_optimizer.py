"""Tests for BaseAgent, TokenOptimizer, and ProjectMemory."""

from unittest.mock import MagicMock

import pytest

from mado.backend.agents.base_agent import DEFAULT_AGENT_PROFILES, BaseAgent
from mado.backend.memory.project_memory import ProjectMemory
from mado.backend.token_optimizer import TokenOptimizer

# ============================================================
# BaseAgent (concrete subclass for testing)
# ============================================================

class StubAgent(BaseAgent):
    """Minimal concrete agent for testing BaseAgent methods."""
    def execute(self, task: dict) -> dict:
        return self.make_result("stub result", summary="stub")


@pytest.fixture
def agent(tmp_path):
    return StubAgent(
        role="engineer",
        model={"name": "test-model", "provider": "ollama"},
        workspace_path=str(tmp_path),
    )


class TestBaseAgentToolDispatch:
    def test_get_tool_by_class_name(self, agent):
        mock_tool = MagicMock()
        type(mock_tool).__name__ = "FileTools"
        agent.tools = [mock_tool]
        assert agent.get_tool("FileTools") is mock_tool
        assert agent.get_tool("ExecTools") is None

    def test_file_tools_property(self, agent):
        mock_ft = MagicMock()
        type(mock_ft).__name__ = "FileTools"
        agent.tools = [mock_ft]
        assert agent.file_tools is mock_ft

    def test_read_file_no_tools(self, agent):
        result = agent.read_file("test.txt")
        assert "[Error]" in result

    def test_write_file_no_tools(self, agent):
        result = agent.write_file("test.txt", "content")
        assert "[Error]" in result

    def test_list_files_no_tools(self, agent):
        assert agent.list_files() == []

    def test_search_code_no_tools(self, agent):
        assert agent.search_code("query") == []

    def test_run_command_no_tools(self, agent):
        result = agent.run_command("script.py")
        assert "error" in result

    def test_run_tests_no_tools(self, agent):
        result = agent.run_tests()
        assert "error" in result

    def test_search_web_no_tools(self, agent):
        result = agent.search_web("query")
        assert result[0].get("error")


class TestBaseAgentExtractJSON:
    def test_extract_json_block(self):
        text = 'Some text\n```json\n{"key": "value"}\n```\nMore text'
        result = BaseAgent.extract_json(text)
        assert result == {"key": "value"}

    def test_extract_json_raw_object(self):
        text = 'Result: {"score": 8, "approved": true}'
        result = BaseAgent.extract_json(text)
        assert result["score"] == 8

    def test_extract_json_raw_array(self):
        text = 'Items: ["a", "b", "c"]'
        result = BaseAgent.extract_json(text)
        assert result == ["a", "b", "c"]

    def test_extract_json_empty(self):
        assert BaseAgent.extract_json("") is None
        assert BaseAgent.extract_json("no json here") is None

    def test_extract_json_invalid(self):
        text = '```json\n{invalid json}\n```'
        assert BaseAgent.extract_json(text) is None


class TestExtractJsonBracketMatching:
    """Tests for the bracket-matching JSON extraction algorithm."""

    def test_nested_json_objects(self):
        text = 'Result: {"outer": {"inner": {"deep": 1}}, "key": "val"}'
        result = BaseAgent.extract_json(text)
        assert result == {"outer": {"inner": {"deep": 1}}, "key": "val"}

    def test_json_with_escaped_quotes(self):
        text = r'Output: {"message": "He said \"hello\"", "count": 3}'
        result = BaseAgent.extract_json(text)
        assert result["count"] == 3
        assert "hello" in result["message"]

    def test_json_with_braces_in_strings(self):
        text = '{"code": "if (x) { return {}; }", "valid": true}'
        result = BaseAgent.extract_json(text)
        assert result["valid"] is True
        assert "{" in result["code"]

    def test_nested_arrays(self):
        text = 'Data: [["a", "b"], [1, 2], [{"x": 1}]]'
        result = BaseAgent.extract_json(text)
        assert result == [["a", "b"], [1, 2], [{"x": 1}]]

    def test_mixed_text_before_and_after(self):
        text = 'Here is the plan:\n{"tasks": ["build", "test"]}\nEnd of response.'
        result = BaseAgent.extract_json(text)
        assert result == {"tasks": ["build", "test"]}

    def test_prefers_fenced_block_over_raw(self):
        text = '{"wrong": true}\n```json\n{"correct": true}\n```'
        result = BaseAgent.extract_json(text)
        assert result == {"correct": True}

    def test_whole_text_fallback(self):
        text = '{"simple": true}'
        result = BaseAgent.extract_json(text)
        assert result == {"simple": True}

    def test_invalid_json_returns_none(self):
        text = '{key: no quotes}'
        result = BaseAgent.extract_json(text)
        assert result is None


class TestGetToolByClass:
    """Tests for class-reference based tool lookup with caching."""

    def test_get_tool_by_class_reference(self, agent):
        mock_tool = MagicMock()
        type(mock_tool).__name__ = "FileTools"
        agent.tools = [mock_tool]
        from mado.backend.tools.file_tools import FileTools
        assert agent.get_tool(FileTools) is mock_tool

    def test_get_tool_cache_works(self, agent):
        mock_tool = MagicMock()
        type(mock_tool).__name__ = "FileTools"
        agent.tools = [mock_tool]
        # First call populates cache
        result1 = agent.get_tool("FileTools")
        # Second call uses cache
        result2 = agent.get_tool("FileTools")
        assert result1 is result2 is mock_tool

    def test_get_tool_cache_none_for_missing(self, agent):
        agent.tools = []
        result = agent.get_tool("NonExistent")
        assert result is None
        # Cached None
        assert "NonExistent" in agent._tool_cache
        assert agent._tool_cache["NonExistent"] is None

    def test_tool_properties_use_class_reference(self, agent):
        mock_ft = MagicMock()
        type(mock_ft).__name__ = "FileTools"
        mock_et = MagicMock()
        type(mock_et).__name__ = "ExecTools"
        agent.tools = [mock_ft, mock_et]
        assert agent.file_tools is mock_ft
        assert agent.exec_tools is mock_et


class TestBaseAgentExtractList:
    def test_extract_list_json(self):
        text = '["engineer", "tester"]'
        result = BaseAgent.extract_list_from_text(text)
        assert result == ["engineer", "tester"]

    def test_extract_list_with_valid_items(self):
        text = "We need an engineer and a tester for this"
        result = BaseAgent.extract_list_from_text(
            text, valid_items=["engineer", "tester", "reviewer"]
        )
        assert "engineer" in result
        assert "tester" in result
        assert "reviewer" not in result

    def test_extract_list_empty(self):
        assert BaseAgent.extract_list_from_text("") == []
        assert BaseAgent.extract_list_from_text(None) == []


class TestBaseAgentSystemPrompt:
    def test_build_system_prompt_basic(self, agent):
        prompt = agent.build_system_prompt()
        # Should include role identity
        assert "engineer" in prompt.lower() or "エンジニア" in prompt

    def test_build_system_prompt_includes_preset(self, agent):
        prompt = agent.build_system_prompt()
        assert "Preset" in prompt or "Personality" in prompt

    def test_build_system_prompt_with_rules(self, agent):
        agent.project_config = {
            "rules_must": "Always write tests",
            "rules_forbidden": "Never use eval()",
        }
        prompt = agent.build_system_prompt()
        assert "Always write tests" in prompt
        assert "Never use eval()" in prompt

    def test_build_system_prompt_with_goal(self, agent):
        agent.project_config = {"goal": "Build a REST API"}
        prompt = agent.build_system_prompt()
        assert "Build a REST API" in prompt

    def test_build_system_prompt_with_extra(self, agent):
        prompt = agent.build_system_prompt(extra_instructions="Focus on security")
        assert "Focus on security" in prompt


class TestBaseAgentContextBuilders:
    def test_build_iteration_context_empty(self, agent):
        assert agent.build_iteration_context() == ""

    def test_build_iteration_context_with_data(self, agent):
        agent.iteration_context = [
            {"iteration": 1, "summary": "Set up project structure"},
            {"iteration": 2, "summary": "Implemented API endpoints"},
        ]
        result = agent.build_iteration_context()
        assert "Iteration 1" in result
        assert "Set up project structure" in result

    def test_build_iteration_context_max_3(self, agent):
        agent.iteration_context = [
            {"iteration": i, "summary": f"iter {i}"} for i in range(10)
        ]
        result = agent.build_iteration_context()
        # Should only include last 3
        assert "Iteration 7" in result
        assert "Iteration 9" in result
        assert "Iteration 1" not in result

    def test_build_shared_context(self, agent):
        agent.shared_context = {
            "cto": "Architecture plan...",
            "engineer": "My own output (should be excluded)",
        }
        result = agent.build_shared_context()
        assert "cto" in result
        # Should exclude own role
        assert "My own output" not in result


class TestBaseAgentMakeResult:
    def test_make_result(self, agent):
        result = agent.make_result(
            "done", files_modified=["app.py"], summary="Completed task"
        )
        assert result["role"] == "engineer"
        assert result["result"] == "done"
        assert result["summary"] == "Completed task"
        assert result["files_modified"] == ["app.py"]
        assert result["error"] is False

    def test_make_result_defaults(self, agent):
        result = agent.make_result("done")
        assert result["files_modified"] == []
        assert result["error"] is False


class TestDefaultAgentProfiles:
    def test_all_roles_have_profiles(self):
        expected_roles = {
            "cto", "manager", "researcher", "engineer", "reviewer",
            "tester", "optimizer", "documenter", "marketer",
        }
        assert set(DEFAULT_AGENT_PROFILES.keys()) == expected_roles

    def test_profiles_have_required_fields(self):
        for role, profile in DEFAULT_AGENT_PROFILES.items():
            assert "title" in profile, f"{role} missing title"
            assert "personality" in profile, f"{role} missing personality"
            assert len(profile["personality"]) > 50, f"{role} personality too short"


# ============================================================
# TokenOptimizer
# ============================================================

class TestTokenOptimizer:
    def test_build_context_basic(self):
        opt = TokenOptimizer()
        result = opt.build_context(
            system_prompt="You are helpful",
            task="Write a function",
        )
        assert "You are helpful" in result
        assert "Write a function" in result

    def test_build_context_with_memory(self):
        opt = TokenOptimizer()
        result = opt.build_context(
            system_prompt="SP",
            task="Task",
            project_memory="Important: use Python 3.11",
        )
        assert "Important: use Python 3.11" in result

    def test_build_context_with_files(self):
        opt = TokenOptimizer()
        result = opt.build_context(
            system_prompt="SP",
            task="Task",
            retrieved_files=[{"file": "app.py", "content": "def main(): pass"}],
        )
        assert "app.py" in result
        assert "def main(): pass" in result

    def test_build_context_with_summaries(self):
        opt = TokenOptimizer()
        result = opt.build_context(
            system_prompt="SP",
            task="Task",
            iteration_summaries=[
                {"iteration": 1, "summary": "Created structure"},
            ],
        )
        assert "Created structure" in result

    def test_estimate_tokens(self):
        opt = TokenOptimizer()
        tokens = opt._estimate_tokens("Hello world")
        assert tokens > 0
        # ~11 chars / 3 ≈ 3
        assert tokens < 10

    def test_trim_to_budget(self):
        opt = TokenOptimizer()
        long_text = "x" * 10000
        trimmed = opt._trim_to_budget(long_text, 100)
        assert len(trimmed) < len(long_text)
        assert "trimmed" in trimmed

    def test_trim_short_text_unchanged(self):
        opt = TokenOptimizer()
        short = "short text"
        assert opt._trim_to_budget(short, 1000) == short

    def test_budget_limits_output(self):
        opt = TokenOptimizer(max_tokens=100)
        result = opt.build_context(
            system_prompt="SP",
            task="Task",
            project_memory="x" * 50000,
        )
        # Should not include the full 50k memory
        assert len(result) < 50000


# ============================================================
# ProjectMemory
# ============================================================

class TestProjectMemory:
    def test_load_empty(self, tmp_path):
        pm = ProjectMemory(str(tmp_path))
        assert pm.load() == ""

    def test_save_and_load(self, tmp_path):
        pm = ProjectMemory(str(tmp_path))
        pm.save("## Architecture\nMicroservices approach")
        assert "Microservices" in pm.load()

    def test_get_context_sections(self, tmp_path):
        pm = ProjectMemory(str(tmp_path))
        pm.save(
            "## Architecture\nMicroservices\n\n## Stack\nPython + FastAPI"
        )
        ctx = pm.get_context()
        assert "Architecture" in ctx
        assert "Microservices" in ctx["Architecture"]
        assert "Stack" in ctx
        assert "Python + FastAPI" in ctx["Stack"]

    def test_get_context_empty(self, tmp_path):
        pm = ProjectMemory(str(tmp_path))
        assert pm.get_context() == {}

    def test_get_context_no_sections(self, tmp_path):
        pm = ProjectMemory(str(tmp_path))
        pm.save("Just plain text without headers")
        assert pm.get_context() == {}
