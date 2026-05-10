"""
Anthropic provider (Claude) — Phase 5.

Analysis tasks  → claude-haiku-4-5-20251001  (fast, cheap)
Generation tasks → claude-sonnet-4-6          (quality critical)
"""
import logging
from typing import Generator
import anthropic as anthropic_sdk
from providers.base import BaseLLMProvider
from config import get_settings

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):

    def __init__(self, model: str | None = None):
        # Don't snapshot settings — re-read on every access so .env hot-reloads
        # (after Settings UI save) take effect without restarting the server.
        self._model_override = model
        self._client: anthropic_sdk.Anthropic | None = None
        self._client_key: str = ""  # track which key built the cached client

    @property
    def _settings(self):
        return get_settings()

    @property
    def _model(self) -> str:
        return self._model_override or self._settings.anthropic_analysis_model

    @property
    def name(self) -> str:
        return f"anthropic/{self._model}"

    def _get_client(self) -> anthropic_sdk.Anthropic:
        current_key = self._settings.anthropic_api_key
        # Rebuild client when key changes (e.g. after Settings UI save)
        if self._client is None or self._client_key != current_key:
            from copilot.secrets_manager import audit_secret_used
            audit_secret_used("system", "anthropic_api_key")
            self._client = anthropic_sdk.Anthropic(api_key=current_key)
            self._client_key = current_key
        return self._client

    def complete(self, prompt: str, system: str = "") -> str:
        client = self._get_client()
        kwargs = {
            "model": self._model,
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        try:
            response = client.messages.create(**kwargs)
            return response.content[0].text
        except anthropic_sdk.APIConnectionError as e:
            raise RuntimeError(f"Anthropic API connection error: {e}")
        except anthropic_sdk.AuthenticationError:
            raise RuntimeError("Anthropic API key is invalid or not set.")
        except anthropic_sdk.RateLimitError:
            raise RuntimeError("Anthropic rate limit exceeded — try again later.")
        except anthropic_sdk.APIStatusError as e:
            raise RuntimeError(f"Anthropic API error {e.status_code}: {e.message}")

    def stream_complete(self, prompt: str, system: str = "") -> Generator[str, None, None]:
        """Stream response tokens from Anthropic using the SDK's native streaming API."""
        client = self._get_client()
        kwargs: dict = {
            "model": self._model,
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        try:
            with client.messages.stream(**kwargs) as stream:
                for text in stream.text_stream:
                    yield text
        except anthropic_sdk.APIConnectionError as e:
            raise RuntimeError(f"Anthropic API connection error: {e}")
        except anthropic_sdk.AuthenticationError:
            raise RuntimeError("Anthropic API key is invalid or not set.")
        except anthropic_sdk.RateLimitError:
            raise RuntimeError("Anthropic rate limit exceeded — try again later.")
        except anthropic_sdk.APIStatusError as e:
            raise RuntimeError(f"Anthropic API error {e.status_code}: {e.message}")

    def is_available(self) -> bool:
        key = self._settings.anthropic_api_key
        if not key:
            logger.warning("Anthropic unavailable: ANTHROPIC_API_KEY not set in settings")
            return False
        try:
            client = self._get_client()
            client.models.list()
            return True
        except anthropic_sdk.AuthenticationError:
            logger.warning("Anthropic unavailable: AuthenticationError (key rejected by API)")
            return False
        except anthropic_sdk.APIConnectionError as e:
            logger.warning("Anthropic unavailable: connection error: %s", e)
            return False
        except Exception as e:
            logger.warning("Anthropic unavailable: %s: %s", type(e).__name__, e)
            return False
