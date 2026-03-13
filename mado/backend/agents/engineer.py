"""Engineer Agent - Write code, modify project files, execute scripts.

The Engineer:
- Reads existing code before modifying
- Writes code using FileTools
- Runs scripts using ExecTools
- Reports files modified and code written
- Uses shared context from researcher/CTO to guide implementation
"""

import logging

from mado.backend.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class EngineerAgent(BaseAgent):
    """Engineer: write code, modify project files, execute scripts with tool support."""

    def execute(self, task: dict) -> dict:
        """Execute an engineering task with file operations."""
        description = task.get("description", "")

        # Gather workspace context
        files = self.list_files()
        shared_ctx = self.build_shared_context()
        iteration_ctx = self.build_iteration_context()

        # Search for relevant code if keywords present
        relevant_code = []
        keywords = [w for w in description.split() if len(w) > 4][:3]
        for kw in keywords:
            results = self.search_code(kw)
            relevant_code.extend(results[:5])

        prompt = (
            f"You are a software engineer. Implement the following task.\n\n"
            f"## Task\n{description}\n\n"
            f"## Workspace Files\n{files[:30]}\n\n"
        )

        if relevant_code:
            code_ctx = "\n".join(
                f"- {r['file']}:{r['line']}: {r['content']}" for r in relevant_code[:10]
            )
            prompt += f"## Relevant Code Found\n{code_ctx}\n\n"

        if shared_ctx:
            prompt += f"{shared_ctx}\n\n"
        if iteration_ctx:
            prompt += f"{iteration_ctx}\n\n"

        prompt += (
            f"Return JSON with the code to write:\n"
            f"```json\n"
            f'{{\n'
            f'  "approach": "Brief description of your approach",\n'
            f'  "files": [\n'
            f'    {{\n'
            f'      "path": "relative/path/to/file.py",\n'
            f'      "action": "create|modify",\n'
            f'      "content": "full file content"\n'
            f'    }}\n'
            f'  ],\n'
            f'  "summary": "What was implemented"\n'
            f'}}\n'
            f"```\n"
        )

        result = self.call_llm_json(prompt, fallback=None)

        files_modified = []
        if isinstance(result, dict) and "files" in result:
            for file_spec in result["files"]:
                path = file_spec.get("path", "")
                content = file_spec.get("content", "")
                if path and content:
                    write_result = self.write_file(path, content)
                    files_modified.append(path)
                    logger.info(f"[Engineer] {write_result}")

            return self.make_result(
                result=result,
                files_modified=files_modified,
                summary=result.get("summary", f"Implemented: {description[:100]}"),
            )

        # Fallback: raw LLM response as result
        return self.make_result(
            result={"approach": "direct", "raw_output": str(result)[:1000]},
            summary=f"Engineer: {description[:100]}",
        )
