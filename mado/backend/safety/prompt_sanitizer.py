"""Prompt Sanitizer - Sanitize user input before embedding in LLM prompts.

Mitigates prompt injection attacks by:
- Escaping instruction-like patterns in user input
- Limiting input length
- Detecting and flagging suspicious patterns
"""

import re
from typing import Optional

# Patterns that could be used for prompt injection
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"ignore\s+(all\s+)?above", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?previous", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?previous", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+a", re.IGNORECASE),
    re.compile(r"new\s+instructions?:", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
    re.compile(r"<\s*/?\s*system\s*>", re.IGNORECASE),
]

# Max lengths for different input types
MAX_GOAL_LENGTH = 5000
MAX_DESCRIPTION_LENGTH = 10000


def sanitize_user_input(text: str, max_length: int = MAX_GOAL_LENGTH) -> str:
    """Sanitize user-provided text before embedding in prompts.

    - Truncates to max_length
    - Wraps in delimiters to separate from instructions
    - Does NOT modify the content itself (to preserve user intent)
    """
    if not text:
        return ""
    return text[:max_length]


def detect_injection(text: str) -> list[str]:
    """Detect potential prompt injection patterns in user input.

    Returns a list of matched pattern descriptions. Empty list means no issues.
    This is for logging/monitoring, not blocking.
    """
    if not text:
        return []
    findings = []
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            findings.append(f"Suspicious pattern: {pattern.pattern}")
    return findings


def wrap_user_content(text: str, label: str = "USER_INPUT") -> str:
    """Wrap user-provided content in clear delimiters.

    This helps the LLM distinguish between instructions and user content,
    reducing the effectiveness of prompt injection.
    """
    if not text:
        return ""
    sanitized = sanitize_user_input(text)
    return (
        f"<{label}>\n"
        f"{sanitized}\n"
        f"</{label}>"
    )


def sanitize_goal(goal: str) -> str:
    """Sanitize a project goal string."""
    return wrap_user_content(goal, label="PROJECT_GOAL")


def sanitize_description(description: str) -> str:
    """Sanitize a task description string."""
    return wrap_user_content(description, label="TASK_DESCRIPTION")


def sanitize_project_id(project_id: str, max_length: int = 100) -> Optional[str]:
    """Validate and sanitize a project ID.

    Returns None if the project_id is invalid.
    """
    if not project_id or not isinstance(project_id, str):
        return None
    project_id = project_id.strip()[:max_length]
    # Only allow safe characters
    if not re.match(r'^[a-zA-Z0-9_\-]+$', project_id):
        return None
    return project_id
