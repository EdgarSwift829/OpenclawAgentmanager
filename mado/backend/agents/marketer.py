"""Marketer Agent - Marketing strategy, SNS management, sales promotion.

The Marketer:
- Researches market via WebTools
- Creates marketing content and strategies
- Generates promotional materials
"""

import logging

from mado.backend.agents.base_agent import BaseAgent
from mado.backend.safety.prompt_sanitizer import sanitize_description

logger = logging.getLogger(__name__)


class MarketerAgent(BaseAgent):
    """Marketer: marketing strategy, content creation, market research."""

    def execute(self, task: dict) -> dict:
        """Execute a marketing task."""
        description = task.get("description", "")

        # Market research via web
        web_results = self.search_web(f"market trends {description[:50]}")
        web_context = ""
        if web_results and not any(r.get("error") for r in web_results):
            web_context = "\n".join(
                f"- {r.get('title', '')}: {r.get('content', '')[:200]}"
                for r in web_results[:5]
            )

        shared_ctx = self.build_shared_context()

        safe_desc = sanitize_description(description)
        prompt = (
            f"You are a marketing specialist. Execute this task.\n\n"
            f"## Task\n{safe_desc}\n\n"
        )

        if web_context:
            prompt += f"## Market Research\n{web_context}\n\n"
        if shared_ctx:
            prompt += f"{shared_ctx}\n\n"

        prompt += (
            f"Return JSON:\n"
            f"```json\n"
            f'{{\n'
            f'  "strategy": "Marketing approach",\n'
            f'  "content": [{{"type": "blog|social|email|landing", "title": "...", "body": "..."}}],\n'
            f'  "target_audience": "Description",\n'
            f'  "channels": ["channel1", "channel2"],\n'
            f'  "summary": "What was created"\n'
            f'}}\n'
            f"```"
        )

        result = self.call_llm_json(prompt, fallback={
            "strategy": description,
            "content": [],
            "target_audience": "",
            "channels": [],
            "summary": description[:200],
        })

        # Write marketing content to files
        files_written = []
        if isinstance(result, dict):
            for i, content in enumerate(result.get("content", [])):
                if isinstance(content, dict) and content.get("body"):
                    ctype = content.get("type", "content")
                    title = content.get("title", f"content_{i}")
                    safe_title = "".join(c for c in title if c.isalnum() or c in "-_ ").strip()[:50]
                    path = f"marketing/{ctype}_{safe_title}.md"
                    self.write_file(path, f"# {title}\n\n{content['body']}")
                    files_written.append(path)

        summary = result.get("summary", "") if isinstance(result, dict) else str(result)[:200]
        return self.make_result(
            result=result,
            files_modified=files_written,
            summary=f"Marketing: {summary[:100]}",
        )
