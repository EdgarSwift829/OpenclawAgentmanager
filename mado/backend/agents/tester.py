"""Tester Agent - Generate tests, run tests, detect failures.

The Tester:
- Reads implementation code from shared context or workspace
- Generates test files using FileTools
- Runs tests using ExecTools
- Reports structured test results
"""

import logging

from mado.backend.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class TesterAgent(BaseAgent):
    """Tester: generate tests, run tests, report failures with tool support."""

    def execute(self, task: dict) -> dict:
        """Execute a testing task - generate and/or run tests."""
        description = task.get("description", "")

        # Find files to test from shared context
        files_to_test = []
        for role, ctx in self.shared_context.items():
            if isinstance(ctx, dict):
                files_to_test.extend(ctx.get("files_modified", []))

        # Read implementation files for context
        code_context = []
        for fpath in files_to_test[:5]:
            content = self.read_file(fpath)
            if not content.startswith("[Error"):
                code_context.append(f"### {fpath}\n```\n{content[:2000]}\n```")

        # List existing test files
        all_files = self.list_files()
        test_files = [f for f in all_files if "test" in f.lower()]

        prompt = (
            f"You are a test engineer. Create and run tests.\n\n"
            f"## Task\n{description}\n\n"
        )

        if code_context:
            prompt += f"## Implementation Code\n{''.join(code_context)}\n\n"
        if test_files:
            prompt += f"## Existing Test Files\n{test_files}\n\n"

        prompt += (
            f"Return JSON:\n"
            f"```json\n"
            f'{{\n'
            f'  "test_files": [\n'
            f'    {{"path": "tests/test_xxx.py", "content": "test code"}}\n'
            f'  ],\n'
            f'  "test_strategy": "Description of testing approach",\n'
            f'  "coverage_areas": ["area1", "area2"],\n'
            f'  "summary": "What was tested"\n'
            f'}}\n'
            f"```"
        )

        result = self.call_llm_json(prompt, fallback=None)

        files_written = []
        test_output = None

        if isinstance(result, dict) and "test_files" in result:
            # Write test files
            for tf in result["test_files"]:
                path = tf.get("path", "")
                content = tf.get("content", "")
                if path and content:
                    write_result = self.write_file(path, content)
                    files_written.append(path)
                    logger.info(f"[Tester] {write_result}")

            # Try to run tests
            if files_written:
                test_output = self.run_tests()
                if test_output:
                    result["test_output"] = {
                        "stdout": test_output.get("stdout", "")[:1000],
                        "stderr": test_output.get("stderr", "")[:500],
                        "returncode": test_output.get("returncode"),
                        "passed": test_output.get("returncode") == 0,
                    }

        summary = result.get("summary", "") if isinstance(result, dict) else str(result)[:200]
        return self.make_result(
            result=result,
            files_modified=files_written,
            summary=f"Tests: {summary[:100]}",
        )
