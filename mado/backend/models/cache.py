"""LLM Response Cache - In-memory cache for LLM responses to avoid redundant calls.

Features:
- Hash-based key from (model, prompt, system_prompt)
- TTL-based expiration (default 10 minutes)
- Max size limit with LRU eviction
- Thread-safe
- Can be disabled via MADO_LLM_CACHE_ENABLED=false
"""

import hashlib
import os
import threading
import time
from collections import OrderedDict
from typing import Optional


class LLMCache:
    """Thread-safe in-memory LRU cache for LLM responses."""

    def __init__(self, max_size: int = 200, ttl_seconds: int = 600):
        self._cache: OrderedDict[str, tuple[str, float]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._enabled = os.environ.get("MADO_LLM_CACHE_ENABLED", "true").lower() != "false"

    @staticmethod
    def _make_key(model_name: str, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Create a deterministic cache key from inputs."""
        parts = f"{model_name}||{system_prompt or ''}||{prompt}"
        return hashlib.sha256(parts.encode("utf-8")).hexdigest()

    def get(self, model_name: str, prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
        """Get cached response. Returns None on miss or expired entry."""
        if not self._enabled:
            return None

        key = self._make_key(model_name, prompt, system_prompt)
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            response, timestamp = self._cache[key]
            if time.time() - timestamp > self._ttl:
                # Expired
                del self._cache[key]
                self._misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            return response

    def put(self, model_name: str, prompt: str, response: str, system_prompt: Optional[str] = None) -> None:
        """Cache a response."""
        if not self._enabled:
            return
        # Don't cache error responses
        if response.startswith("[LLM Error]"):
            return

        key = self._make_key(model_name, prompt, system_prompt)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = (response, time.time())

            # Evict oldest if over limit
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "enabled": self._enabled,
            "size": self.size,
            "max_size": self._max_size,
            "ttl_seconds": self._ttl,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self.hit_rate, 3),
        }


# Global cache instance
llm_cache = LLMCache()
