"""AgentFactory - Dynamic agent creation, tool binding, and registration."""

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

# Role -> tool type mapping
# Each role gets tools appropriate to its responsibilities
ROLE_TOOLS: dict[str, list[str]] = {
    "cto": ["file", "memory"],
    "manager": ["file", "memory"],
    "researcher": ["file", "web", "memory"],
    "engineer": ["file", "exec", "memory"],
    "reviewer": ["file", "exec", "memory"],
    "tester": ["file", "exec", "memory"],
    "optimizer": ["file", "exec", "memory"],
    "documenter": ["file", "memory"],
}


def _create_tools(tool_types: list[str], workspace_path: str) -> list:
    """Instantiate tool objects for the given tool type names."""
    tools = []
    for tool_type in tool_types:
        if tool_type == "file":
            from mado.backend.tools.file_tools import FileTools
            tools.append(FileTools(workspace_path))
        elif tool_type == "exec":
            from mado.backend.tools.exec_tools import ExecTools
            tools.append(ExecTools(workspace_path))
        elif tool_type == "web":
            from mado.backend.tools.web_tools import WebTools
            tools.append(WebTools())
        elif tool_type == "memory":
            from mado.backend.tools.memory_tools import MemoryTools
            tools.append(MemoryTools(workspace_path))
    return tools


class AgentFactory:
    """Create agents dynamically based on role, model, and workspace.

    Automatically attaches appropriate tools based on role.
    """

    def __init__(self, model_manager: ModelManager):
        self.model_manager = model_manager
        self.registry: dict = {}

    def create(self, role: str, workspace_path: str) -> "BaseAgent":
        """Instantiate agent, assign model, auto-attach tools, bind workspace, register."""
        import importlib

        if role not in AGENT_CLASSES:
            raise ValueError(f"Unknown agent role: {role}")

        module_path, class_name = AGENT_CLASSES[role].rsplit(".", 1)
        module = importlib.import_module(module_path)
        agent_class = getattr(module, class_name)

        model = self.model_manager.get_model(role)
        agent = agent_class(role=role, model=model, workspace_path=workspace_path)

        # Auto-attach tools based on role
        tool_types = ROLE_TOOLS.get(role, ["file"])
        tools = _create_tools(tool_types, workspace_path)
        agent.attach_tools(tools)

        self.registry[role] = agent
        return agent

    def get_agent(self, role: str) -> Optional["BaseAgent"]:
        return self.registry.get(role)

    def list_agents(self) -> list:
        return list(self.registry.keys())

    def get_tool_mapping(self) -> dict:
        """Get the tool types assigned to each registered agent."""
        return {
            role: [type(t).__name__ for t in agent.tools]
            for role, agent in self.registry.items()
            if hasattr(agent, 'tools')
        }
