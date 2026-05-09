"""
Parse and validate LLM JSON responses for failure analysis.
"""
import json
import logging
import re

logger = logging.getLogger(__name__)

VALID_FIX_TYPES = {
    "retry", "clear_cache", "clear_npm_cache", "pull_image", "increase_timeout",
    "configure_tool", "configure_credential", "fix_step_typo", "diagnostic_only", "missing_plugin",
}

VALID_POTENTIAL_ISSUE_TYPES = {"config", "syntax", "logic"}
VALID_POTENTIAL_FIX_TYPES = {"configure_tool", "configure_credential", "fix_step_typo", "pull_image", "logic_error"}

# Extracts JSON object from text that might have surrounding prose or markdown fences
_JSON_BLOCK = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_JSON_BARE = re.compile(r"\{.*\}", re.DOTALL)


def parse_analysis_response(raw: str) -> dict:
    """
    Parse the LLM response into a validated analysis dict.

    Returns dict with keys: root_cause, fix_suggestion, confidence, fix_type.
    On parse failure, returns a safe diagnostic_only fallback.
    """
    text = raw.strip()

    # Try to extract JSON from markdown code fence first
    match = _JSON_BLOCK.search(text)
    if match:
        text = match.group(1)
    else:
        # Fall back to finding a bare JSON object
        match = _JSON_BARE.search(text)
        if match:
            text = match.group(0)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse LLM response as JSON: %s | raw: %.200s", e, raw)
        return _fallback("Could not parse LLM response")

    return _validate(data)


def _validate(data: dict) -> dict:
    """Validate and normalise parsed JSON into the expected schema."""
    root_cause = str(data.get("root_cause", "")).strip()
    fix_suggestion = str(data.get("fix_suggestion", "")).strip()

    raw_steps = data.get("steps", [])
    steps = [str(s).strip() for s in raw_steps if str(s).strip()] if isinstance(raw_steps, list) else []

    try:
        confidence = float(data.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = 0.0

    fix_type = str(data.get("fix_type", "diagnostic_only")).strip().lower()
    if fix_type not in VALID_FIX_TYPES:
        logger.warning("Unknown fix_type '%s', defaulting to diagnostic_only", fix_type)
        fix_type = "diagnostic_only"

    # missing_plugin requires admin install + Jenkins restart — no safe auto-fix.
    # Coerce to diagnostic_only so UI shows the manual steps instead of a broken Apply Fix button.
    if fix_type == "missing_plugin":
        fix_type = "diagnostic_only"

    # Enforce: low confidence → diagnostic_only
    if confidence < 0.6:
        fix_type = "diagnostic_only"

    if not root_cause:
        return _fallback("LLM returned empty root_cause")

    result = {
        "root_cause": root_cause,
        "fix_suggestion": fix_suggestion or "Review the failed stage log manually.",
        "steps": steps,
        "confidence": confidence,
        "fix_type": fix_type,
    }
    # Pass through optional fix fields from LLM
    if data.get("bad_line"):
        result["bad_line"] = str(data["bad_line"])
    if data.get("correct_line"):
        result["correct_line"] = str(data["correct_line"])
    if data.get("bad_image"):
        result["bad_image"] = str(data["bad_image"])
    if data.get("correct_image"):
        result["correct_image"] = str(data["correct_image"])
    if data.get("credential_type"):
        result["credential_type"] = str(data["credential_type"]).strip().lower()
    result["potential_issues"] = _parse_potential_issues(data.get("potential_issues", []))
    return result


def _parse_potential_issues(raw_list) -> list:
    """Parse and validate potential_issues list from LLM response. Skips malformed entries."""
    if not isinstance(raw_list, list):
        return []
    result = []
    for entry in raw_list[:5]:
        if not isinstance(entry, dict):
            continue
        issue_type = str(entry.get("type", "")).strip().lower()
        line = str(entry.get("line", "")).strip()
        issue = str(entry.get("issue", "")).strip()
        fix_type = str(entry.get("fix_type", "")).strip().lower()
        if not issue_type or not line or not issue or not fix_type:
            continue
        if issue_type not in VALID_POTENTIAL_ISSUE_TYPES:
            continue
        if fix_type not in VALID_POTENTIAL_FIX_TYPES:
            continue
        item = {
            "type": issue_type,
            "line": line,
            "issue": issue,
            "fix_type": fix_type,
        }
        correct_line = str(entry.get("correct_line", "")).strip()
        if correct_line:
            item["correct_line"] = correct_line
        raw_manual = entry.get("manual_steps", [])
        if isinstance(raw_manual, list):
            manual_steps = [str(s).strip() for s in raw_manual if str(s).strip()]
            if manual_steps:
                item["manual_steps"] = manual_steps[:6]
        result.append(item)
    return result


def _fallback(reason: str) -> dict:
    return {
        "root_cause": reason,
        "fix_suggestion": "Manual review required.",
        "steps": [],
        "confidence": 0.0,
        "fix_type": "diagnostic_only",
        "potential_issues": [],
    }
