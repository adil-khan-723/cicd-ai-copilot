"""
Secrets Manager.

Audit helpers for tracking secret usage.
Secret values are never stored, logged, or persisted.
"""
import logging
from agent.audit_log import log_fix

logger = logging.getLogger(__name__)


def use_secret_directly(secret_value: str, target_fn, *args, **kwargs):
    """
    Pass a secret value directly to a target function without storing it.
    The secret_value reference ends when target_fn returns.
    """
    result = target_fn(secret_value, *args, **kwargs)
    return result


def audit_secret_used(user_id: str, secret_name: str) -> None:
    """Record that a secret was used. Logs name + user, NEVER the value."""
    log_fix(
        fix_type="secret_used",
        triggered_by=user_id,
        job_name="secrets_manager",
        build_number="0",
        result=f"used:{secret_name}",
        confidence_at_trigger=0.0,
    )
    logger.info("Secret '%s' used by %s — value not retained", secret_name, user_id)
