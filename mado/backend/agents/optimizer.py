"""Optimizer Agent - Performance tuning, code refactoring, resource optimization."""

from mado.backend.agents.base_agent import BaseAgent


class OptimizerAgent(BaseAgent):
    """Optimizer: performance tuning, code refactoring, resource optimization."""

    def execute(self, task: dict) -> dict:
        prompt = f"Optimize: {task.get('description', '')}"
        response = self.call_llm(prompt)
        return {"role": self.role, "result": response}
