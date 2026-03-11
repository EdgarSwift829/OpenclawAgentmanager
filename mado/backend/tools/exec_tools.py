"""Execution Tools - run_python, run_tests, install_package (sandboxed)."""

import subprocess
from pathlib import Path

ALLOWED_COMMANDS = {"python", "pytest", "pip"}
BLOCKED_COMMANDS = {"rm", "sudo", "chmod", "chown", "kill", "shutdown", "reboot"}


class ExecTools:
    """Sandboxed execution tools for agents."""

    def __init__(self, workspace_path: str):
        self.workspace = Path(workspace_path).resolve()

    def _check_command(self, cmd: str) -> None:
        base_cmd = cmd.split()[0] if cmd else ""
        if base_cmd in BLOCKED_COMMANDS:
            raise PermissionError(f"Blocked command: {base_cmd}")
        if base_cmd not in ALLOWED_COMMANDS:
            raise PermissionError(f"Command not allowed: {base_cmd}. Allowed: {ALLOWED_COMMANDS}")

    def run_python(self, script_path: str, timeout: int = 60) -> dict:
        """Run a Python script inside the workspace."""
        full_path = (self.workspace / script_path).resolve()
        if not str(full_path).startswith(str(self.workspace)):
            raise PermissionError("Script outside workspace")
        cmd = f"python {full_path}"
        self._check_command("python")
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=str(self.workspace),
        )
        return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}

    def run_tests(self, test_path: str = ".", timeout: int = 120) -> dict:
        """Run pytest inside the workspace."""
        self._check_command("pytest")
        result = subprocess.run(
            f"pytest {test_path}", shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=str(self.workspace),
        )
        return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}

    def install_package(self, package: str, timeout: int = 120) -> dict:
        """Install a Python package via pip."""
        self._check_command("pip")
        result = subprocess.run(
            f"pip install {package}", shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=str(self.workspace),
        )
        return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}
