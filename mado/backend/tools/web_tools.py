"""Web Tools - search_web (SearXNG), fetch_url, extract_text."""

import urllib.request
import json
import re
from typing import Optional


SEARXNG_URL = "http://localhost:8888"


class WebTools:
    """Web research tools for agents. Uses local SearXNG for search."""

    def __init__(self, searxng_url: str = SEARXNG_URL):
        self.searxng_url = searxng_url.rstrip("/")

    def search_web(self, query: str, max_results: int = 5, categories: str = "general") -> list:
        """Search the web via local SearXNG instance."""
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
