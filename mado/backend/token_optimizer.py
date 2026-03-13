"""Token Optimization - Context management to minimize token usage per LLM call.

Context layers (in order):
  1. system prompt
  2. task description
  3. project memory
  4. retrieved files (via vector search)

Optimization strategies:
  - iteration summaries instead of full history
  - context trimming (max token budget)
  - code chunking (only relevant sections)
"""



class TokenOptimizer:
    """Build optimized context for LLM calls within a token budget."""

    DEFAULT_BUDGET = 16000  # tokens (conservative estimate for 32k context models)

    def __init__(self, max_tokens: int = DEFAULT_BUDGET):
        self.max_tokens = max_tokens

    def build_context(
        self,
        system_prompt: str,
        task: str,
        project_memory: str = "",
        retrieved_files: list = None,
        iteration_summaries: list = None,
    ) -> str:
        """Assemble optimized context within token budget."""
        retrieved_files = retrieved_files or []
        iteration_summaries = iteration_summaries or []

        parts = []
        budget = self.max_tokens

        # Layer 1: system prompt (always included)
        parts.append(system_prompt)
        budget -= self._estimate_tokens(system_prompt)

        # Layer 2: task (always included)
        parts.append(f"\n## Task\n{task}")
        budget -= self._estimate_tokens(task)

        # Layer 3: project memory (trimmed if needed)
        if project_memory and budget > 500:
            trimmed = self._trim_to_budget(project_memory, min(budget // 3, 4000))
            parts.append(f"\n## Project Context\n{trimmed}")
            budget -= self._estimate_tokens(trimmed)

        # Layer 3.5: iteration summaries (most recent first, instead of full history)
        if iteration_summaries and budget > 300:
            summary_text = self._build_summaries(iteration_summaries, min(budget // 4, 2000))
            if summary_text:
                parts.append(f"\n## Previous Iterations\n{summary_text}")
                budget -= self._estimate_tokens(summary_text)

        # Layer 4: retrieved files (most relevant first)
        if retrieved_files and budget > 200:
            files_text = self._build_file_context(retrieved_files, budget)
            if files_text:
                parts.append(f"\n## Relevant Code\n{files_text}")

        return "\n".join(parts)

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimate: ~4 chars per token for English, ~2 for CJK."""
        return len(text) // 3

    def _trim_to_budget(self, text: str, max_tokens: int) -> str:
        """Trim text to fit within token budget."""
        max_chars = max_tokens * 3
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "\n... (trimmed)"

    def _build_summaries(self, summaries: list, max_tokens: int) -> str:
        """Build iteration summaries, most recent first."""
        result = []
        budget = max_tokens
        for summary in reversed(summaries):
            text = f"- Iteration {summary.get('iteration', '?')}: {summary.get('summary', '')}"
            tokens = self._estimate_tokens(text)
            if budget - tokens < 0:
                break
            result.append(text)
            budget -= tokens
        return "\n".join(result)

    def _build_file_context(self, files: list, max_tokens: int) -> str:
        """Build file context from retrieved code chunks."""
        result = []
        budget = max_tokens
        for f in files:
            filename = f.get("file", "unknown")
            content = f.get("content", "")
            chunk = f"### {filename}\n```\n{content}\n```"
            tokens = self._estimate_tokens(chunk)
            if budget - tokens < 0:
                break
            result.append(chunk)
            budget -= tokens
        return "\n".join(result)
