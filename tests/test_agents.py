"""Tests for individual agent implementations (CTO, Manager, Engineer, Reviewer, etc.)

All agents call LLMs via call_llm / call_llm_json, so we mock those
to test the logic around prompt construction, JSON parsing, fallbacks,
file operations, and result formatting.
"""

import json
import pytest
from unittest.mock import patch, MagicMock, PropertyMock

from mado.backend.agents.cto import CTOAgent, AVAILABLE_ROLES, DEFAULT_TEAM
from mado.backend.agents.manager import ManagerAgent
from mado.backend.agents.engineer import EngineerAgent
from mado.backend.agents.reviewer import ReviewerAgent
from mado.backend.agents.tester import TesterAgent
from mado.backend.agents.researcher import ResearcherAgent
from mado.backend.agents.optimizer import OptimizerAgent
from mado.backend.agents.documenter import DocumenterAgent
from mado.backend.agents.marketer import MarketerAgent


def make_agent(cls, tmp_path, **kwargs):
    agent = cls(
        role=kwargs.get("role", cls.__name__.replace("Agent", "").lower()),
        model={"name": "test-model", "provider": "ollama"},
        workspace_path=str(tmp_path),
    )
    return agent


# ============================================================
# CTO Agent
# ============================================================

class TestCTOAnalyzeAndPlan:
    def test_parse_valid_roles(self, tmp_path):
        cto = make_agent(CTOAgent, tmp_path, role="cto")
        with patch.object(cto, "call_llm", return_value='```json\n["engineer", "tester", "reviewer"]\n```'):
            roles = cto.analyze_and_plan("Build a REST API")
        assert "engineer" in roles
        assert "tester" in roles
        assert "reviewer" in roles

    def test_always_includes_engineer(self, tmp_path):
        cto = make_agent(CTOAgent, tmp_path, role="cto")
        with patch.object(cto, "call_llm", return_value='```json\n["tester"]\n```'):
            roles = cto.analyze_and_plan("Test something")
        assert "engineer" in roles

    def test_fallback_to_default_team(self, tmp_path):
        cto = make_agent(CTOAgent, tmp_path, role="cto")
        with patch.object(cto, "call_llm", return_value="gibberish no json here"):
            roles = cto.analyze_and_plan("Do something")
        assert set(roles) == set(DEFAULT_TEAM)

    def test_filters_invalid_roles(self, tmp_path):
        cto = make_agent(CTOAgent, tmp_path, role="cto")
        with patch.object(cto, "call_llm", return_value='["engineer", "hacker", "spy"]'):
            roles = cto.analyze_and_plan("Test")
        assert "engineer" in roles
        assert "hacker" not in roles
        assert "spy" not in roles


class TestCTOPlan:
    def test_parse_structured_plan(self, tmp_path):
        cto = make_agent(CTOAgent, tmp_path, role="cto")
        llm_response = json.dumps({
            "plan_summary": "Build API",
            "architecture_notes": "Use FastAPI",
            "phases": [{"phase": "Setup", "tasks": [
                {"task_id": "t1", "description": "Init project",
                 "assigned_to": "engineer", "depends_on": [], "priority": "high"}
            ]}]
        })
        with patch.object(cto, "call_llm", return_value=f"```json\n{llm_response}\n```"):
            plan = cto.plan("Build API", iteration=1)
        assert plan["plan_summary"] == "Build API"
        assert plan["iteration"] == 1
        assert len(plan["phases"]) == 1

    def test_fallback_plan_on_parse_failure(self, tmp_path):
        cto = make_agent(CTOAgent, tmp_path, role="cto")
        with patch.object(cto, "call_llm", return_value="Not valid JSON at all"):
            plan = cto.plan("Build something", iteration=2)
        assert plan["iteration"] == 2
        assert len(plan["phases"]) == 1
        tasks = plan["phases"][0]["tasks"]
        assert any(t["assigned_to"] == "engineer" for t in tasks)


class TestCTOExecute:
    def test_execute_with_json(self, tmp_path):
        cto = make_agent(CTOAgent, tmp_path, role="cto")
        result_json = {"decisions": ["Use PostgreSQL"], "recommendations": ["Add caching"], "risks": []}
        with patch.object(cto, "call_llm_json", return_value=result_json):
            result = cto.execute({"description": "Choose database"})
        assert result["role"] == "cto"
        assert result["result"]["decisions"] == ["Use PostgreSQL"]

    def test_execute_uses_fallback(self, tmp_path):
        cto = make_agent(CTOAgent, tmp_path, role="cto")
        with patch.object(cto, "call_llm_json", return_value={"decisions": ["Do it"], "recommendations": [], "risks": []}):
            result = cto.execute({"description": "Decide architecture"})
        assert not result["error"]


# ============================================================
# Manager Agent
# ============================================================

class TestManagerDecompose:
    def test_extract_from_phases(self, tmp_path):
        mgr = make_agent(ManagerAgent, tmp_path, role="manager")
        plan = {
            "phases": [{
                "phase": "Setup",
                "tasks": [
                    {"task_id": "t1", "description": "Init", "assigned_to": "engineer",
                     "depends_on": [], "priority": "high"},
                    {"task_id": "t2", "description": "Test", "assigned_to": "tester",
                     "depends_on": ["t1"], "priority": "medium"},
                ]
            }]
        }
        tasks = mgr.decompose(plan)
        assert len(tasks) == 2
        assert tasks[0]["task_id"] == "t1"
        assert tasks[1]["depends_on"] == ["t1"]

    def test_auto_assign_missing_fields(self, tmp_path):
        mgr = make_agent(ManagerAgent, tmp_path, role="manager")
        plan = {"phases": [{"phase": "Work", "tasks": [
            {"description": "Do something"}  # Missing task_id, assigned_to, etc.
        ]}]}
        tasks = mgr.decompose(plan)
        assert len(tasks) == 1
        assert tasks[0]["task_id"] == "task_0"
        assert tasks[0]["assigned_to"] == "engineer"

    def test_llm_decompose_fallback(self, tmp_path):
        mgr = make_agent(ManagerAgent, tmp_path, role="manager")
        with patch.object(mgr, "call_llm_json", return_value="invalid"):
            tasks = mgr.decompose({"plan_summary": "Build API"})
        assert len(tasks) == 1
        assert tasks[0]["assigned_to"] == "engineer"

    def test_llm_decompose_valid(self, tmp_path):
        mgr = make_agent(ManagerAgent, tmp_path, role="manager")
        llm_tasks = [
            {"task_id": "a", "description": "Research", "assigned_to": "researcher", "depends_on": []},
            {"task_id": "b", "description": "Implement", "assigned_to": "engineer", "depends_on": ["a"]},
        ]
        with patch.object(mgr, "call_llm_json", return_value=llm_tasks):
            tasks = mgr.decompose({"plan_summary": "Build feature"})
        assert len(tasks) == 2
        assert tasks[1]["depends_on"] == ["a"]


class TestManagerValidateTasks:
    def test_dedup_task_ids(self, tmp_path):
        mgr = make_agent(ManagerAgent, tmp_path, role="manager")
        tasks = [
            {"task_id": "t1", "description": "A"},
            {"task_id": "t1", "description": "B"},  # duplicate
        ]
        valid = mgr._validate_tasks(tasks)
        assert len(valid) == 2
        ids = [t["task_id"] for t in valid]
        assert len(set(ids)) == 2  # All unique

    def test_remove_invalid_deps(self, tmp_path):
        mgr = make_agent(ManagerAgent, tmp_path, role="manager")
        tasks = [
            {"task_id": "t1", "description": "A", "depends_on": ["nonexistent"]},
        ]
        valid = mgr._validate_tasks(tasks)
        assert valid[0]["depends_on"] == []

    def test_skips_non_dict(self, tmp_path):
        mgr = make_agent(ManagerAgent, tmp_path, role="manager")
        valid = mgr._validate_tasks(["not a dict", 42, None])
        assert len(valid) == 0


# ============================================================
# Engineer Agent
# ============================================================

class TestEngineerExecute:
    def test_writes_files(self, tmp_path):
        eng = make_agent(EngineerAgent, tmp_path, role="engineer")
        # Attach file tools
        from mado.backend.tools.file_tools import FileTools
        eng.tools = [FileTools(str(tmp_path))]

        llm_result = {
            "approach": "Create main module",
            "files": [{"path": "app.py", "action": "create", "content": "print('hello')"}],
            "summary": "Created app.py",
        }
        with patch.object(eng, "call_llm_json", return_value=llm_result):
            result = eng.execute({"description": "Create main app"})
        assert "app.py" in result["files_modified"]
        assert (tmp_path / "app.py").exists()

    def test_fallback_on_invalid_json(self, tmp_path):
        eng = make_agent(EngineerAgent, tmp_path, role="engineer")
        with patch.object(eng, "call_llm_json", return_value="raw text"):
            result = eng.execute({"description": "Build something"})
        assert result["role"] == "engineer"
        assert result["files_modified"] == []


# ============================================================
# Reviewer Agent
# ============================================================

class TestReviewerReview:
    def test_approved_review(self, tmp_path):
        rev = make_agent(ReviewerAgent, tmp_path, role="reviewer")
        review_result = {"approved": True, "score": 9, "issues": [], "feedback": "Great", "improvements": []}
        with patch.object(rev, "call_llm_json", return_value=review_result):
            result = rev.review([{"role": "engineer", "summary": "Built API", "files_modified": []}])
        assert result["approved"] is True
        assert result["score"] == 9

    def test_rejected_on_critical_issues(self, tmp_path):
        rev = make_agent(ReviewerAgent, tmp_path, role="reviewer")
        review_result = {
            "approved": True, "score": 6,
            "issues": [{"severity": "critical", "description": "SQL injection"}],
            "feedback": "Major bug", "improvements": ["Fix SQL"]
        }
        with patch.object(rev, "call_llm_json", return_value=review_result):
            result = rev.review([{"role": "engineer", "summary": "Built API"}])
        assert result["approved"] is False  # Auto-rejected due to critical

    def test_string_approved_parsed(self, tmp_path):
        rev = make_agent(ReviewerAgent, tmp_path, role="reviewer")
        review_result = {"approved": "true", "score": 8, "issues": [], "feedback": "OK", "improvements": []}
        with patch.object(rev, "call_llm_json", return_value=review_result):
            result = rev.review([])
        assert result["approved"] is True

    def test_fallback_on_parse_failure(self, tmp_path):
        rev = make_agent(ReviewerAgent, tmp_path, role="reviewer")
        with patch.object(rev, "call_llm_json", return_value=None):
            result = rev.review([])
        assert result["approved"] is False
        assert result["score"] == 5

    def test_includes_project_rules(self, tmp_path):
        rev = make_agent(ReviewerAgent, tmp_path, role="reviewer")
        rev.project_config = {"rules_must": "Always test", "rules_forbidden": "No eval()"}
        with patch.object(rev, "call_llm_json", return_value={"approved": True, "score": 8, "issues": [], "feedback": "OK", "improvements": []}) as mock_call:
            rev.review([{"role": "engineer", "summary": "Done"}])
        # Verify rules are in prompt
        prompt = mock_call.call_args[0][0]
        assert "Always test" in prompt
        assert "No eval()" in prompt


# ============================================================
# Tester Agent
# ============================================================

class TestTesterExecute:
    def test_writes_and_runs_tests(self, tmp_path):
        tester = make_agent(TesterAgent, tmp_path, role="tester")
        from mado.backend.tools.file_tools import FileTools
        tester.tools = [FileTools(str(tmp_path))]

        llm_result = {
            "test_files": [{"path": "tests/test_app.py", "content": "def test_pass(): assert True"}],
            "test_strategy": "Unit tests",
            "coverage_areas": ["main"],
            "summary": "Created unit tests",
        }
        with patch.object(tester, "call_llm_json", return_value=llm_result):
            with patch.object(tester, "run_tests", return_value={"stdout": "1 passed", "stderr": "", "returncode": 0}):
                result = tester.execute({"description": "Test the app"})
        assert "tests/test_app.py" in result["files_modified"]
        assert result["result"]["test_output"]["passed"] is True

    def test_fallback_no_test_files(self, tmp_path):
        tester = make_agent(TesterAgent, tmp_path, role="tester")
        with patch.object(tester, "call_llm_json", return_value="invalid"):
            result = tester.execute({"description": "Test something"})
        assert result["files_modified"] == []


# ============================================================
# Researcher Agent
# ============================================================

class TestResearcherExecute:
    def test_uses_web_search(self, tmp_path):
        researcher = make_agent(ResearcherAgent, tmp_path, role="researcher")
        web_results = [{"title": "FastAPI docs", "url": "https://fastapi.tiangolo.com", "content": "Modern API framework"}]
        findings = {"findings": ["FastAPI is good"], "recommendations": ["Use it"], "references": [], "summary": "FastAPI research"}

        with patch.object(researcher, "search_web", return_value=web_results):
            with patch.object(researcher, "call_llm_json", return_value=findings):
                result = researcher.execute({"description": "Research FastAPI"})
        assert result["result"]["findings"] == ["FastAPI is good"]

    def test_fallback_on_parse_failure(self, tmp_path):
        researcher = make_agent(ResearcherAgent, tmp_path, role="researcher")
        with patch.object(researcher, "search_web", return_value=[{"error": "unavailable"}]):
            with patch.object(researcher, "call_llm_json", return_value={"findings": ["Research"], "recommendations": [], "references": [], "summary": "Done"}):
                result = researcher.execute({"description": "Research topic"})
        assert not result["error"]


# ============================================================
# Optimizer, Documenter, Marketer
# ============================================================

class TestOptimizerExecute:
    def test_execute(self, tmp_path):
        opt = make_agent(OptimizerAgent, tmp_path, role="optimizer")
        llm_result = {
            "bottlenecks": [],
            "optimizations": [],
            "estimated_impact": "Minor improvement",
            "summary": "Optimized DB queries",
        }
        with patch.object(opt, "call_llm_json", return_value=llm_result):
            result = opt.execute({"description": "Optimize database"})
        assert result["role"] == "optimizer"
        assert not result["error"]

    def test_execute_writes_files(self, tmp_path):
        opt = make_agent(OptimizerAgent, tmp_path, role="optimizer")
        from mado.backend.tools.file_tools import FileTools
        opt.tools = [FileTools(str(tmp_path))]
        llm_result = {
            "bottlenecks": [],
            "optimizations": [{"file": "app.py", "change": "cache", "content": "optimized code"}],
            "estimated_impact": "2x faster",
            "summary": "Applied caching",
        }
        with patch.object(opt, "call_llm_json", return_value=llm_result):
            result = opt.execute({"description": "Optimize"})
        assert "app.py" in result["files_modified"]


class TestDocumenterExecute:
    def test_execute(self, tmp_path):
        doc = make_agent(DocumenterAgent, tmp_path, role="documenter")
        from mado.backend.tools.file_tools import FileTools
        doc.tools = [FileTools(str(tmp_path))]

        llm_result = {
            "files": [{"path": "README.md", "content": "# Project\nDescription"}],
            "summary": "Created README",
        }
        with patch.object(doc, "call_llm_json", return_value=llm_result):
            result = doc.execute({"description": "Write docs"})
        assert result["role"] == "documenter"


class TestMarketerExecute:
    def test_execute(self, tmp_path):
        mkt = make_agent(MarketerAgent, tmp_path, role="marketer")
        with patch.object(mkt, "call_llm_json", return_value={"strategy": "Social media campaign", "summary": "Launch plan"}):
            result = mkt.execute({"description": "Create launch plan"})
        assert result["role"] == "marketer"
        assert not result["error"]
