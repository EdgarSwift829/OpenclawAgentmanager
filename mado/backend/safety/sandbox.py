"""Sandbox - Thin wrapper around ExecTools for backward compatibility.

The actual sandboxed execution logic (allowed/blocked commands, shell=False,
workspace isolation) lives in mado.backend.tools.exec_tools.ExecTools.
This module re-exports ExecTools constants and provides a simple Sandbox
facade for any code that imports from here.
"""

import shlex
import shutil
import subprocess
from pathlib import Path

# Re-export the canonical allowlist/blocklist from ExecTools
from mado.backend.tools.exec_tools import ALLOWED_COMMANDS, BLOCKED_COMMANDS


class Sandbox:
    """Enforce sandboxed execution: only allowed commands, within workspace.

    For new code, prefer using ExecTools directly.
    """

    def __init__(self, workspace_path: str):
        self.workspace = Path(workspace_path).resolve()

    def validate_command(self, command: str) -> bool:
        """Check if a command is allowed."""
        base = command.strip().split()[0] if command.strip() else ""
        if base in BLOCKED_COMMANDS:
            return False
        if base not in ALLOWED_COMMANDS:
            return False
        return True

    def execute(self, command: str, timeout: int = 60) -> dict:
        """Execute a command in the sandboxed environment."""
        if not self.validate_command(command):
            return {"error": f"Command not allowed: {command}", "returncode": -1}

        try:
            parts = shlex.split(command)
            executable = shutil.which(parts[0]) or parts[0]
            parts[0] = executable
            result = subprocess.run(
                parts, capture_output=True, text=True,
                timeout=timeout, cwd=str(self.workspace),
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"error": f"Command timed out after {timeout}s", "returncode": -1}
