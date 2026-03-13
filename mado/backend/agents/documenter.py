"""Documenter Agent - Write documentation, generate README, maintain specifications.

The Documenter:
- Reads project files and code to understand what to document
- Generates README, API docs, architecture docs
- Uses shared context from other agents
"""

import logging

from mado.backend.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class DocumenterAgent(BaseAgent):
    """Documenter: write documentation, generate README, maintain specs."""

    def execute(self, task: dict) -> dict:
        """Execute a documentation task."""
        description = task.get("description", "")

        # Gather project context
        files = self.list_files()
        shared_ctx = self.build_shared_context()

        # Read key files for documentation
        code_context = []
        for fpath in files[:10]:
            if any(fpath.endswith(ext) for ext in [".py", ".ts", ".js", ".yaml", ".json"]):
                content = self.read_file(fpath)
                if not content.startswith("[Error") and len(content) < 3000:
                    code_context.append(f"### {fpath}\n```\n{content[:1500]}\n```")

        prompt = (
            f"You are a technical writer. Create documentation.\n\n"
            f"## Task\n{description}\n\n"
            f"## Project Files\n{files[:20]}\n\n"
        )

        if code_context:
            prompt += f"## Source Code\n{''.join(code_context[:5])}\n\n"
        if shared_ctx:
            prompt += f"{shared_ctx}\n\n"

        prompt += (
            f"Return JSON:\n"
            f"```json\n"
            f'{{\n'
            f'  "documents": [\n'
            f'    {{"path": "docs/filename.md", "content": "document content"}}\n'
            f'  ],\n'
            f'  "summary": "What was documented"\n'
            f'}}\n'
            f"```"
        )

        result = self.call_llm_json(prompt, fallback={
            "documents": [],
            "summary": description[:200],
        })

        files_written = []
        if isinstance(result, dict):
            for doc in result.get("documents", []):
                path = doc.get("path", "")
                content = doc.get("content", "")
                if path and content:
                    self.write_file(path, content)
                    files_written.append(path)

        summary = result.get("summary", "") if isinstance(result, dict) else str(result)[:200]
        return self.make_result(
            result=result,
            files_modified=files_written,
            summary=f"Docs: {summary[:100]}",
        )
