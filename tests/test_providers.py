"""
Multi-provider tests (Increment 32).

Tests the full provider abstraction layer:
  - Each provider builds correctly and routes models
  - Fallback chain works end-to-end
  - is_available() returns False when key is missing
  - complete() raises RuntimeError on API errors (not raw SDK exceptions)

All external API calls are mocked — no live tokens needed.
"""
import pytest
from unittest.mock import patch, MagicMock, PropertyMock

from providers.factory import get_provider, ProviderUnavailableError, _build_provider
from providers.ollama_provider import OllamaProvider
from providers.anthropic_provider import AnthropicProvider


# ---------------------------------------------------------------------------
# Ollama provider
# ---------------------------------------------------------------------------

class TestOllamaProvider:
    def test_name_includes_model(self):
        p = OllamaProvider(model="llama3.1:8b")
        assert "llama3.1:8b" in p.name

    def test_complete_returns_response(self):
        import respx, httpx
        with respx.mock:
            respx.post("http://localhost:11434/api/generate").mock(
                return_value=httpx.Response(200, json={"response": "Hello!"})
            )
            p = OllamaProvider(model="llama3.1:8b")
            result = p.complete("Say hello")
        assert result == "Hello!"

    def test_complete_raises_on_connect_error(self):
        import respx, httpx
        with respx.mock:
            respx.post("http://localhost:11434/api/generate").mock(
                side_effect=httpx.ConnectError("refused")
            )
            p = OllamaProvider(model="llama3.1:8b")
            with pytest.raises(RuntimeError, match="Cannot reach Ollama"):
                p.complete("hello")

    def test_is_available_true_when_model_present(self):
        import respx, httpx
        with respx.mock:
            respx.get("http://localhost:11434/api/tags").mock(
                return_value=httpx.Response(200, json={"models": [{"name": "llama3.1:8b"}]})
            )
            p = OllamaProvider(model="llama3.1:8b")
            assert p.is_available() is True

    def test_is_available_false_when_model_missing(self):
        import respx, httpx
        with respx.mock:
            respx.get("http://localhost:11434/api/tags").mock(
                return_value=httpx.Response(200, json={"models": []})
            )
            p = OllamaProvider(model="llama3.1:8b")
            assert p.is_available() is False


# ---------------------------------------------------------------------------
# Anthropic provider
# ---------------------------------------------------------------------------

class TestAnthropicProvider:
    def _make_provider(self, api_key="sk-ant-test"):
        with patch("providers.anthropic_provider.get_settings") as mock_settings:
            mock_settings.return_value.anthropic_api_key = api_key
            mock_settings.return_value.anthropic_analysis_model = "claude-haiku-4-5-20251001"
            mock_settings.return_value.anthropic_generation_model = "claude-sonnet-4-6"
            return AnthropicProvider(model="claude-haiku-4-5-20251001")

    def test_name_includes_model(self):
        p = self._make_provider()
        assert "claude-haiku" in p.name

    def test_complete_returns_text(self):
        p = self._make_provider()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Analysis result")]
        mock_client.messages.create.return_value = mock_response
        p._client = mock_client

        result = p.complete("Analyze this log", system="You are an expert")
        assert result == "Analysis result"
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == "You are an expert"

    def test_complete_raises_on_auth_error(self):
        import anthropic as sdk
        p = self._make_provider()
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = sdk.AuthenticationError(
            message="Invalid key", response=MagicMock(), body={}
        )
        p._client = mock_client
        with pytest.raises(RuntimeError, match="invalid"):
            p.complete("test")

    def test_is_available_false_when_no_key(self):
        p = self._make_provider(api_key="")
        assert p.is_available() is False

    def test_is_available_true_when_models_list_succeeds(self):
        p = self._make_provider(api_key="sk-ant-test")
        mock_client = MagicMock()
        mock_client.models.list.return_value = []
        p._client = mock_client
        assert p.is_available() is True

    def test_is_available_false_when_api_error(self):
        p = self._make_provider(api_key="sk-ant-test")
        mock_client = MagicMock()
        mock_client.models.list.side_effect = Exception("network error")
        p._client = mock_client
        assert p.is_available() is False

    def test_anthropic_stream_complete_yields_multiple_chunks(self):
        """stream_complete must yield multiple chunks, not one big blob."""
        p = self._make_provider()
        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_stream.text_stream = iter(["Hello", " world", "!"])

        mock_client = MagicMock()
        mock_client.messages.stream.return_value = mock_stream

        p._client = mock_client

        chunks = list(p.stream_complete("say hello"))

        assert len(chunks) > 1, f"Expected multiple chunks, got {len(chunks)}: {chunks}"
        assert "".join(chunks) == "Hello world!"
        mock_client.messages.stream.assert_called_once()


# ---------------------------------------------------------------------------
# Factory — provider routing tests
# ---------------------------------------------------------------------------

class TestFactory:
    def test_ollama_analysis_uses_analysis_model(self):
        with patch("providers.factory.get_settings") as mock_s:
            mock_s.return_value.llm_provider = "ollama"
            mock_s.return_value.llm_fallback_provider = ""
            mock_s.return_value.analysis_model = "llama3.1:8b"
            mock_s.return_value.generation_model = "qwen2.5-coder:14b"
            mock_s.return_value.ollama_base_url = "http://localhost:11434"
            mock_s.return_value.ollama_timeout = 30

            with patch("providers.ollama_provider.get_settings", mock_s):
                provider = _build_provider("ollama", False, mock_s.return_value)
            assert "llama3.1" in provider.name

    def test_ollama_generation_uses_generation_model(self):
        with patch("providers.factory.get_settings") as mock_s:
            mock_s.return_value.analysis_model = "llama3.1:8b"
            mock_s.return_value.generation_model = "qwen2.5-coder:14b"
            mock_s.return_value.ollama_base_url = "http://localhost:11434"
            mock_s.return_value.ollama_timeout = 30

            with patch("providers.ollama_provider.get_settings", mock_s):
                provider = _build_provider("ollama", True, mock_s.return_value)
            assert "qwen2.5-coder" in provider.name

    def test_anthropic_analysis_uses_haiku(self):
        with patch("providers.factory.get_settings") as mock_s:
            mock_s.return_value.anthropic_api_key = "sk-test"
            mock_s.return_value.anthropic_analysis_model = "claude-haiku-4-5-20251001"
            mock_s.return_value.anthropic_generation_model = "claude-sonnet-4-6"
            with patch("providers.anthropic_provider.get_settings", mock_s):
                provider = _build_provider("anthropic", False, mock_s.return_value)
            assert "haiku" in provider.name

    def test_anthropic_generation_uses_sonnet(self):
        with patch("providers.factory.get_settings") as mock_s:
            mock_s.return_value.anthropic_api_key = "sk-test"
            mock_s.return_value.anthropic_analysis_model = "claude-haiku-4-5-20251001"
            mock_s.return_value.anthropic_generation_model = "claude-sonnet-4-6"
            with patch("providers.anthropic_provider.get_settings", mock_s):
                provider = _build_provider("anthropic", True, mock_s.return_value)
            assert "sonnet" in provider.name

    def test_unknown_provider_raises_value_error(self):
        with patch("providers.factory.get_settings") as mock_s:
            mock_s.return_value.llm_provider = "unknown-llm"
            mock_s.return_value.llm_fallback_provider = ""
            with pytest.raises((ValueError, ProviderUnavailableError)):
                get_provider("analysis")

    def test_secrets_manager_no_secret_in_audit(self):
        """Verify secrets manager audit log never contains the secret value."""
        import tempfile, os, json
        from copilot.secrets_manager import audit_secret_used
        from agent import audit_log as audit_mod

        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False)
        tmp.close()
        try:
            with patch("agent.audit_log.get_settings") as mock_s:
                mock_s.return_value.audit_log_path = tmp.name
                audit_secret_used("U123", "MY_SECRET_KEY")

            with open(tmp.name) as f:
                entry = json.loads(f.readline())

            # The secret NAME appears in result field (e.g. "used:MY_SECRET_KEY") — that's OK
            # The secret VALUE must never appear
            assert "MY_SECRET_KEY" in entry["result"]  # name is fine
            # Ensure no field contains "sk-" or "xoxb-" style values
            for v in entry.values():
                assert not str(v).startswith("sk-")
                assert not str(v).startswith("xoxb-")
        finally:
            os.unlink(tmp.name)
