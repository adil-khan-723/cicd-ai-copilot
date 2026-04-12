from abc import ABC, abstractmethod
from typing import Generator


class BaseLLMProvider(ABC):
    """Abstract base for all LLM providers. Implement this to add a new provider."""

    @abstractmethod
    def complete(self, prompt: str, system: str = "") -> str:
        """Send a prompt and return the text response."""

    def stream_complete(self, prompt: str, system: str = "") -> Generator[str, None, None]:
        """
        Stream the response token-by-token (or chunk-by-chunk).
        Default implementation calls complete() and yields the full response at once.
        Override in providers that support native streaming (e.g. Ollama, Anthropic).
        """
        yield self.complete(prompt, system)

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the provider is reachable and configured."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name for logging."""
