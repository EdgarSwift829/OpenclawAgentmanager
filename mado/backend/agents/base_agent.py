"""BaseAgent - Abstract base class for all agents."""

from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseAgent(ABC):
    """Base class that all agents inherit from."""

    def __init__(self, role: str, model: dict, workspace_path: str):
        self.role = role
        self.model = model
        self.workspace_path = workspace_path
        self.tools: list = []
        self.iteration_count = 0
        self.max_retries = 3

    @abstractmethod
    def execute(self, task: dict) -> dict:
        """Execute a given task and return results."""
        pass

    def call_llm(self, prompt: str, system_prompt: Optional[str] = None,
                  project_memory: str = "", retrieved_files: list = None) -> str:
        """Send prompt to the assigned LLM model with token-optimized context."""
        from mado.backend.models.router import route_inference
        from mado.backend.token_optimizer import TokenOptimizer

        optimizer = TokenOptimizer()
        optimized_prompt = optimizer.build_context(
            system_prompt=system_prompt or self.load_prompt_template(),
            task=prompt,
            project_memory=project_memory,
            retrieved_files=retrieved_files or [],
        )
        return route_inference(
            model=self.model,
            prompt=optimized_prompt,
            system_prompt=None,
        )

    def load_prompt_template(self) -> str:
        """Load the prompt template for this agent role."""
        from pathlib import Path
        prompt_path = Path(__file__).resolve().parents[3] / "prompts" / f"{self.role}.txt"
        if prompt_path.exists():
            return prompt_path.read_text()
        return ""

    def attach_tools(self, tools: list) -> None:
        """Attach tools to this agent."""
        self.tools = tools
