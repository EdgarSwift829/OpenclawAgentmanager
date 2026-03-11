"""Logging System - Log agent messages, tool calls, errors, iteration summaries."""

import json
import logging
from datetime import datetime
from pathlib import Path

STORAGE_DIR = Path(__file__).resolve().parents[2] / "mado" / "backend" / "storage" / "logs"


class MADOLogger:
    """Structured logging for MADO: agent messages, tool calls, errors, iterations."""

    def __init__(self, project_id: str, log_dir: str = None):
        self.project_id = project_id
        self.log_dir = Path(log_dir) if log_dir else STORAGE_DIR / project_id
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # File logger
        self.logger = logging.getLogger(f"mado.{project_id}")
        self.logger.setLevel(logging.DEBUG)

        handler = logging.FileHandler(self.log_dir / "mado.log")
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        if not self.logger.handlers:
            self.logger.addHandler(handler)

        # Structured log file
        self.structured_log = self.log_dir / "structured.jsonl"

    def _write_structured(self, event: dict) -> None:
        event["timestamp"] = datetime.utcnow().isoformat()
        event["project_id"] = self.project_id
        with open(self.structured_log, "a") as f:
            f.write(json.dumps(event) + "\n")

    def log_agent_message(self, role: str, message: str, direction: str = "output") -> None:
        """Log an agent message."""
        self.logger.info(f"[{role}] ({direction}) {message[:200]}")
        self._write_structured({
            "type": "agent_message",
            "role": role,
            "direction": direction,
            "message": message,
        })

    def log_tool_call(self, role: str, tool: str, args: dict, result: str = "") -> None:
        """Log a tool call."""
        self.logger.info(f"[{role}] tool:{tool} args:{args}")
        self._write_structured({
            "type": "tool_call",
            "role": role,
            "tool": tool,
            "args": args,
            "result": result[:500] if result else "",
        })

    def log_error(self, role: str, error: str) -> None:
        """Log an error."""
        self.logger.error(f"[{role}] {error}")
        self._write_structured({
            "type": "error",
            "role": role,
            "error": error,
        })

    def log_iteration_summary(self, iteration: int, summary: str) -> None:
        """Log an iteration summary."""
        self.logger.info(f"[iteration:{iteration}] {summary[:200]}")
        self._write_structured({
            "type": "iteration_summary",
            "iteration": iteration,
            "summary": summary,
        })

    def get_logs(self, log_type: str = None, limit: int = 100) -> list:
        """Read structured logs, optionally filtered by type."""
        if not self.structured_log.exists():
            return []
        logs = []
        with open(self.structured_log) as f:
            for line in f:
                entry = json.loads(line.strip())
                if log_type is None or entry.get("type") == log_type:
                    logs.append(entry)
        return logs[-limit:]
