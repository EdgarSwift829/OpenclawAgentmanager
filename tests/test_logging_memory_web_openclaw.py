"""Tests for MADOLogger, MemoryTools, WebTools, and OpenClawIntegration."""

import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from mado.backend.logging_system import MADOLogger
from mado.backend.tools.memory_tools import MemoryTools
from mado.backend.tools.web_tools import WebTools
from mado.backend.integrations.openclaw import OpenClawIntegration


# ============================================================
# MADOLogger
# ============================================================

class TestMADOLogger:
    def test_log_agent_message(self, tmp_path):
        logger = MADOLogger("test-proj", log_dir=str(tmp_path))
        logger.log_agent_message("engineer", "Writing code...")
        logs = logger.get_logs()
        assert len(logs) == 1
        assert logs[0]["type"] == "agent_message"
        assert logs[0]["role"] == "engineer"
        assert "timestamp" in logs[0]

    def test_log_tool_call(self, tmp_path):
        logger = MADOLogger("test-proj", log_dir=str(tmp_path))
        logger.log_tool_call("engineer", "write_file", {"path": "app.py"}, "ok")
        logs = logger.get_logs(log_type="tool_call")
        assert len(logs) == 1
        assert logs[0]["tool"] == "write_file"

    def test_log_error(self, tmp_path):
        logger = MADOLogger("test-proj", log_dir=str(tmp_path))
        logger.log_error("reviewer", "Parse error")
        logs = logger.get_logs(log_type="error")
        assert len(logs) == 1
        assert logs[0]["error"] == "Parse error"

    def test_log_iteration_summary(self, tmp_path):
        logger = MADOLogger("test-proj", log_dir=str(tmp_path))
        logger.log_iteration_summary(1, "Completed setup phase")
        logs = logger.get_logs(log_type="iteration_summary")
        assert len(logs) == 1
        assert logs[0]["iteration"] == 1

    def test_get_logs_empty(self, tmp_path):
        logger = MADOLogger("test-proj", log_dir=str(tmp_path))
        assert logger.get_logs() == []

    def test_get_logs_with_limit(self, tmp_path):
        logger = MADOLogger("test-proj", log_dir=str(tmp_path))
        for i in range(10):
            logger.log_agent_message("agent", f"msg {i}")
        logs = logger.get_logs(limit=3)
        assert len(logs) == 3

    def test_get_logs_filter_by_type(self, tmp_path):
        logger = MADOLogger("test-proj", log_dir=str(tmp_path))
        logger.log_agent_message("eng", "msg")
        logger.log_error("eng", "err")
        logger.log_tool_call("eng", "tool", {})
        assert len(logger.get_logs(log_type="error")) == 1
        assert len(logger.get_logs(log_type="agent_message")) == 1

    def test_sanitizes_project_id(self, tmp_path):
        logger = MADOLogger("../evil", log_dir=str(tmp_path))
        assert ".." not in logger.project_id

    def test_structured_log_jsonl_format(self, tmp_path):
        logger = MADOLogger("test-proj", log_dir=str(tmp_path))
        logger.log_agent_message("cto", "Planning")
        logger.log_error("cto", "Something broke")
        # Each line should be valid JSON
        with open(logger.structured_log, encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 2
        for line in lines:
            parsed = json.loads(line)
            assert "timestamp" in parsed
            assert "project_id" in parsed


# ============================================================
# MemoryTools
# ============================================================

class TestMemoryTools:
    def test_load_empty(self, tmp_path):
        mt = MemoryTools(str(tmp_path))
        assert mt.load_project_memory() == ""

    def test_update_new_section(self, tmp_path):
        mt = MemoryTools(str(tmp_path))
        result = mt.update_project_memory("Architecture", "Microservices pattern")
        assert "Updated" in result
        content = mt.load_project_memory()
        assert "## Architecture" in content
        assert "Microservices pattern" in content

    def test_update_existing_section(self, tmp_path):
        mt = MemoryTools(str(tmp_path))
        mt.update_project_memory("Stack", "Python")
        mt.update_project_memory("Stack", "Python + FastAPI")
        content = mt.load_project_memory()
        assert "Python + FastAPI" in content
        # Should not have duplicate headers
        assert content.count("## Stack") == 1

    def test_multiple_sections(self, tmp_path):
        mt = MemoryTools(str(tmp_path))
        mt.update_project_memory("Architecture", "Microservices")
        mt.update_project_memory("Stack", "Python + FastAPI")
        content = mt.load_project_memory()
        assert "## Architecture" in content
        assert "## Stack" in content

    def test_save_summary(self, tmp_path):
        mt = MemoryTools(str(tmp_path))
        result = mt.save_summary(1, "Setup complete")
        assert "Updated" in result
        content = mt.load_project_memory()
        assert "Iteration 1 Summary" in content
        assert "Setup complete" in content

    def test_save_multiple_summaries(self, tmp_path):
        mt = MemoryTools(str(tmp_path))
        mt.save_summary(1, "Phase 1 done")
        mt.save_summary(2, "Phase 2 done")
        content = mt.load_project_memory()
        assert "Iteration 1 Summary" in content
        assert "Iteration 2 Summary" in content


# ============================================================
# WebTools
# ============================================================

class TestWebTools:
    def test_extract_text_basic(self):
        wt = WebTools()
        html = "<html><body><p>Hello <b>World</b></p></body></html>"
        text = wt.extract_text(html)
        assert "Hello" in text
        assert "World" in text
        assert "<" not in text

    def test_extract_text_removes_scripts(self):
        wt = WebTools()
        html = "<p>Text</p><script>alert('xss')</script><p>More</p>"
        text = wt.extract_text(html)
        assert "alert" not in text
        assert "Text" in text
        assert "More" in text

    def test_extract_text_removes_styles(self):
        wt = WebTools()
        html = "<style>.x{color:red}</style><p>Visible</p>"
        text = wt.extract_text(html)
        assert "color" not in text
        assert "Visible" in text

    @patch("mado.backend.tools.web_tools.urllib.request.urlopen")
    def test_search_web_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "results": [
                {"title": "Result 1", "url": "http://a.com", "content": "Info 1"},
                {"title": "Result 2", "url": "http://b.com", "content": "Info 2"},
            ]
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        wt = WebTools()
        results = wt.search_web("test query", max_results=2)
        assert len(results) == 2
        assert results[0]["title"] == "Result 1"

    @patch("mado.backend.tools.web_tools.urllib.request.urlopen")
    def test_search_web_max_results(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "results": [{"title": f"R{i}", "url": f"http://{i}.com"} for i in range(10)]
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        wt = WebTools()
        results = wt.search_web("query", max_results=3)
        assert len(results) == 3

    def test_search_web_connection_error(self):
        wt = WebTools(searxng_url="http://localhost:99999")
        results = wt.search_web("test")
        assert len(results) == 1
        assert "error" in results[0]


# ============================================================
# OpenClawIntegration
# ============================================================

class TestOpenClawIntegration:
    @patch("mado.backend.integrations.openclaw.subprocess.run")
    def test_is_installed_via_command(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="1.0.0")
        oci = OpenClawIntegration()
        assert oci.is_installed() is True

    @patch("mado.backend.integrations.openclaw.shutil.which")
    @patch("mado.backend.integrations.openclaw.subprocess.run")
    def test_is_installed_not_found(self, mock_run, mock_which):
        mock_run.side_effect = FileNotFoundError
        mock_which.return_value = None
        oci = OpenClawIntegration()
        assert oci.is_installed() is False

    @patch("mado.backend.integrations.openclaw.subprocess.run")
    def test_get_version(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="2.1.0\n")
        oci = OpenClawIntegration()
        assert oci.get_version() == "2.1.0"

    @patch("mado.backend.integrations.openclaw.subprocess.run")
    def test_get_version_not_installed(self, mock_run):
        mock_run.side_effect = FileNotFoundError
        oci = OpenClawIntegration()
        assert oci.get_version() is None

    @patch("mado.backend.integrations.openclaw.shutil.which")
    @patch("mado.backend.integrations.openclaw.subprocess.run")
    def test_install_npm_not_found(self, mock_run, mock_which):
        mock_which.return_value = None
        oci = OpenClawIntegration()
        result = oci.install()
        assert result["success"] is False
        assert result["error_code"] == "npm_not_found"

    @patch("mado.backend.integrations.openclaw.shutil.which")
    @patch("mado.backend.integrations.openclaw.subprocess.run")
    def test_install_success(self, mock_run, mock_which):
        mock_which.return_value = "/usr/bin/npm"
        mock_run.return_value = MagicMock(returncode=0, stdout="installed", stderr="")
        oci = OpenClawIntegration()
        result = oci.install()
        assert result["success"] is True

    @patch("mado.backend.integrations.openclaw.subprocess.run")
    def test_ensure_installed_already(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="1.0.0")
        oci = OpenClawIntegration()
        result = oci.ensure_installed()
        assert result["status"] == "already_installed"

    @patch("mado.backend.integrations.openclaw.subprocess.Popen")
    def test_start_gateway(self, mock_popen):
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process
        oci = OpenClawIntegration()
        result = oci.start_gateway()
        assert result["status"] == "started"
        assert result["pid"] == 12345

    @patch("mado.backend.integrations.openclaw.subprocess.Popen")
    def test_start_gateway_error(self, mock_popen):
        mock_popen.side_effect = FileNotFoundError("openclaw not found")
        oci = OpenClawIntegration()
        result = oci.start_gateway()
        assert result["status"] == "error"
