"""Web Tools - search_web, fetch_url, extract_text."""

import urllib.request
import json
from typing import Optional


class WebTools:
    """Web research tools for agents."""

    def search_web(self, query: str, max_results: int = 5) -> list:
        """Search the web for a query. Placeholder for actual search API integration."""
        # TODO: Integrate with a search API (DuckDuckGo, SearXNG, etc.)
        return [{"query": query, "note": "Search API not configured. Integrate SearXNG or similar."}]

    def fetch_url(self, url: str, timeout: int = 10) -> str:
        """Fetch content from a URL."""
        req = urllib.request.Request(url, headers={"User-Agent": "MADO/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def extract_text(self, html: str) -> str:
        """Extract plain text from HTML content."""
        import re
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
