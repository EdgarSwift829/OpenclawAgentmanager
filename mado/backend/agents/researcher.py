"""Researcher Agent - Web search, documentation lookup, summarize findings.

The Researcher:
- Uses WebTools to search for relevant information
- Reads existing project files for context
- Provides structured research findings to other agents
"""

import logging
from mado.backend.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ResearcherAgent(BaseAgent):
    """Researcher: web search, documentation lookup, summarize findings with tools."""

    def execute(self, task: dict) -> dict:
        """Execute a research task using web search and file analysis."""
        description = task.get("description", "")

        # Search the web for relevant info
        web_results = self.search_web(description[:100])
        web_context = ""
        if web_results and not any(r.get("error") for r in web_results):
            web_context = "\n".join(
                f"- [{r.get('title', '')}]({r.get('url', '')}): {r.get('content', '')[:200]}"
                for r in web_results[:5]
            )

        # Search existing codebase
        code_results = self.search_code(description.split()[0] if description.split() else "")
        code_context = ""
        if code_results:
            code_context = "\n".join(
                f"- {r['file']}:{r['line']}: {r['content']}"
                for r in code_results[:10]
            )

        prompt = (
            f"You are a researcher. Investigate the following topic.\n\n"
            f"## Research Task\n{description}\n\n"
        )

        if web_context:
            prompt += f"## Web Search Results\n{web_context}\n\n"
        if code_context:
            prompt += f"## Existing Code References\n{code_context}\n\n"

        prompt += (
            f"Return JSON:\n"
            f"```json\n"
            f'{{\n'
            f'  "findings": ["key finding 1", "key finding 2"],\n'
            f'  "recommendations": ["recommendation 1"],\n'
            f'  "references": [{{"title": "...", "url": "...", "relevance": "high|medium|low"}}],\n'
            f'  "summary": "Brief summary of research"\n'
            f'}}\n'
            f"```"
        )

        result = self.call_llm_json(prompt, fallback={
            "findings": [description],
            "recommendations": [],
            "references": [],
            "summary": f"Research on: {description[:100]}",
        })

        summary = result.get("summary", "") if isinstance(result, dict) else str(result)[:200]
        return self.make_result(result=result, summary=f"Research: {summary[:100]}")
