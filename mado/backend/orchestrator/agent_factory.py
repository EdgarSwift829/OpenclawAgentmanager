"""AgentFactory - Dynamic agent creation and registration."""

from typing import Optional
from mado.backend.models.model_manager import ModelManager


AGENT_CLASSES = {
    "cto": "mado.backend.agents.cto.CTOAgent",
    "manager": "mado.backend.agents.manager.ManagerAgent",
    "researcher": "mado.backend.agents.researcher.ResearcherAgent",
    "engineer": "mado.backend.agents.engineer.EngineerAgent",
    "reviewer": "mado.backend.agents.reviewer.ReviewerAgent",
    "tester": "mado.backend.agents.tester.TesterAgent",
    "optimizer": "mado.backend.agents.optimizer.OptimizerAgent",
    "documenter": "mado.backend.agents.documenter.DocumenterAgent",
}


class AgentFactory:
    """Create agents dynamically based on role, model, and workspace."""

    def __init__(self, model_manager: ModelManager):
        self.model_manager = model_manager
        self.registry: dict = {}

    def create(self, role: str, workspace_path: str) -> "BaseAgent":
        """Instantiate agent, assign model, attach tools, bind workspace, register."""
        import importlib

        if role not in AGENT_CLASSES:
            raise ValueError(f"Unknown agent role: {role}")

        module_path, class_name = AGENT_CLASSES[role].rsplit(".", 1)
        module = importlib.import_module(module_path)
        agent_class = getattr(module, class_name)

        model = self.model_manager.get_model(role)
        agent = agent_class(role=role, model=model, workspace_path=workspace_path)

        self.registry[role] = agent
        return agent

    def get_agent(self, role: str) -> Optional["BaseAgent"]:
        return self.registry.get(role)

    def list_agents(self) -> list:
        return list(self.registry.keys())
