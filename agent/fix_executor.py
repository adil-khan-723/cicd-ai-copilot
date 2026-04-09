"""
Fix executor (Increment 18).

Maps fix_type strings to concrete fix functions.
Never executes fixes for diagnostic_only — returns a FixResult with success=False.
"""
import logging
from agent.models import FixResult
from agent.pipeline_fixes import (
    retry_pipeline,
    clear_docker_cache,
    clear_npm_cache,
    pull_fresh_image,
    increase_timeout,
)

logger = logging.getLogger(__name__)

# fix_type → executor function
_FIX_MAP = {
    "retry": retry_pipeline,
    "clear_cache": clear_docker_cache,    # default to docker; npm variant via pipeline param
    "pull_image": pull_fresh_image,
    "increase_timeout": increase_timeout,
}

# These fix types must never be auto-executed — always diagnostic
_DIAGNOSTIC_ONLY = {"diagnostic_only"}


def execute_fix(fix_type: str, job_name: str, build_number: str = "0") -> FixResult:
    """
    Execute the approved fix.

    Args:
        fix_type: One of retry|clear_cache|pull_image|increase_timeout|diagnostic_only
        job_name: Jenkins job name
        build_number: Build number (informational, used in audit log)

    Returns:
        FixResult with success status and detail message.
    """
    if fix_type in _DIAGNOSTIC_ONLY:
        logger.info("Fix type '%s' is diagnostic only — not executing", fix_type)
        return FixResult(
            success=False,
            fix_type=fix_type,
            detail="This issue requires manual intervention — no automated fix available.",
        )

    executor = _FIX_MAP.get(fix_type)
    if executor is None:
        logger.warning("Unknown fix_type '%s' — treating as diagnostic_only", fix_type)
        return FixResult(
            success=False,
            fix_type=fix_type,
            detail=f"Unknown fix type '{fix_type}' — no executor registered.",
        )

    logger.info("Executing fix '%s' for job '%s' build #%s", fix_type, job_name, build_number)
    return executor(job_name, build_number)
