"""Documenter Agent - Write documentation, generate README, maintain specifications."""

from mado.backend.agents.base_agent import BaseAgent


class DocumenterAgent(BaseAgent):
    """Documenter: write documentation, generate README, maintain specifications."""

    def execute(self, task: dict) -> dict:
        prompt = f"Document: {task.get('description', '')}"
        response = self.call_llm(prompt)
        return {"role": self.role, "result": response}
