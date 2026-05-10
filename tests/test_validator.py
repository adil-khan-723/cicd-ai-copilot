import pytest
from unittest.mock import MagicMock


def _make_settings(provider: str, api_key: str) -> MagicMock:
    s = MagicMock()
    s.llm_provider = provider
    s.anthropic_api_key = api_key
    return s


class TestValidateConfig:
    def test_anthropic_provider_missing_key_warns_does_not_raise(self, caplog):
        """Server must boot even without key — user configures via Settings UI."""
        import logging
        from config.validator import validate_config
        settings = _make_settings("anthropic", "")
        with caplog.at_level(logging.WARNING, logger="config.validator"):
            validate_config(settings)  # MUST NOT raise
        assert any("ANTHROPIC_API_KEY not set" in r.message for r in caplog.records)
        assert any("Settings" in r.message for r in caplog.records)

    def test_anthropic_provider_with_key_passes(self, caplog):
        import logging
        from config.validator import validate_config
        settings = _make_settings("anthropic", "sk-ant-abc123")
        with caplog.at_level(logging.WARNING, logger="config.validator"):
            validate_config(settings)
        assert not any("ANTHROPIC_API_KEY" in r.message for r in caplog.records)

    def test_ollama_provider_no_key_needed(self, caplog):
        import logging
        from config.validator import validate_config
        settings = _make_settings("ollama", "")
        with caplog.at_level(logging.WARNING, logger="config.validator"):
            validate_config(settings)
        assert not any("ANTHROPIC_API_KEY" in r.message for r in caplog.records)

