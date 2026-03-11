"""Reviewer Agent - Analyze code, detect bugs, suggest improvements."""

from mado.backend.agents.base_agent import BaseAgent


class ReviewerAgent(BaseAgent):
    """Reviewer: analyze code, detect bugs, suggest improvements."""

    def review(self, results: list) -> dict:
        """Review iteration results and decide if approved."""
        prompt = f"Review these results and decide if they are approved:\n{results}"
        response = self.call_llm(prompt)
        return {"approved": False, "feedback": response}

    def execute(self, task: dict) -> dict:
        prompt = f"Review: {task.get('description', '')}"
        response = self.call_llm(prompt)
        return {"role": self.role, "result": response}
