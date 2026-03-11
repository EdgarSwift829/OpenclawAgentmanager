"""Tester Agent - Generate tests, run tests, detect failures."""

from mado.backend.agents.base_agent import BaseAgent


class TesterAgent(BaseAgent):
    """Tester: generate tests, run tests, detect failures."""

    def execute(self, task: dict) -> dict:
        prompt = f"Generate and run tests for: {task.get('description', '')}"
        response = self.call_llm(prompt)
        return {"role": self.role, "result": response}
