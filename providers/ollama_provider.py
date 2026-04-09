import httpx
from providers.base import BaseLLMProvider
from config import get_settings


class OllamaProvider(BaseLLMProvider):

    def __init__(self, model: str | None = None):
        self._settings = get_settings()
        self._model = model or self._settings.analysis_model
        self._base_url = self._settings.ollama_base_url
        self._timeout = self._settings.ollama_timeout

    @property
    def name(self) -> str:
        return f"ollama/{self._model}"

    def complete(self, prompt: str, system: str = "") -> str:
        payload = {
            "model": self._model,
            "prompt": prompt,
            "system": system,
            "stream": False,
        }
        try:
            response = httpx.post(
                f"{self._base_url}/api/generate",
                json=payload,
                timeout=self._timeout,
            )
            response.raise_for_status()
            return response.json()["response"]
        except httpx.ConnectError:
            raise RuntimeError(
                f"Cannot reach Ollama at {self._base_url}. "
                "Is Ollama running? Try: ollama serve"
            )
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Ollama returned {e.response.status_code}: {e.response.text}")

    def is_available(self) -> bool:
        try:
            response = httpx.get(f"{self._base_url}/api/tags", timeout=5)
            if response.status_code != 200:
                return False
            models = [m["name"] for m in response.json().get("models", [])]
            # Accept model names with or without tag suffix (e.g. "llama3.1:8b" or "llama3.1")
            model_base = self._model.split(":")[0]
            return any(model_base in m for m in models)
        except Exception:
            return False
