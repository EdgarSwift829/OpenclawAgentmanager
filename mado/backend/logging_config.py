"""Structured logging configuration for MADO.

Provides:
- JSON-formatted log output for production (MADO_LOG_FORMAT=json)
- Human-readable output for development (default)
- Configurable log levels via MADO_LOG_LEVEL
- Contextual fields (project_id, agent_role, task_id) via LoggerAdapter
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Optional


class JSONFormatter(logging.Formatter):
    """Format log records as JSON for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Add extra fields if present
        for key in ("project_id", "agent_role", "task_id", "event_type", "duration_ms"):
            value = getattr(record, key, None)
            if value is not None:
                log_entry[key] = value
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


class ReadableFormatter(logging.Formatter):
    """Human-readable format for development."""

    def format(self, record: logging.LogRecord) -> str:
        # Add contextual info if available
        extra_parts = []
        for key in ("project_id", "agent_role", "task_id"):
            value = getattr(record, key, None)
            if value is not None:
                extra_parts.append(f"{key}={value}")
        extra = f" [{', '.join(extra_parts)}]" if extra_parts else ""
        timestamp = datetime.now().strftime("%H:%M:%S")
        return f"{timestamp} {record.levelname:<8} {record.name}{extra} | {record.getMessage()}"


class ContextLogger(logging.LoggerAdapter):
    """Logger adapter that injects contextual fields into log records."""

    def process(self, msg, kwargs):
        extra = kwargs.get("extra", {})
        extra.update(self.extra)
        kwargs["extra"] = extra
        return msg, kwargs


def get_context_logger(
    name: str,
    project_id: Optional[str] = None,
    agent_role: Optional[str] = None,
    task_id: Optional[str] = None,
) -> ContextLogger:
    """Create a logger with contextual fields pre-filled."""
    logger = logging.getLogger(name)
    context = {}
    if project_id:
        context["project_id"] = project_id
    if agent_role:
        context["agent_role"] = agent_role
    if task_id:
        context["task_id"] = task_id
    return ContextLogger(logger, context)


def setup_logging() -> None:
    """Configure logging based on environment variables.

    Environment variables:
    - MADO_LOG_LEVEL: DEBUG, INFO, WARNING, ERROR (default: INFO)
    - MADO_LOG_FORMAT: json, readable (default: readable)
    """
    log_level = os.environ.get("MADO_LOG_LEVEL", "INFO").upper()
    log_format = os.environ.get("MADO_LOG_FORMAT", "readable").lower()

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Remove existing handlers
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)

    if log_format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(ReadableFormatter())

    root_logger.addHandler(handler)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
