"""Reviewer Agent - Analyze code, detect bugs, approve or reject iterations.

The Reviewer:
- Reads code files that were modified during the iteration
- Checks against project rules (must/forbidden)
- Provides structured feedback with specific issues
- Makes an approval decision based on quality criteria
"""

import logging
from mado.backend.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ReviewerAgent(BaseAgent):
    """Reviewer: analyze code, detect bugs, approve or reject with structured feedback."""

    def review(self, results: list) -> dict:
        """Review iteration results and decide if approved.

        Parses the LLM response for an explicit approved/rejected decision.
        """
        # Gather what was done in this iteration
        summaries = []
        files_modified = []
        for r in results:
            if isinstance(r, dict):
                summaries.append(f"- [{r.get('role', '?')}] {r.get('summary', str(r.get('result', ''))[:200])}")
                files_modified.extend(r.get("files_modified", []))

        results_text = "\n".join(summaries) if summaries else str(results)[:2000]

        # Read modified files for review
        file_contents = []
        for fpath in files_modified[:5]:  # Limit to 5 files
            content = self.read_file(fpath)
            if not content.startswith("[Error"):
                file_contents.append(f"### {fpath}\n```\n{content[:2000]}\n```")

        # Get project rules for checking
        rules_must = self.project_config.get("rules_must", "")
        rules_forbidden = self.project_config.get("rules_forbidden", "")

        prompt = (
            f"You are a code reviewer. Review the following iteration results.\n\n"
            f"## Work Done\n{results_text}\n\n"
        )

        if file_contents:
            prompt += f"## Modified Files\n{''.join(file_contents[:3])}\n\n"

        if rules_must or rules_forbidden:
            prompt += "## Project Rules to Check Against\n"
            if rules_must:
                prompt += f"MUST follow: {rules_must}\n"
            if rules_forbidden:
                prompt += f"FORBIDDEN: {rules_forbidden}\n"
            prompt += "\n"

        prompt += (
            f"Evaluate quality, correctness, and rule compliance.\n"
            f"Return JSON:\n"
            f"```json\n"
            f'{{\n'
            f'  "approved": true/false,\n'
            f'  "score": 1-10,\n'
            f'  "issues": [\n'
            f'    {{"severity": "critical|warning|info", "description": "...", "file": "..."}}\n'
            f'  ],\n'
            f'  "feedback": "Overall assessment",\n'
            f'  "improvements": ["Suggested improvement 1", "..."]\n'
            f'}}\n'
            f"```\n"
        )

        result = self.call_llm_json(prompt, fallback=None)

        if isinstance(result, dict):
            approved = result.get("approved", False)
            # Ensure approved is actually a boolean
            if isinstance(approved, str):
                approved = approved.lower() in ("true", "yes", "1")
            score = result.get("score", 5)
            issues = result.get("issues", [])

            # Auto-reject if critical issues found
            critical_count = sum(
                1 for i in issues
                if isinstance(i, dict) and i.get("severity") == "critical"
            )
            if critical_count > 0:
                approved = False

            logger.info(
                f"[Reviewer] approved={approved}, score={score}, "
                f"issues={len(issues)}, critical={critical_count}"
            )
            return {
                "approved": approved,
                "score": score,
                "issues": issues,
                "feedback": result.get("feedback", ""),
                "improvements": result.get("improvements", []),
            }

        # Fallback: conservative - don't approve if can't parse
        logger.warning("[Reviewer] Could not parse review, defaulting to not approved")
        return {
            "approved": False,
            "score": 5,
            "issues": [],
            "feedback": str(result)[:500] if result else "Review inconclusive",
            "improvements": [],
        }

    def execute(self, task: dict) -> dict:
        """Execute a review task on specific code or deliverables."""
        description = task.get("description", "")

        # Try to find files to review from shared context
        files_to_review = []
        for role, ctx in self.shared_context.items():
            if isinstance(ctx, dict):
                files_to_review.extend(ctx.get("files_modified", []))

        file_contents = []
        for fpath in files_to_review[:5]:
            content = self.read_file(fpath)
            if not content.startswith("[Error"):
                file_contents.append(f"### {fpath}\n```\n{content[:2000]}\n```")

        prompt = (
            f"Review the following:\n{description}\n\n"
        )
        if file_contents:
            prompt += f"## Code to Review\n{''.join(file_contents)}\n\n"

        prompt += (
            f"Return JSON:\n"
            f"```json\n"
            f'{{"issues": [{{"severity": "critical|warning|info", "description": "..."}}], '
            f'"feedback": "assessment", "quality_score": 1-10}}\n'
            f"```"
        )

        result = self.call_llm_json(prompt, fallback={
            "issues": [],
            "feedback": description,
            "quality_score": 5,
        })

        return self.make_result(result=result, summary=f"Review: {description[:100]}")
