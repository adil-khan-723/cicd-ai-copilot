"""
Groq provider — Llama 70B on Groq free tier.
Fast inference, great for analysis tasks.
"""
import logging
from groq import Groq, APIConnectionError, AuthenticationError, RateLimitError
from providers.base import BaseLLMProvider
from config import get_settings

logger = logging.getLogger(__name__)


class GroqProvider(BaseLLMProvider):

    def __init__(self, model: str | None = None):
        self._settings = get_settings()
        self._model = model or self._settings.groq_model
        self._client: Groq | None = None

    @property
    def name(self) -> str:
        return f"groq/{self._model}"

    def _get_client(self) -> Groq:
        if self._client is None:
            self._client = Groq(api_key=self._settings.groq_api_key)
        return self._client

    def complete(self, prompt: str, system: str = "") -> str:
        client = self._get_client()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=2048,
            )
            return response.choices[0].message.content
        except APIConnectionError as e:
            raise RuntimeError(f"Groq API connection error: {e}")
        except AuthenticationError:
            raise RuntimeError("Groq API key is invalid or not set.")
        except RateLimitError:
            raise RuntimeError("Groq rate limit exceeded — try again later.")
        except Exception as e:
            raise RuntimeError(f"Groq API error: {e}")

    def is_available(self) -> bool:
        if not self._settings.groq_api_key:
            return False
        try:
            client = self._get_client()
            client.models.list()
            return True
        except Exception:
            return False
