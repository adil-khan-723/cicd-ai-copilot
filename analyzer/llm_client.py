"""
LLM Analyzer client (Increment 15).

Orchestrates: cache check → build prompt → call provider → parse response → cache result.
"""
import logging

from providers import get_provider
from providers.factory import ProviderUnavailableError
from analyzer import cache as analysis_cache
from analyzer.prompt_builder import build_system_prompt, build_user_prompt
from analyzer.response_parser import parse_analysis_response

logger = logging.getLogger(__name__)

_PROVIDER_UNAVAILABLE = {
    "root_cause": "No LLM provider is available.",
    "fix_suggestion": (
        "Start Ollama (`ollama serve`) or set ANTHROPIC_API_KEY in .env."
    ),
    "confidence": 0.0,
    "fix_type": "diagnostic_only",
}


def analyze(
    context: str,
    provider_override: str = "",
    model_override: str = "",
) -> dict:
    """
    Analyze a pipeline failure context string using the configured LLM provider.

    Args:
        context: Output from context_builder.build_context()
        provider_override: 'anthropic' / 'ollama' to bypass default + fallback chain
        model_override: specific model id; both override args bypass cache

    Returns:
        Dict with keys: root_cause, fix_suggestion, confidence, fix_type, model_used, provider_used
    """
    using_override = bool(provider_override or model_override)

    # Cache check — only when no override (overrides force a fresh call)
    if not using_override:
        cached = analysis_cache.get(context)
        if cached is not None:
            return cached

    try:
        provider = get_provider(
            "analysis",
            provider_override=provider_override,
            model_override=model_override,
        )
    except ProviderUnavailableError as e:
        logger.error("All LLM providers unavailable: %s", e)
        return dict(_PROVIDER_UNAVAILABLE)

    system = build_system_prompt()
    user = build_user_prompt(context)

    try:
        raw = provider.complete(user, system=system)
    except Exception as e:
        logger.error("LLM provider '%s' failed: %s", provider.name, e)
        return {
            "root_cause": f"LLM provider error ({provider.name}): {e}",
            "fix_suggestion": "Check provider config or switch LLM_PROVIDER in .env.",
            "confidence": 0.0,
            "fix_type": "diagnostic_only",
        }

    result = parse_analysis_response(raw)
    # Stamp which model + provider produced this result so the UI can show + offer re-run
    result["provider_used"] = provider.name
    result["model_used"] = getattr(provider, "_model", "")

    # Only cache the default-routed result. Overrides are one-shot.
    if not using_override:
        analysis_cache.set(context, result)

    return result
