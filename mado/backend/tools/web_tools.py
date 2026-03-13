"""Web Tools - search_web (SearXNG), fetch_url, extract_text.

Web access can be disabled per-project or globally:
  - Environment variable: MADO_WEB_ACCESS=false
  - Project config: {"web_access": false}
"""

import json
import logging
import os
import re
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

SEARXNG_URL = "http://localhost:8888"


def is_web_access_enabled() -> bool:
    """Check if web access is globally enabled."""
    return os.environ.get("MADO_WEB_ACCESS", "true").lower() not in ("false", "0", "no")


class WebTools:
    """Web research tools for agents. Uses local SearXNG for search.

    Web access can be disabled via MADO_WEB_ACCESS=false env var
    or per-project via project config {"web_access": false}.
    """

    def __init__(self, searxng_url: str = SEARXNG_URL, web_access: bool = True):
        self.searxng_url = searxng_url.rstrip("/")
        self._web_access = web_access and is_web_access_enabled()

    def search_web(self, query: str, max_results: int = 5, categories: str = "general") -> list:
        """Search the web via local SearXNG instance."""
        if not self._web_access:
            return [{"error": "Web access is disabled", "note": "Enable via MADO_WEB_ACCESS=true or project config"}]
        params = urllib.parse.urlencode({
            "q": query,
            "format": "json",
            "categories": categories,
            "pageno": 1,
        })
        url = f"{self.searxng_url}/search?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "MADO/1.0"})

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                results = []
                for item in data.get("results", [])[:max_results]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "content": item.get("content", ""),
                        "engine": item.get("engine", ""),
                    })
                return results
        except Exception as e:
            return [{"error": str(e), "note": "SearXNG may not be running at " + self.searxng_url}]

    def fetch_url(self, url: str, timeout: int = 10) -> str:
        """Fetch content from a URL."""
        if not self._web_access:
            raise PermissionError("Web access is disabled")
        req = urllib.request.Request(url, headers={"User-Agent": "MADO/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def extract_text(self, html: str) -> str:
        """Extract plain text from HTML content."""
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
