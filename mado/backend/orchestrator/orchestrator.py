"""Orchestrator - Main loop for multi-agent task execution."""

from typing import Optional
from mado.backend.orchestrator.agent_factory import AgentFactory
from mado.backend.orchestrator.workspace_manager import WorkspaceManager
from mado.backend.models.model_manager import ModelManager


class Orchestrator:
    """Core orchestration loop: goal -> CTO planning -> Manager breakdown -> execute -> review -> iterate."""

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.workspace_manager = WorkspaceManager()
        self.model_manager = ModelManager()
        self.agent_factory = AgentFactory(self.model_manager)
        self.agents: dict = {}
        self.iteration = 0
        self.max_iterations = 10

    def initialize_project(self, goal: str) -> None:
        """Initialize workspace and spawn agents for a project."""
        self.workspace_manager.create_workspace(self.project_id)
        workspace_path = self.workspace_manager.get_workspace_path(self.project_id)

        # CTO analyzes the goal and determines required roles
        cto = self.agent_factory.create("cto", workspace_path)
        self.agents["cto"] = cto

        required_roles = cto.analyze_and_plan(goal)

        # Spawn required agents
        for role in required_roles:
            agent = self.agent_factory.create(role, workspace_path)
            self.agents[role] = agent

    def run(self, goal: str) -> dict:
        """Execute the main orchestration loop."""
        self.initialize_project(goal)

        results = []
        while self.iteration < self.max_iterations:
            self.iteration += 1

            # CTO planning
            plan = self.agents["cto"].plan(goal, self.iteration)

            # Manager task breakdown
            if "manager" in self.agents:
                tasks = self.agents["manager"].decompose(plan)
            else:
                tasks = [plan]

            # Execute tasks
            iteration_results = []
            for task in tasks:
                agent_role = task.get("assigned_to", "engineer")
                if agent_role in self.agents:
                    result = self.agents[agent_role].execute(task)
                    iteration_results.append(result)

            # Review
            if "reviewer" in self.agents:
                review = self.agents["reviewer"].review(iteration_results)
                if review.get("approved", False):
                    break

            results.extend(iteration_results)

        return {"project_id": self.project_id, "iterations": self.iteration, "results": results}
