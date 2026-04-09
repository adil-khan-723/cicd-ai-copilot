from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    """Abstract base for all LLM providers. Implement this to add a new provider."""

    @abstractmethod
    def complete(self, prompt: str, system: str = "") -> str:
        """Send a prompt and return the text response."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the provider is reachable and configured."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name for logging."""
