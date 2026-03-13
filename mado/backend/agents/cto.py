"""CTO Agent - Analyzes goals, designs teams, creates structured development plans.

The CTO is the strategic leader:
- Analyzes the project goal and determines the optimal agent team
- Creates phased development plans with task dependencies
- Adapts plans based on iteration feedback
- Considers project rules (must/forbidden) in all decisions
"""

import logging

from mado.backend.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

AVAILABLE_ROLES = [
    "manager", "researcher", "engineer", "reviewer",
    "tester", "optimizer", "documenter", "marketer",
]

DEFAULT_TEAM = ["manager", "researcher", "engineer", "reviewer", "tester"]


class CTOAgent(BaseAgent):
    """CTO: analyze project goal, design agent team, create architecture and plans."""

    def analyze_and_plan(self, goal: str) -> list:
        """Analyze the project goal and return required agent roles."""
        prompt = (
            f"You are a CTO assembling a development team.\n\n"
            f"Project Goal:\n{goal}\n\n"
            f"Available roles: {', '.join(AVAILABLE_ROLES)}\n\n"
            f"Based on the goal, select which roles are needed.\n"
            f"Consider:\n"
            f"- 'researcher' if the goal involves unknown technologies or research\n"
            f"- 'tester' if quality assurance is important\n"
            f"- 'optimizer' if performance is a key concern\n"
            f"- 'documenter' if documentation deliverables are needed\n"
            f"- 'marketer' if marketing/promotion tasks are involved\n"
            f"- 'manager' is recommended for complex multi-step projects\n"
            f"- 'engineer' is almost always needed\n"
            f"- 'reviewer' is recommended for code quality\n\n"
            f"Return a JSON array of role strings. Example:\n"
            f'```json\n["manager", "engineer", "reviewer", "tester"]\n```'
        )

        response = self.call_llm(prompt)
        roles = self.extract_list_from_text(response, valid_items=AVAILABLE_ROLES)

        if not roles:
            logger.warning("[CTO] Could not parse team roles from LLM, using default team")
            roles = list(DEFAULT_TEAM)

        if "engineer" not in roles:
            roles.append("engineer")

        logger.info(f"[CTO] Team composition: {roles}")
        return roles

    def plan(self, goal: str, iteration: int) -> dict:
        """Create a structured development plan for the current iteration."""
        iteration_ctx = self.build_iteration_context()
        shared_ctx = self.build_shared_context()

        prompt = (
            f"You are the CTO. Create a development plan for iteration {iteration}.\n\n"
            f"## Project Goal\n{goal}\n\n"
        )

        if iteration_ctx:
            prompt += f"{iteration_ctx}\n\n"
        if shared_ctx:
            prompt += f"{shared_ctx}\n\n"

        prompt += (
            f"Create a structured plan. Return JSON:\n"
            f"```json\n"
            f'{{\n'
            f'  "plan_summary": "Brief description of what this iteration achieves",\n'
            f'  "architecture_notes": "Key technical decisions",\n'
            f'  "phases": [\n'
            f'    {{\n'
            f'      "phase": "Phase name",\n'
            f'      "tasks": [\n'
            f'        {{\n'
            f'          "task_id": "unique_id",\n'
            f'          "description": "What to do",\n'
            f'          "assigned_to": "role_name",\n'
            f'          "depends_on": ["other_task_id"],\n'
            f'          "priority": "high|medium|low"\n'
            f'        }}\n'
            f'      ]\n'
            f'    }}\n'
            f'  ]\n'
            f'}}\n'
            f"```\n"
        )

        response = self.call_llm(prompt)
        parsed = self.extract_json(response)

        if isinstance(parsed, dict) and "phases" in parsed:
            parsed["iteration"] = iteration
            parsed["raw_response"] = response[:500]
            logger.info(f"[CTO] Plan created: {parsed.get('plan_summary', '')[:100]}")
            return parsed

        # Fallback: structured plan from raw response
        logger.warning("[CTO] Could not parse structured plan, creating fallback plan")
        return {
            "plan_summary": response[:200] if response else "Development iteration",
            "architecture_notes": "",
            "iteration": iteration,
            "phases": [
                {
                    "phase": "Implementation",
                    "tasks": [
                        {
                            "task_id": "research_1",
                            "description": f"Research requirements for: {goal[:200]}",
                            "assigned_to": "researcher",
                            "depends_on": [],
                            "priority": "high",
                        },
                        {
                            "task_id": "implement_1",
                            "description": f"Implement: {goal[:200]}",
                            "assigned_to": "engineer",
                            "depends_on": ["research_1"],
                            "priority": "high",
                        },
                        {
                            "task_id": "test_1",
                            "description": "Test the implementation",
                            "assigned_to": "tester",
                            "depends_on": ["implement_1"],
                            "priority": "medium",
                        },
                        {
                            "task_id": "review_1",
                            "description": "Review code quality and correctness",
                            "assigned_to": "reviewer",
                            "depends_on": ["implement_1"],
                            "priority": "medium",
                        },
                    ],
                }
            ],
            "raw_response": response[:500] if response else "",
        }

    def execute(self, task: dict) -> dict:
        """Execute a CTO-level task (architecture decisions, technical guidance)."""
        description = task.get("description", "")
        files = self.list_files()

        prompt = (
            f"As the CTO, execute this task:\n{description}\n\n"
            f"Current workspace files: {files[:20]}\n\n"
            f"Provide architectural guidance and decisions.\n"
            f"Return JSON:\n"
            f"```json\n"
            f'{{"decisions": ["..."], "recommendations": ["..."], "risks": ["..."]}}\n'
            f"```"
        )

        result = self.call_llm_json(prompt, fallback={
            "decisions": [description],
            "recommendations": [],
            "risks": [],
        })

        return self.make_result(
            result=result,
            summary=f"CTO: {description[:100]}",
        )
