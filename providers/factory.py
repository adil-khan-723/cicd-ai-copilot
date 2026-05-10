"""
LLM provider factory with fallback chain (Increment 20).

Fallback order (configured via .env):
  1. LLM_PROVIDER (primary)
  2. LLM_FALLBACK_PROVIDER (secondary, if primary unavailable)
  3. All fail → raise ProviderUnavailableError
"""
import logging
from providers.base import BaseLLMProvider
from config import get_settings

logger = logging.getLogger(__name__)

# Task types and which model setting they use
_GENERATION_TASKS = {"generation", "generate", "generate_jenkinsfile", "generate_workflow"}
_ANALYSIS_TASKS = {"analysis", "analyze", "analyze_logs", "summarize"}


class ProviderUnavailableError(RuntimeError):
    """Raised when all providers in the fallback chain are unavailable."""


def get_provider(
    task: str = "analysis",
    provider_override: str = "",
    model_override: str = "",
) -> BaseLLMProvider:
    """
    Return the configured LLM provider for the given task.

    Default behaviour: try LLM_PROVIDER then LLM_FALLBACK_PROVIDER.
    Task type determines which model is selected:
      - analysis tasks   → settings.analysis_model
      - generation tasks → settings.generation_model

    Overrides (set both for per-call routing — used by Re-analyze UI):
      - provider_override: skip fallback chain, use this provider only
      - model_override: pass this model to the provider instead of the
        task-default. Empty string falls back to task-default.
    """
    settings = get_settings()
    is_generation = task.lower() in _GENERATION_TASKS

    # Override path: build directly, no fallback chain
    if provider_override:
        provider = _build_provider(
            provider_override.lower(), is_generation, settings,
            model_override=model_override,
        )
        if not provider.is_available():
            raise ProviderUnavailableError(
                f"Override provider '{provider_override}' is not available"
            )
        return provider

    primary = settings.llm_provider.lower()
    fallback = settings.llm_fallback_provider.lower()

    # Build ordered list of providers to try: [primary, fallback] (deduplicated)
    chain = [primary]
    if fallback and fallback != primary:
        chain.append(fallback)

    for provider_name in chain:
        try:
            provider = _build_provider(provider_name, is_generation, settings)
        except NotImplementedError:
            logger.warning("Provider '%s' not yet implemented — skipping", provider_name)
            continue

        if provider.is_available():
            if provider_name != primary:
                logger.warning(
                    "Primary provider '%s' unavailable — using fallback '%s'",
                    primary,
                    provider_name,
                )
            return provider
        else:
            logger.warning("Provider '%s' is not available", provider_name)

    raise ProviderUnavailableError(
        f"All LLM providers unavailable (tried: {chain}). "
        "Check Ollama is running or configure a cloud provider."
    )


def _build_provider(
    provider_name: str,
    is_generation: bool,
    settings,
    model_override: str = "",
) -> BaseLLMProvider:
    """Construct the provider instance for the given name. model_override wins when set."""
    if provider_name == "ollama":
        from providers.ollama_provider import OllamaProvider
        model = model_override or (
            settings.generation_model if is_generation else settings.analysis_model
        )
        return OllamaProvider(model=model)

    if provider_name == "anthropic":
        from providers.anthropic_provider import AnthropicProvider
        model = model_override or (
            settings.anthropic_generation_model if is_generation
            else settings.anthropic_analysis_model
        )
        return AnthropicProvider(model=model)

    raise ValueError(
        f"Unknown LLM provider '{provider_name}'. "
        "Valid options: ollama | anthropic"
    )
