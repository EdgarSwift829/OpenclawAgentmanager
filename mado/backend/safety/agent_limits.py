"""Agent Limits - Prevent runaway agents with iteration, retry, and timeout controls."""


class AgentLimits:
    """Safety controls for agent execution."""

    DEFAULT_LIMITS = {
        "max_iterations": 10,
        "max_retries": 3,
        "execution_timeout": 300,  # seconds
        "max_tool_calls_per_iteration": 20,
    }

    def __init__(self, limits: dict = None):
        self.limits = {**self.DEFAULT_LIMITS, **(limits or {})}
        self.counters: dict = {}

    def check_iteration(self, agent_id: str, iteration: int) -> bool:
        """Return True if agent is within iteration limit."""
        return iteration <= self.limits["max_iterations"]

    def check_retry(self, agent_id: str) -> bool:
        """Return True if agent hasn't exceeded retry limit."""
        retries = self.counters.get(f"{agent_id}_retries", 0)
        return retries < self.limits["max_retries"]

    def increment_retry(self, agent_id: str) -> None:
        key = f"{agent_id}_retries"
        self.counters[key] = self.counters.get(key, 0) + 1

    def reset_retries(self, agent_id: str) -> None:
        self.counters[f"{agent_id}_retries"] = 0

    def get_timeout(self) -> int:
        return self.limits["execution_timeout"]
