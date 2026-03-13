"""Execution Tools - run_python, run_tests, install_package (sandboxed)."""

import logging
import re
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

ALLOWED_COMMANDS = {"python", "pytest", "pip"}
BLOCKED_COMMANDS = {"rm", "sudo", "chmod", "chown", "kill", "shutdown", "reboot", "mkfs", "dd"}

# Allowlist for pip install: only these packages can be installed by agents.
# Set to None to allow all packages (not recommended for production).
ALLOWED_PACKAGES: set[str] | None = None

# Blocked pip packages: packages that should never be installed
BLOCKED_PACKAGES = {
    "os-sys", "python-binance", "cryptominer", "keylogger",
}

# Pattern for valid package names (PEP 508 compatible)
_VALID_PACKAGE_RE = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?(\[.+\])?([><=!~].+)?$')


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

    @staticmethod
    def _validate_package(package: str) -> None:
        """Validate package name against allowlist and blocklist."""
        # Extract base package name (strip version specifiers)
        base_name = re.split(r'[><=!~\[]', package)[0].strip().lower()
        if not base_name:
            raise PermissionError("Package name cannot be empty")
        if not _VALID_PACKAGE_RE.match(package):
            raise PermissionError(f"Invalid package name format: {package}")
        if base_name in BLOCKED_PACKAGES:
            raise PermissionError(f"Blocked package: {base_name}")
        if ALLOWED_PACKAGES is not None and base_name not in ALLOWED_PACKAGES:
            raise PermissionError(
                f"Package '{base_name}' not in allowlist. "
                f"Allowed: {ALLOWED_PACKAGES}"
            )

    def install_package(self, package: str, timeout: int = 120) -> dict:
        """Install a Python package via pip with validation."""
        self._check_command("pip")
        self._validate_package(package)
        logger.info(f"Installing package: {package} (workspace: {self.workspace})")
        result = subprocess.run(
            [self._resolve_executable("pip"), "install", package],
            capture_output=True, text=True,
            timeout=timeout, cwd=str(self.workspace),
        )
        return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}
