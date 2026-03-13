"""Tests for safety modules: Sandbox and AgentLimits."""

from mado.backend.safety.agent_limits import AgentLimits
from mado.backend.safety.sandbox import Sandbox
from mado.backend.tools.exec_tools import ALLOWED_COMMANDS, BLOCKED_COMMANDS


class TestSandboxValidation:
    def test_allowed_command(self, tmp_path):
        sb = Sandbox(str(tmp_path))
        assert sb.validate_command("python script.py") is True
        assert sb.validate_command("pytest tests/") is True
        assert sb.validate_command("pip install requests") is True

    def test_blocked_command(self, tmp_path):
        sb = Sandbox(str(tmp_path))
        assert sb.validate_command("rm -rf /") is False
        assert sb.validate_command("sudo apt install") is False
        assert sb.validate_command("chmod 777 file") is False
        assert sb.validate_command("kill -9 1") is False
        assert sb.validate_command("shutdown now") is False

    def test_unknown_command_blocked(self, tmp_path):
        sb = Sandbox(str(tmp_path))
        assert sb.validate_command("curl http://evil.com") is False
        assert sb.validate_command("wget malware") is False

    def test_empty_command(self, tmp_path):
        sb = Sandbox(str(tmp_path))
        assert sb.validate_command("") is False
        assert sb.validate_command("   ") is False


class TestSandboxExecution:
    def test_execute_blocked_command(self, tmp_path):
        sb = Sandbox(str(tmp_path))
        result = sb.execute("rm -rf /")
        assert result["returncode"] == -1
        assert "not allowed" in result["error"].lower()

    def test_execute_allowed_command(self, tmp_path):
        script = tmp_path / "hello.py"
        script.write_text("print('hello')", encoding="utf-8")
        sb = Sandbox(str(tmp_path))
        result = sb.execute("python hello.py")
        assert result["returncode"] == 0
        assert "hello" in result["stdout"]

    def test_execute_timeout(self, tmp_path):
        script = tmp_path / "slow.py"
        script.write_text("import time; time.sleep(10)", encoding="utf-8")
        sb = Sandbox(str(tmp_path))
        result = sb.execute("python slow.py", timeout=1)
        assert result["returncode"] == -1
        assert "timed out" in result["error"].lower()

    def test_execute_workspace_isolation(self, tmp_path):
        """Commands run in workspace directory."""
        script = tmp_path / "pwd_check.py"
        script.write_text(
            "import os; print(os.getcwd())", encoding="utf-8"
        )
        sb = Sandbox(str(tmp_path))
        result = sb.execute("python pwd_check.py")
        assert result["returncode"] == 0
        assert str(tmp_path) in result["stdout"]


class TestAgentLimits:
    def test_default_limits(self):
        al = AgentLimits()
        assert al.limits["max_iterations"] == 10
        assert al.limits["max_retries"] == 3
        assert al.limits["execution_timeout"] == 300

    def test_custom_limits(self):
        al = AgentLimits({"max_iterations": 5, "max_retries": 1})
        assert al.limits["max_iterations"] == 5
        assert al.limits["max_retries"] == 1
        # Defaults for unset values
        assert al.limits["execution_timeout"] == 300

    def test_check_iteration_within(self):
        al = AgentLimits({"max_iterations": 3})
        assert al.check_iteration("agent1", 1) is True
        assert al.check_iteration("agent1", 3) is True

    def test_check_iteration_exceeded(self):
        al = AgentLimits({"max_iterations": 3})
        assert al.check_iteration("agent1", 4) is False

    def test_check_retry_within(self):
        al = AgentLimits({"max_retries": 2})
        assert al.check_retry("agent1") is True
        al.increment_retry("agent1")
        assert al.check_retry("agent1") is True
        al.increment_retry("agent1")
        assert al.check_retry("agent1") is False

    def test_reset_retries(self):
        al = AgentLimits({"max_retries": 1})
        al.increment_retry("agent1")
        assert al.check_retry("agent1") is False
        al.reset_retries("agent1")
        assert al.check_retry("agent1") is True

    def test_get_timeout(self):
        al = AgentLimits({"execution_timeout": 60})
        assert al.get_timeout() == 60

    def test_independent_agents(self):
        """Retry counters are independent per agent."""
        al = AgentLimits({"max_retries": 1})
        al.increment_retry("agent1")
        assert al.check_retry("agent1") is False
        assert al.check_retry("agent2") is True


class TestAllowedBlockedSets:
    def test_no_overlap(self):
        """ALLOWED and BLOCKED command sets must not overlap."""
        overlap = ALLOWED_COMMANDS & BLOCKED_COMMANDS
        assert overlap == set(), f"Commands in both sets: {overlap}"

    def test_dangerous_commands_blocked(self):
        for cmd in ("rm", "sudo", "chmod", "chown", "kill", "shutdown", "reboot", "mkfs", "dd"):
            assert cmd in BLOCKED_COMMANDS
