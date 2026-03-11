"""Manager Agent - Decomposes tasks, assigns work, monitors progress."""

from mado.backend.agents.base_agent import BaseAgent


class ManagerAgent(BaseAgent):
    """Manager: decompose tasks, assign work, monitor progress, manage iteration cycle."""

    def decompose(self, plan: dict) -> list:
        """Break down a plan into individual tasks assigned to agents."""
        prompt = f"Decompose this plan into tasks. Assign each to an agent role.\nPlan: {plan}"
        response = self.call_llm(prompt)
        # Default decomposition
        return [
            {"description": plan.get("plan", ""), "assigned_to": "engineer"},
        ]

    def execute(self, task: dict) -> dict:
        response = self.call_llm(f"Execute manager task: {task}")
        return {"role": self.role, "result": response}
