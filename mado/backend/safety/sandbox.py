"""Sandbox - Isolated execution environment for agent code execution."""

import subprocess
from pathlib import Path

ALLOWED_COMMANDS = {"python", "pytest", "pip"}
BLOCKED_COMMANDS = {"rm", "sudo", "chmod", "chown", "kill", "shutdown", "reboot", "mkfs", "dd"}


class Sandbox:
    """Enforce sandboxed execution: only allowed commands, within workspace."""

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
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=str(self.workspace),
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"error": f"Command timed out after {timeout}s", "returncode": -1}
