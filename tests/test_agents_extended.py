"""Extended agent tests - coverage boost for documenter, marketer, reviewer execute."""

from unittest.mock import patch

from mado.backend.agents.documenter import DocumenterAgent
from mado.backend.agents.marketer import MarketerAgent
from mado.backend.agents.reviewer import ReviewerAgent


def make_agent(cls, tmp_path, **kwargs):
    agent = cls(
        role=kwargs.get("role", cls.__name__.replace("Agent", "").lower()),
        model={"name": "test-model", "provider": "ollama"},
        workspace_path=str(tmp_path),
    )
    return agent


class TestDocumenterExecuteExtended:
    def test_execute_writes_documents(self, tmp_path):
        doc = make_agent(DocumenterAgent, tmp_path, role="documenter")
        from mado.backend.tools.file_tools import FileTools
        doc.tools = [FileTools(str(tmp_path))]

        llm_result = {
            "documents": [
                {"path": "docs/README.md", "content": "# Project\nDescription"},
                {"path": "docs/API.md", "content": "# API\nEndpoints"},
            ],
            "summary": "Created documentation",
        }
        with patch.object(doc, "call_llm_json", return_value=llm_result):
            with patch.object(doc, "list_files", return_value=["app.py"]):
                with patch.object(doc, "read_file", return_value="def hello(): pass"):
                    result = doc.execute({"description": "Write docs"})
        assert "docs/README.md" in result["files_modified"]
        assert "docs/API.md" in result["files_modified"]

    def test_execute_empty_documents(self, tmp_path):
        doc = make_agent(DocumenterAgent, tmp_path, role="documenter")
        llm_result = {"documents": [], "summary": "Nothing to document"}
        with patch.object(doc, "call_llm_json", return_value=llm_result):
            with patch.object(doc, "list_files", return_value=[]):
                result = doc.execute({"description": "Write docs"})
        assert result["files_modified"] == []

    def test_execute_fallback(self, tmp_path):
        doc = make_agent(DocumenterAgent, tmp_path, role="documenter")
        with patch.object(doc, "call_llm_json", return_value="invalid"):
            with patch.object(doc, "list_files", return_value=[]):
                result = doc.execute({"description": "Write docs"})
        assert result["role"] == "documenter"

    def test_execute_skips_empty_docs(self, tmp_path):
        doc = make_agent(DocumenterAgent, tmp_path, role="documenter")
        from mado.backend.tools.file_tools import FileTools
        doc.tools = [FileTools(str(tmp_path))]
        llm_result = {
            "documents": [
                {"path": "", "content": "should be skipped"},
                {"path": "valid.md", "content": ""},  # empty content skipped
                {"path": "good.md", "content": "# Good"},
            ],
            "summary": "Partial docs",
        }
        with patch.object(doc, "call_llm_json", return_value=llm_result):
            with patch.object(doc, "list_files", return_value=[]):
                result = doc.execute({"description": "Write docs"})
        assert "good.md" in result["files_modified"]
        assert "" not in result["files_modified"]

    def test_execute_reads_code_context(self, tmp_path):
        """Documenter reads .py files for context."""
        (tmp_path / "main.py").write_text("def main(): pass\n", encoding="utf-8")
        doc = make_agent(DocumenterAgent, tmp_path, role="documenter")
        llm_result = {"documents": [], "summary": "Analyzed code"}
        with patch.object(doc, "call_llm_json", return_value=llm_result):
            result = doc.execute({"description": "Analyze project"})
        assert result["role"] == "documenter"


class TestMarketerExecuteExtended:
    def test_execute_with_web_results(self, tmp_path):
        mkt = make_agent(MarketerAgent, tmp_path, role="marketer")
        web_results = [
            {"title": "Trend Report", "content": "AI is growing fast"},
        ]
        llm_result = {
            "strategy": "Target AI developers",
            "content": [
                {"type": "blog", "title": "AI Growth", "body": "AI is transforming..."},
                {"type": "social", "title": "Tweet", "body": "Check out our new product!"},
            ],
            "target_audience": "Developers",
            "channels": ["Twitter", "Blog"],
            "summary": "Marketing plan created",
        }
        with patch.object(mkt, "search_web", return_value=web_results):
            with patch.object(mkt, "call_llm_json", return_value=llm_result):
                result = mkt.execute({"description": "Launch marketing"})
        assert result["role"] == "marketer"
        assert len(result["files_modified"]) == 2

    def test_execute_web_error(self, tmp_path):
        mkt = make_agent(MarketerAgent, tmp_path, role="marketer")
        web_results = [{"error": "Network unavailable"}]
        llm_result = {
            "strategy": "Offline approach",
            "content": [],
            "summary": "Plan without web",
        }
        with patch.object(mkt, "search_web", return_value=web_results):
            with patch.object(mkt, "call_llm_json", return_value=llm_result):
                result = mkt.execute({"description": "Market research"})
        assert result["role"] == "marketer"
        assert result["files_modified"] == []

    def test_execute_fallback(self, tmp_path):
        mkt = make_agent(MarketerAgent, tmp_path, role="marketer")
        with patch.object(mkt, "search_web", return_value=[]):
            with patch.object(mkt, "call_llm_json", return_value="invalid"):
                result = mkt.execute({"description": "Market"})
        assert result["role"] == "marketer"

    def test_execute_content_without_body(self, tmp_path):
        """Content items without body should not create files."""
        mkt = make_agent(MarketerAgent, tmp_path, role="marketer")
        llm_result = {
            "strategy": "Plan",
            "content": [{"type": "blog", "title": "No Body"}],
            "summary": "Plan",
        }
        with patch.object(mkt, "search_web", return_value=[]):
            with patch.object(mkt, "call_llm_json", return_value=llm_result):
                result = mkt.execute({"description": "Market"})
        assert result["files_modified"] == []


class TestReviewerExecuteExtended:
    def test_execute_with_shared_context(self, tmp_path):
        rev = make_agent(ReviewerAgent, tmp_path, role="reviewer")
        rev.shared_context = {
            "engineer": {"files_modified": ["app.py"], "result": "Built"},
        }
        (tmp_path / "app.py").write_text("def hello(): pass\n", encoding="utf-8")
        llm_result = {
            "issues": [{"severity": "warning", "description": "Missing docstring"}],
            "feedback": "Needs improvement",
            "quality_score": 7,
        }
        with patch.object(rev, "call_llm_json", return_value=llm_result):
            result = rev.execute({"description": "Review code"})
        assert result["role"] == "reviewer"

    def test_execute_no_shared_context(self, tmp_path):
        rev = make_agent(ReviewerAgent, tmp_path, role="reviewer")
        llm_result = {
            "issues": [],
            "feedback": "Good",
            "quality_score": 9,
        }
        with patch.object(rev, "call_llm_json", return_value=llm_result):
            result = rev.execute({"description": "Review code"})
        assert result["role"] == "reviewer"

    def test_review_with_file_contents(self, tmp_path):
        """Reviewer reads modified files for review."""
        rev = make_agent(ReviewerAgent, tmp_path, role="reviewer")
        (tmp_path / "main.py").write_text("import os\n\ndef main(): pass\n", encoding="utf-8")
        review_result = {
            "approved": True, "score": 8,
            "issues": [], "feedback": "Clean",
            "improvements": ["Add tests"],
        }
        with patch.object(rev, "call_llm_json", return_value=review_result):
            result = rev.review([{
                "role": "engineer",
                "summary": "Built feature",
                "files_modified": ["main.py"],
            }])
        assert result["approved"] is True
        assert result["improvements"] == ["Add tests"]

    def test_review_with_rules(self, tmp_path):
        rev = make_agent(ReviewerAgent, tmp_path, role="reviewer")
        rev.project_config = {
            "rules_must": "Use type hints",
            "rules_forbidden": "No global state",
        }
        review_result = {
            "approved": False, "score": 4,
            "issues": [{"severity": "warning", "description": "Missing type hints"}],
            "feedback": "Rules violated",
        }
        with patch.object(rev, "call_llm_json", return_value=review_result) as mock_call:
            result = rev.review([{"role": "engineer", "summary": "Done"}])
        prompt = mock_call.call_args[0][0]
        assert "Use type hints" in prompt
        assert "No global state" in prompt
        assert result["approved"] is False
