"""Researcher Agent - Web search, documentation lookup, summarize findings."""

from mado.backend.agents.base_agent import BaseAgent


class ResearcherAgent(BaseAgent):
    """Researcher: web search, documentation lookup, summarize findings."""

    def execute(self, task: dict) -> dict:
        prompt = f"Research the following: {task.get('description', '')}"
        response = self.call_llm(prompt)
        return {"role": self.role, "result": response}
