"""Execution Tools - run_python, run_tests, install_package (sandboxed)."""

import shutil
import subprocess
import sys
from pathlib import Path

ALLOWED_COMMANDS = {"python", "pytest", "pip"}
BLOCKED_COMMANDS = {"rm", "sudo", "chmod", "chown", "kill", "shutdown", "reboot", "mkfs", "dd"}


class ExecTools:
    """Sandboxed execution tools for agents."""

    def __init__(self, workspace_path: str):
        self.workspace = Path(workspace_path).resolve()

    def _check_command(self, cmd: str) -> None:
        if not cmd or not cmd.strip():
            raise PermissionError("Command cannot be empty")
        base_cmd = cmd.split()[0]
        if base_cmd in BLOCKED_COMMANDS:
            raise PermissionError(f"Blocked command: {base_cmd}")
        if base_cmd not in ALLOWED_COMMANDS:
            raise PermissionError(f"Command not allowed: {base_cmd}. Allowed: {ALLOWED_COMMANDS}")

    @staticmethod
    def _resolve_executable(name: str) -> str:
        """Resolve executable path, preferring the current Python environment."""
        if name == "python":
            return sys.executable
        found = shutil.which(name)
        if found:
            return found
        return name

    def _validate_path_in_workspace(self, path: Path) -> None:
        """Ensure a resolved path is within the workspace."""
        try:
            path.relative_to(self.workspace)
        except ValueError as e:
            raise PermissionError(f"Path outside workspace: {path}") from e

    def run_python(self, script_path: str, timeout: int = 60) -> dict:
        """Run a Python script inside the workspace."""
        full_path = (self.workspace / script_path).resolve()
        self._validate_path_in_workspace(full_path)
        self._check_command("python")
        result = subprocess.run(
            [self._resolve_executable("python"), str(full_path)],
            capture_output=True, text=True,
            timeout=timeout, cwd=str(self.workspace),
        )
        return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}

    def run_tests(self, test_path: str = ".", timeout: int = 120) -> dict:
        """Run pytest inside the workspace."""
        self._check_command("pytest")
        resolved_test = (self.workspace / test_path).resolve()
        self._validate_path_in_workspace(resolved_test)
        result = subprocess.run(
            [self._resolve_executable("pytest"), str(resolved_test)],
            capture_output=True, text=True,
            timeout=timeout, cwd=str(self.workspace),
        )
        return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}

    def install_package(self, package: str, timeout: int = 120) -> dict:
        """Install a Python package via pip."""
        self._check_command("pip")
        result = subprocess.run(
            [self._resolve_executable("pip"), "install", package],
            capture_output=True, text=True,
            timeout=timeout, cwd=str(self.workspace),
        )
        return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}
