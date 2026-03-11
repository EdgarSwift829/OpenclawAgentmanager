"""Engineer Agent - Write code, modify project files, execute scripts."""

from mado.backend.agents.base_agent import BaseAgent


class EngineerAgent(BaseAgent):
    """Engineer: write code, modify project files, execute scripts."""

    def execute(self, task: dict) -> dict:
        prompt = f"Implement the following task:\n{task.get('description', '')}"
        response = self.call_llm(prompt)
        return {"role": self.role, "result": response}
