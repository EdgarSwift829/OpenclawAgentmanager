"""Router - Route inference requests to the appropriate LLM backend.

Supported providers:
- lmstudio  (primary) - OpenAI-compatible API on localhost:1234
- ollama    (alternative) - Ollama API on localhost:11434
- vllm      - OpenAI-compatible API on localhost:8000

Enhanced with:
- Retry with exponential backoff
- Fallback model support
- Configurable timeout
"""

import json
import time
import logging
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0  # seconds
DEFAULT_TIMEOUT = 120  # seconds


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
    provider = model.get("provider", "lmstudio")
    model_name = model.get("name", "qwen3.5-9b")
    fallback_model = model.get("fallback")

    # Try primary model with retries
    result = _call_with_retry(provider, model_name, prompt, system_prompt, max_retries, timeout)
    if not result.startswith("[LLM Error]"):
        return result

    # Try fallback model if configured
    if fallback_model:
        fallback_name = fallback_model.get("name", model_name)
        fallback_provider = fallback_model.get("provider", provider)
        logger.warning(f"Primary model {model_name} failed, trying fallback {fallback_name}")
        fallback_result = _call_with_retry(
            fallback_provider, fallback_name, prompt, system_prompt, max_retries, timeout,
        )
        return fallback_result

    return result


def _call_with_retry(
    provider: str,
    model_name: str,
    prompt: str,
    system_prompt: Optional[str],
    max_retries: int,
    timeout: int,
) -> str:
    """Call LLM with exponential backoff retry."""
    last_error = None
    for attempt in range(max_retries):
        try:
            if provider == "lmstudio":
                return _call_lmstudio(model_name, prompt, system_prompt, timeout)
            elif provider == "ollama":
                return _call_ollama(model_name, prompt, system_prompt, timeout)
            elif provider == "vllm":
                return _call_vllm(model_name, prompt, system_prompt, timeout)
            else:
                return f"[LLM Error] Unknown provider: {provider}"
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                delay = DEFAULT_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    f"LLM call failed (attempt {attempt + 1}/{max_retries}), "
                    f"retrying in {delay}s: {e}"
                )
                time.sleep(delay)

    return f"[LLM Error] All {max_retries} attempts failed: {last_error}"


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
