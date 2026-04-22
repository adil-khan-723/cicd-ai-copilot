import pytest
from unittest.mock import MagicMock


def _make_settings(provider: str, api_key: str) -> MagicMock:
    s = MagicMock()
    s.llm_provider = provider
    s.anthropic_api_key = api_key
    return s


class TestValidateConfig:
    def test_anthropic_provider_missing_key_raises(self):
        from config.validator import validate_config
        settings = _make_settings("anthropic", "")
        with pytest.raises(SystemExit) as exc_info:
            validate_config(settings)
        assert "ANTHROPIC_API_KEY" in str(exc_info.value)
        assert "console.anthropic.com" in str(exc_info.value)

    def test_anthropic_provider_with_key_passes(self):
        from config.validator import validate_config
        settings = _make_settings("anthropic", "sk-ant-abc123")
        validate_config(settings)  # must not raise

    def test_ollama_provider_no_key_needed(self):
        from config.validator import validate_config
        settings = _make_settings("ollama", "")
        validate_config(settings)  # must not raise

