"""Router - Route inference requests to the appropriate LLM backend (Ollama / vLLM)."""

import json
import urllib.request
from typing import Optional


def route_inference(model: dict, prompt: str, system_prompt: Optional[str] = None) -> str:
    """Route an inference request to Ollama or vLLM based on model provider."""
    provider = model.get("provider", "ollama")
    model_name = model.get("name", "qwen3.5-9b")

    if provider == "ollama":
        return _call_ollama(model_name, prompt, system_prompt)
    elif provider == "vllm":
        return _call_vllm(model_name, prompt, system_prompt)
    else:
        raise ValueError(f"Unknown provider: {provider}")


def _call_ollama(model_name: str, prompt: str, system_prompt: Optional[str] = None) -> str:
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
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("response", "")
    except Exception as e:
        return f"[LLM Error] {e}"


def _call_vllm(model_name: str, prompt: str, system_prompt: Optional[str] = None) -> str:
    """Call vLLM OpenAI-compatible API."""
    url = "http://localhost:8000/v1/completions"
    payload = {
        "model": model_name,
        "prompt": f"{system_prompt}\n\n{prompt}" if system_prompt else prompt,
        "max_tokens": 4096,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("choices", [{}])[0].get("text", "")
    except Exception as e:
        return f"[LLM Error] {e}"
