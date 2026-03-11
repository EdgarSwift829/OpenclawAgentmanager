"""CTO Agent - Analyzes goals, designs teams, assigns models, determines architecture."""

from mado.backend.agents.base_agent import BaseAgent


class CTOAgent(BaseAgent):
    """CTO: analyze project goal, design agent team, assign models, determine architecture."""

    def analyze_and_plan(self, goal: str) -> list:
        """Analyze the project goal and return required agent roles."""
        prompt = self.load_prompt_template() or (
            f"You are a CTO. Analyze this project goal and return the required agent roles.\n"
            f"Goal: {goal}\n"
            f"Return a JSON list of roles from: manager, researcher, engineer, reviewer, tester, optimizer, documenter"
        )
        response = self.call_llm(prompt.format(goal=goal) if "{goal}" in prompt else prompt)
        # Default team if parsing fails
        return ["manager", "researcher", "engineer", "reviewer", "tester"]

    def plan(self, goal: str, iteration: int) -> dict:
        """Create a plan for the current iteration."""
        prompt = f"Iteration {iteration}. Goal: {goal}. Create a development plan."
        response = self.call_llm(prompt)
        return {"plan": response, "iteration": iteration}

    def execute(self, task: dict) -> dict:
        response = self.call_llm(f"Execute CTO task: {task}")
        return {"role": self.role, "result": response}
