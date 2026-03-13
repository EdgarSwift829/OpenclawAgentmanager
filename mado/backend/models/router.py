"""Router - Route inference requests to the appropriate LLM backend.

Supported providers:
- lmstudio  (primary) - OpenAI-compatible API on localhost:1234
- ollama    (alternative) - Ollama API on localhost:11434
- vllm      - OpenAI-compatible API on localhost:8000

Enhanced with:
- Retry with exponential backoff
- Fallback model support
- Configurable timeout
- Call metrics tracking
"""

import json
import logging
import time
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0  # seconds
DEFAULT_TIMEOUT = 120  # seconds


# ── Metrics tracking ──

class LLMMetrics:
    """Track LLM call metrics for monitoring and debugging."""

    def __init__(self):
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.total_retries = 0
        self.fallback_calls = 0
        self.total_latency_ms = 0.0
        self._call_history: list[dict] = []
        self._max_history = 100

    def record_call(self, provider: str, model: str, latency_ms: float, success: bool, retries: int = 0):
        self.total_calls += 1
        self.total_latency_ms += latency_ms
        self.total_retries += retries
        if success:
            self.successful_calls += 1
        else:
            self.failed_calls += 1

        entry = {
            "provider": provider, "model": model,
            "latency_ms": round(latency_ms, 1),
            "success": success, "retries": retries,
            "timestamp": time.time(),
        }
        self._call_history.append(entry)
        if len(self._call_history) > self._max_history:
            self._call_history = self._call_history[-self._max_history:]

    def record_fallback(self):
        self.fallback_calls += 1

    @property
    def avg_latency_ms(self) -> float:
        if self.successful_calls == 0:
            return 0.0
        return self.total_latency_ms / self.successful_calls

    def to_dict(self) -> dict:
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "total_retries": self.total_retries,
            "fallback_calls": self.fallback_calls,
            "avg_latency_ms": round(self.avg_latency_ms, 1),
        }


# Global metrics instance
metrics = LLMMetrics()


def route_inference(
    model: dict,
    prompt: str,
    system_prompt: Optional[str] = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """Route an inference request with retry and fallback support.

    Args:
        model: Model config dict with name, provider, and optional fallback.
        prompt: The prompt to send.
        system_prompt: Optional system prompt.
        max_retries: Max retry attempts with exponential backoff.
        timeout: Request timeout in seconds.
    """
    from mado.backend.models.cache import llm_cache

    provider = model.get("provider", "lmstudio")
    model_name = model.get("name", "qwen3.5-9b")
    fallback_model = model.get("fallback")

    # Check cache first
    cached = llm_cache.get(model_name, prompt, system_prompt)
    if cached is not None:
        logger.debug(f"Cache hit for model={model_name}")
        return cached

    # Try primary model with retries
    start_time = time.time()
    result, retries_used = _call_with_retry(provider, model_name, prompt, system_prompt, max_retries, timeout)
    elapsed_ms = (time.time() - start_time) * 1000

    if not result.startswith("[LLM Error]"):
        metrics.record_call(provider, model_name, elapsed_ms, success=True, retries=retries_used)
        llm_cache.put(model_name, prompt, result, system_prompt)
        return result

    metrics.record_call(provider, model_name, elapsed_ms, success=False, retries=retries_used)

    # Try fallback model if configured
    if fallback_model:
        fallback_name = fallback_model.get("name", model_name)
        fallback_provider = fallback_model.get("provider", provider)
        logger.warning(f"Primary model {model_name} failed, trying fallback {fallback_name}")
        metrics.record_fallback()
        fb_start = time.time()
        fallback_result, fb_retries = _call_with_retry(
            fallback_provider, fallback_name, prompt, system_prompt, max_retries, timeout,
        )
        fb_elapsed = (time.time() - fb_start) * 1000
        fb_success = not fallback_result.startswith("[LLM Error]")
        metrics.record_call(fallback_provider, fallback_name, fb_elapsed, success=fb_success, retries=fb_retries)
        return fallback_result

    return result


def _call_with_retry(
    provider: str,
    model_name: str,
    prompt: str,
    system_prompt: Optional[str],
    max_retries: int,
    timeout: int,
) -> tuple[str, int]:
    """Call LLM with exponential backoff retry.

    Returns (result_text, retries_used).
    """
    last_error = None
    for attempt in range(max_retries):
        try:
            if provider == "lmstudio":
                return _call_lmstudio(model_name, prompt, system_prompt, timeout), attempt
            elif provider == "ollama":
                return _call_ollama(model_name, prompt, system_prompt, timeout), attempt
            elif provider == "vllm":
                return _call_vllm(model_name, prompt, system_prompt, timeout), attempt
            else:
                return f"[LLM Error] Unknown provider: {provider}", 0
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                delay = DEFAULT_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    f"LLM call failed (attempt {attempt + 1}/{max_retries}), "
                    f"retrying in {delay}s: {e}"
                )
                time.sleep(delay)

    return f"[LLM Error] All {max_retries} attempts failed: {last_error}", max_retries


def _call_lmstudio(
    model_name: str, prompt: str, system_prompt: Optional[str], timeout: int,
) -> str:
    """Call LM Studio OpenAI-compatible Chat API (localhost:1234)."""
    url = "http://localhost:1234/v1/chat/completions"
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model_name,
        "messages": messages,
        "stream": False,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        return result.get("choices", [{}])[0].get("message", {}).get("content", "")


def _call_ollama(
    model_name: str, prompt: str, system_prompt: Optional[str], timeout: int,
) -> str:
    """Call Ollama API."""
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
    }
    if system_prompt:
        payload["system"] = system_prompt

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        return result.get("response", "")


def _call_vllm(
    model_name: str, prompt: str, system_prompt: Optional[str], timeout: int,
) -> str:
    """Call vLLM OpenAI-compatible API."""
    url = "http://localhost:8000/v1/completions"
    payload = {
        "model": model_name,
        "prompt": f"{system_prompt}\n\n{prompt}" if system_prompt else prompt,
        "max_tokens": 4096,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        return result.get("choices", [{}])[0].get("text", "")
