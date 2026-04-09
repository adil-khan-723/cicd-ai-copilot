"""
Gemini provider — Google AI Studio (free tier).
Uses the current google-genai SDK.
"""
import logging
from google import genai
from google.genai import types
from providers.base import BaseLLMProvider
from config import get_settings

logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):

    def __init__(self, model: str | None = None):
        self._settings = get_settings()
        self._model = model or self._settings.gemini_model
        self._client: genai.Client | None = None

    @property
    def name(self) -> str:
        return f"gemini/{self._model}"

    def _get_client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(api_key=self._settings.gemini_api_key)
        return self._client

    def complete(self, prompt: str, system: str = "") -> str:
        client = self._get_client()
        config = types.GenerateContentConfig(
            system_instruction=system if system else None,
            max_output_tokens=2048,
        )
        try:
            response = client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=config,
            )
            return response.text
        except Exception as e:
            raise RuntimeError(f"Gemini API error: {e}")

    def is_available(self) -> bool:
        if not self._settings.gemini_api_key:
            return False
        try:
            client = self._get_client()
            list(client.models.list())
            return True
        except Exception:
            return False
