"""Optimizer Agent - Performance tuning, code refactoring, resource optimization.

The Optimizer:
- Reads existing code and identifies performance bottlenecks
- Suggests and applies optimizations
- Measures improvements where possible
"""

import logging

from mado.backend.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class OptimizerAgent(BaseAgent):
    """Optimizer: performance tuning, code refactoring, resource optimization."""

    def execute(self, task: dict) -> dict:
        """Execute an optimization task."""
        description = task.get("description", "")

        # Find files to optimize from shared context
        target_files = []
        for role, ctx in self.shared_context.items():
            if isinstance(ctx, dict):
                target_files.extend(ctx.get("files_modified", []))

        # Read target files
        code_context = []
        for fpath in target_files[:5]:
            content = self.read_file(fpath)
            if not content.startswith("[Error"):
                code_context.append(f"### {fpath}\n```\n{content[:2000]}\n```")

        prompt = (
            f"You are a performance optimizer. Analyze and optimize.\n\n"
            f"## Task\n{description}\n\n"
        )

        if code_context:
            prompt += f"## Code to Optimize\n{''.join(code_context)}\n\n"

        prompt += (
            f"Return JSON:\n"
            f"```json\n"
            f'{{\n'
            f'  "bottlenecks": [{{"location": "file:line", "issue": "description", "severity": "high|medium|low"}}],\n'
            f'  "optimizations": [\n'
            f'    {{"file": "path", "change": "description", "content": "optimized code"}}\n'
            f'  ],\n'
            f'  "estimated_impact": "description of expected improvement",\n'
            f'  "summary": "What was optimized"\n'
            f'}}\n'
            f"```"
        )

        result = self.call_llm_json(prompt, fallback={
            "bottlenecks": [],
            "optimizations": [],
            "estimated_impact": "Unknown",
            "summary": description[:200],
        })

        # Apply optimizations
        files_modified = []
        if isinstance(result, dict):
            for opt in result.get("optimizations", []):
                fpath = opt.get("file", "")
                content = opt.get("content", "")
                if fpath and content:
                    self.write_file(fpath, content)
                    files_modified.append(fpath)

        summary = result.get("summary", "") if isinstance(result, dict) else str(result)[:200]
        return self.make_result(
            result=result,
            files_modified=files_modified,
            summary=f"Optimize: {summary[:100]}",
        )
