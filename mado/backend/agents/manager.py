"""Manager Agent - Decomposes CTO plans into executable task DAGs.

The Manager:
- Takes the CTO's structured plan and creates concrete, actionable tasks
- Builds proper dependency graphs (task_id + depends_on)
- Assigns tasks to the right agent roles
- Monitors progress and adjusts priorities
"""

import logging
from mado.backend.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ManagerAgent(BaseAgent):
    """Manager: decompose plans into task DAGs, assign work, track progress."""

    def decompose(self, plan: dict) -> list:
        """Break down a CTO plan into individual tasks with dependencies."""
        # If CTO already produced structured tasks, extract them
        phases = plan.get("phases", [])
        if phases:
            tasks = self._extract_tasks_from_phases(phases)
            if tasks:
                logger.info(f"[Manager] Extracted {len(tasks)} tasks from CTO plan")
                return tasks

        # Otherwise, ask LLM to decompose
        plan_text = plan.get("plan_summary", "") or plan.get("plan", "")
        iteration_ctx = self.build_iteration_context()

        prompt = (
            f"You are the project manager. Decompose this plan into concrete tasks.\n\n"
            f"## Plan\n{plan_text}\n\n"
        )

        if iteration_ctx:
            prompt += f"{iteration_ctx}\n\n"

        prompt += (
            f"Available agent roles: manager, researcher, engineer, reviewer, tester, "
            f"optimizer, documenter, marketer\n\n"
            f"Create tasks with dependencies. Return JSON:\n"
            f"```json\n"
            f'[\n'
            f'  {{"task_id": "unique_id", "description": "Concrete task", '
            f'"assigned_to": "role", "depends_on": [], "priority": "high"}}\n'
            f']\n'
            f"```\n\n"
            f"Rules:\n"
            f"- Parallel tasks should NOT depend on each other\n"
            f"- Testing depends on implementation\n"
            f"- Review depends on implementation\n"
            f"- Research usually has no dependencies\n"
        )

        result = self.call_llm_json(prompt, fallback=None)

        if isinstance(result, list) and result:
            valid_tasks = self._validate_tasks(result)
            if valid_tasks:
                logger.info(f"[Manager] LLM decomposed into {len(valid_tasks)} tasks")
                return valid_tasks

        # Fallback
        logger.warning("[Manager] Could not decompose plan, creating single engineer task")
        return [
            {
                "task_id": "implement_1",
                "description": plan_text[:500] or "Implement the planned changes",
                "assigned_to": "engineer",
                "depends_on": [],
                "priority": "high",
            }
        ]

    def _extract_tasks_from_phases(self, phases: list) -> list:
        """Extract and flatten tasks from CTO's phased plan."""
        all_tasks = []
        for phase in phases:
            for task in phase.get("tasks", []):
                if isinstance(task, dict) and task.get("description"):
                    if not task.get("task_id"):
                        task["task_id"] = f"task_{len(all_tasks)}"
                    if not task.get("assigned_to"):
                        task["assigned_to"] = "engineer"
                    if not task.get("depends_on"):
                        task["depends_on"] = []
                    if not task.get("priority"):
                        task["priority"] = "medium"
                    task["phase"] = phase.get("phase", "")
                    all_tasks.append(task)
        return all_tasks

    def _validate_tasks(self, tasks: list) -> list:
        """Validate and clean task structures from LLM output."""
        valid = []
        seen_ids = set()

        for i, task in enumerate(tasks):
            if not isinstance(task, dict):
                continue
            task_id = task.get("task_id", f"task_{i}")
            if task_id in seen_ids:
                task_id = f"{task_id}_{i}"
            seen_ids.add(task_id)

            valid.append({
                "task_id": task_id,
                "description": task.get("description", "Unnamed task"),
                "assigned_to": task.get("assigned_to", "engineer"),
                "depends_on": task.get("depends_on", []) or [],
                "priority": task.get("priority", "medium"),
            })

        # Remove references to non-existent task_ids
        valid_ids = {t["task_id"] for t in valid}
        for task in valid:
            task["depends_on"] = [d for d in task["depends_on"] if d in valid_ids]

        return valid

    def execute(self, task: dict) -> dict:
        """Execute a management task (progress tracking, coordination)."""
        description = task.get("description", "")

        prompt = (
            f"As the project manager, handle this task:\n{description}\n\n"
            f"Return JSON:\n"
            f"```json\n"
            f'{{"action": "what you did", "status_update": "status", '
            f'"blockers": [], "next_steps": []}}\n'
            f"```"
        )

        result = self.call_llm_json(prompt, fallback={
            "action": description,
            "status_update": "In progress",
            "blockers": [],
            "next_steps": [],
        })

        return self.make_result(result=result, summary=f"Manager: {description[:100]}")
