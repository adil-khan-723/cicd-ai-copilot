"""
Secrets Manager (Increment 29).

Handles secrets exclusively via Slack DM.

Rules (non-negotiable):
- Secrets are requested by DMing the user, never posted in channels
- Collected value is passed directly to the target API call
- Value is NEVER stored in memory, files, logs, or any persistent store
- Audit log records: secret name + user ID + timestamp (never the value)
"""
import logging
from agent.audit_log import log_fix

logger = logging.getLogger(__name__)


def request_secret_via_dm(
    client,
    user_id: str,
    secret_name: str,
    context: str = "",
) -> None:
    """
    Send a Slack DM to the user requesting a specific secret value.

    The user replies in DM. The calling flow must handle the response
    via a Slack event handler — this function only initiates the request.

    Args:
        client: Slack WebClient instance
        user_id: Slack user ID to DM
        secret_name: Name of the secret being requested (e.g. 'AWS_ACCESS_KEY_ID')
        context: Optional context explaining why the secret is needed
    """
    message = (
        f":lock: *Secret required: `{secret_name}`*\n"
        f"{context + chr(10) if context else ''}"
        f"Please reply with the value in this DM. "
        f"It will be used immediately and never stored."
    )

    try:
        # Open a DM channel with the user
        dm_response = client.conversations_open(users=[user_id])
        dm_channel = dm_response["channel"]["id"]

        client.chat_postMessage(
            channel=dm_channel,
            text=message,
            unfurl_links=False,
            unfurl_media=False,
        )
        logger.info("Secret request sent via DM to %s for '%s'", user_id, secret_name)

        # Audit: record that a secret was requested (never the value)
        log_fix(
            fix_type="secret_requested",
            triggered_by=user_id,
            job_name="secrets_manager",
            build_number="0",
            result=f"requested:{secret_name}",
            confidence_at_trigger=0.0,
        )

    except Exception as e:
        logger.error("Failed to send secret request DM to %s: %s", user_id, e)


def use_secret_directly(secret_value: str, target_fn, *args, **kwargs):
    """
    Pass a secret value directly to a target function without storing it.

    The secret_value is passed to target_fn and immediately goes out of scope.
    No reference to the value is kept after the call.

    Args:
        secret_value: The secret value (never stored or logged)
        target_fn: Callable that uses the secret
        *args, **kwargs: Additional args passed to target_fn

    Returns:
        Whatever target_fn returns
    """
    result = target_fn(secret_value, *args, **kwargs)
    # secret_value reference ends here — Python GC will collect it
    return result


def audit_secret_used(user_id: str, secret_name: str) -> None:
    """
    Record that a secret was used. Logs name + user, NEVER the value.
    Call this immediately after use_secret_directly() returns.
    """
    log_fix(
        fix_type="secret_used",
        triggered_by=user_id,
        job_name="secrets_manager",
        build_number="0",
        result=f"used:{secret_name}",
        confidence_at_trigger=0.0,
    )
    logger.info("Secret '%s' used by %s — value not retained", secret_name, user_id)
