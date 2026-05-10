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

def _active_key_name(provider_name: str) -> str:
    """Return the name of the active key in the LLM key manager for a provider,
    or empty string if no key registered. Provider names look like 'anthropic/claude-...'."""
    try:
        provider = provider_name.split("/", 1)[0].lower()
        from ui.llm_keys_store import get_active_key
        active = get_active_key(provider)
        return active.get("name", "") if active else ""
    except Exception:
        return ""


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
    # Stamp which named API key was used (multi-key manager). Empty for ollama or
    # when no key registered in the key manager (e.g. raw .env fallback).
    result["key_name"] = _active_key_name(provider.name)

    # Only cache the default-routed result. Overrides are one-shot.
    if not using_override:
        analysis_cache.set(context, result)

    return result
