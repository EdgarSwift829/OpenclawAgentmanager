"""Tests for LLM Router and ModelManager."""

import json
from unittest.mock import MagicMock, patch

import pytest

from mado.backend.models.model_manager import ModelManager
from mado.backend.models.router import (
    DEFAULT_BASE_DELAY,
    _call_with_retry,
    route_inference,
)

# ============================================================
# Router
# ============================================================

class TestRouteInference:
    @patch("mado.backend.models.router._call_with_retry")
    def test_success_primary(self, mock_retry):
        mock_retry.return_value = "Generated text"
        result = route_inference(
            model={"name": "test-model", "provider": "ollama"},
            prompt="Hello",
        )
        assert result == "Generated text"
        mock_retry.assert_called_once()

    @patch("mado.backend.models.router._call_with_retry")
    def test_fallback_on_primary_failure(self, mock_retry):
        mock_retry.side_effect = [
            "[LLM Error] connection refused",  # primary fails
            "Fallback response",                # fallback succeeds
        ]
        result = route_inference(
            model={
                "name": "primary",
                "provider": "ollama",
                "fallback": {"name": "backup", "provider": "lmstudio"},
            },
            prompt="Hello",
        )
        assert result == "Fallback response"
        assert mock_retry.call_count == 2

    @patch("mado.backend.models.router._call_with_retry")
    def test_no_fallback_returns_error(self, mock_retry):
        mock_retry.return_value = "[LLM Error] failed"
        result = route_inference(
            model={"name": "test", "provider": "ollama"},
            prompt="Hello",
        )
        assert "[LLM Error]" in result

    def test_unknown_provider(self):
        result = _call_with_retry("unknown_provider", "model", "prompt", None, 1, 10)
        assert "[LLM Error]" in result
        assert "Unknown provider" in result


class TestCallWithRetry:
    @patch("mado.backend.models.router._call_ollama")
    def test_success_first_try(self, mock_ollama):
        mock_ollama.return_value = "response"
        result = _call_with_retry("ollama", "model", "prompt", None, 3, 60)
        assert result == "response"
        assert mock_ollama.call_count == 1

    @patch("mado.backend.models.router.time.sleep")
    @patch("mado.backend.models.router._call_ollama")
    def test_retry_on_exception(self, mock_ollama, mock_sleep):
        mock_ollama.side_effect = [
            ConnectionError("refused"),
            "success",
        ]
        result = _call_with_retry("ollama", "model", "prompt", None, 3, 60)
        assert result == "success"
        assert mock_ollama.call_count == 2
        mock_sleep.assert_called_once()

    @patch("mado.backend.models.router.time.sleep")
    @patch("mado.backend.models.router._call_ollama")
    def test_all_retries_exhausted(self, mock_ollama, mock_sleep):
        mock_ollama.side_effect = ConnectionError("refused")
        result = _call_with_retry("ollama", "model", "prompt", None, 3, 60)
        assert "[LLM Error]" in result
        assert "3 attempts failed" in result
        assert mock_ollama.call_count == 3

    @patch("mado.backend.models.router.time.sleep")
    @patch("mado.backend.models.router._call_ollama")
    def test_exponential_backoff_delays(self, mock_ollama, mock_sleep):
        mock_ollama.side_effect = ConnectionError("refused")
        _call_with_retry("ollama", "model", "prompt", None, 3, 60)
        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert delays == [DEFAULT_BASE_DELAY * 1, DEFAULT_BASE_DELAY * 2]


class TestProviderCalls:
    @patch("mado.backend.models.router.urllib.request.urlopen")
    def test_call_lmstudio_with_system_prompt(self, mock_urlopen):
        from mado.backend.models.router import _call_lmstudio
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "choices": [{"message": {"content": "reply"}}]
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = _call_lmstudio("model", "hello", "system prompt", 60)
        assert result == "reply"
        # Verify the request payload includes system message
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        payload = json.loads(req.data)
        assert len(payload["messages"]) == 2
        assert payload["messages"][0]["role"] == "system"

    @patch("mado.backend.models.router.urllib.request.urlopen")
    def test_call_ollama(self, mock_urlopen):
        from mado.backend.models.router import _call_ollama
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"response": "ollama reply"}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = _call_ollama("model", "prompt", None, 60)
        assert result == "ollama reply"

    @patch("mado.backend.models.router.urllib.request.urlopen")
    def test_call_vllm(self, mock_urlopen):
        from mado.backend.models.router import _call_vllm
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "choices": [{"text": "vllm reply"}]
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = _call_vllm("model", "prompt", "sys", 60)
        assert result == "vllm reply"


# ============================================================
# ModelManager
# ============================================================

class TestModelManager:
    def test_init_empty_config(self, tmp_path):
        mm = ModelManager(config_dir=str(tmp_path))
        assert mm.models == {}
        assert mm.agent_assignments == {}

    def test_load_from_yaml(self, tmp_path):
        models_yaml = tmp_path / "models.yaml"
        models_yaml.write_text(
            "models:\n  qwen:\n    provider: ollama\n    context: 8192\n",
            encoding="utf-8",
        )
        agents_yaml = tmp_path / "agents.yaml"
        agents_yaml.write_text("engineer: qwen\nreviewer: qwen\n", encoding="utf-8")

        mm = ModelManager(config_dir=str(tmp_path))
        assert "qwen" in mm.models
        assert mm.agent_assignments["engineer"] == "qwen"

    def test_get_model(self, tmp_path):
        models_yaml = tmp_path / "models.yaml"
        models_yaml.write_text(
            "models:\n  qwen:\n    provider: ollama\n", encoding="utf-8"
        )
        agents_yaml = tmp_path / "agents.yaml"
        agents_yaml.write_text("engineer: qwen\n", encoding="utf-8")

        mm = ModelManager(config_dir=str(tmp_path))
        model = mm.get_model("engineer")
        assert model["name"] == "qwen"
        assert model["provider"] == "ollama"

    def test_get_model_default(self, tmp_path):
        mm = ModelManager(config_dir=str(tmp_path))
        model = mm.get_model("unknown_role")
        assert model["name"] == "qwen3.5-9b"

    def test_register_model(self, tmp_path):
        mm = ModelManager(config_dir=str(tmp_path))
        mm.register_model("new-model", {"provider": "lmstudio", "context": 4096})
        assert "new-model" in mm.models

    def test_update_model(self, tmp_path):
        mm = ModelManager(config_dir=str(tmp_path))
        mm.register_model("model-a", {"provider": "ollama"})
        mm.update_model("engineer", "model-a")
        assert mm.agent_assignments["engineer"] == "model-a"

    def test_update_model_unregistered(self, tmp_path):
        mm = ModelManager(config_dir=str(tmp_path))
        with pytest.raises(ValueError, match="not registered"):
            mm.update_model("engineer", "nonexistent")

    def test_save_assignments(self, tmp_path):
        mm = ModelManager(config_dir=str(tmp_path))
        mm.register_model("test-model", {"provider": "ollama"})
        mm.update_model("engineer", "test-model")
        # Verify file was persisted
        agents_path = tmp_path / "agents.yaml"
        assert agents_path.exists()
        content = agents_path.read_text(encoding="utf-8")
        assert "engineer" in content
        assert "test-model" in content

    def test_list_models(self, tmp_path):
        mm = ModelManager(config_dir=str(tmp_path))
        mm.register_model("a", {"provider": "ollama"})
        mm.register_model("b", {"provider": "lmstudio"})
        models = mm.list_models()
        assert "a" in models
        assert "b" in models

    def test_reload_models(self, tmp_path):
        models_yaml = tmp_path / "models.yaml"
        models_yaml.write_text("models:\n  v1:\n    provider: ollama\n", encoding="utf-8")
        mm = ModelManager(config_dir=str(tmp_path))
        assert "v1" in mm.models

        # Update config on disk and reload
        models_yaml.write_text("models:\n  v2:\n    provider: lmstudio\n", encoding="utf-8")
        mm.reload_models()
        assert "v2" in mm.models
        assert "v1" not in mm.models
