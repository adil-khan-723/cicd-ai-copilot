"""
LLM Analyzer client (Increment 15).

Orchestrates: cache check → build prompt → call provider → parse response → cache result.
"""
import logging

from providers import get_provider
from analyzer import cache as analysis_cache
from analyzer.prompt_builder import build_system_prompt, build_user_prompt
from analyzer.response_parser import parse_analysis_response

logger = logging.getLogger(__name__)


def analyze(context: str) -> dict:
    """
    Analyze a pipeline failure context string using the configured LLM provider.

    Args:
        context: Output from context_builder.build_context()

    Returns:
        Dict with keys: root_cause, fix_suggestion, confidence, fix_type
    """
    # Cache check
    cached = analysis_cache.get(context)
    if cached is not None:
        return cached

    provider = get_provider("analysis")

    system = build_system_prompt()
    user = build_user_prompt(context)

    try:
        raw = provider.complete(user, system=system)
    except Exception as e:
        logger.error("LLM provider '%s' failed: %s", provider.name, e)
        return {
            "root_cause": f"LLM provider unavailable: {provider.name}",
            "fix_suggestion": "Manual review required.",
            "confidence": 0.0,
            "fix_type": "diagnostic_only",
        }

    result = parse_analysis_response(raw)

    # Cache the parsed result
    analysis_cache.set(context, result)

    return result
