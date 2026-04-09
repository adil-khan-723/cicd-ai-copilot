"""
Anthropic provider (Claude) — Phase 5.

Analysis tasks  → claude-haiku-4-5-20251001  (fast, cheap)
Generation tasks → claude-sonnet-4-6          (quality critical)
"""
import logging
import anthropic as anthropic_sdk
from providers.base import BaseLLMProvider
from config import get_settings

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):

    def __init__(self, model: str | None = None):
        self._settings = get_settings()
        self._model = model or self._settings.anthropic_analysis_model
        self._client: anthropic_sdk.Anthropic | None = None

    @property
    def name(self) -> str:
        return f"anthropic/{self._model}"

    def _get_client(self) -> anthropic_sdk.Anthropic:
        if self._client is None:
            self._client = anthropic_sdk.Anthropic(api_key=self._settings.anthropic_api_key)
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

    def is_available(self) -> bool:
        if not self._settings.anthropic_api_key:
            return False
        try:
            client = self._get_client()
            # Lightweight check: list models (cheap, no tokens used)
            client.models.list()
            return True
        except Exception:
            return False
