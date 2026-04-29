"""
Secrets Manager — Phase 5.

Three responsibilities:
  1. scrub(text)              — redact credential patterns from error strings/logs
  2. check_startup_security() — return list of security warnings at boot time
  3. audit_secret_used()      — append-only record of which credential was accessed

Secret values are NEVER stored, logged, or persisted anywhere in this module.
"""
import re
import logging
from agent.audit_log import log_fix

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Credential patterns → redaction labels
# Each entry: (compiled_pattern, replacement_string)
# ---------------------------------------------------------------------------
_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Anthropic API keys: sk-ant-api03-...
    (re.compile(r'\bsk-ant-[A-Za-z0-9_-]{20,}\b'), '[REDACTED:anthropic-key]'),
    # GitHub fine-grained PATs: github_pat_...
    (re.compile(r'\bgithub_pat_[A-Za-z0-9_]{36,}\b'), '[REDACTED:github-pat]'),
    # GitHub classic PATs: ghp_...
    (re.compile(r'\bghp_[A-Za-z0-9]{36,}\b'), '[REDACTED:github-token]'),
    # Jenkins API tokens: exactly 32 lowercase hex chars (word-boundary via lookarounds)
    (re.compile(r'(?<!\w)[0-9a-f]{32}(?!\w)'), '[REDACTED:jenkins-token]'),
    # AWS access key IDs: AKIA...
    (re.compile(r'\bAKIA[0-9A-Z]{16}\b'), '[REDACTED:aws-key]'),
    # HTTP Bearer tokens
    (re.compile(r'(?i)Bearer\s+[A-Za-z0-9\-._~+/]+=*'), 'Bearer [REDACTED]'),
    # HTTP Basic auth header values
    (re.compile(r'(?i)Basic\s+[A-Za-z0-9+/]+=*'), 'Basic [REDACTED]'),
]


def scrub(text: str) -> str:
    """
    Replace any recognised credential patterns in text with redaction labels.
    Safe to call on exception messages, HTTP error bodies, log strings.
    Returns text unchanged if empty/None.
    """
    if not text:
        return text
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def check_startup_security(settings) -> list[str]:
    """
    Inspect settings and return a list of human-readable security warnings.
    Never raises. Caller is responsible for logging the returned strings.
    """
    warnings: list[str] = []

    if not getattr(settings, 'webhook_secret', ''):
        warnings.append(
            "SECURITY: WEBHOOK_SECRET is not set — incoming webhook requests are not authenticated. "
            "Set WEBHOOK_SECRET in .env to enable HMAC validation."
        )

    if not getattr(settings, 'jenkins_token', ''):
        warnings.append(
            "SECURITY: JENKINS_TOKEN is empty — Jenkins API calls will fail. "
            "Set JENKINS_TOKEN in .env or via the Setup wizard."
        )

    api_key = getattr(settings, 'anthropic_api_key', '')
    log_level = getattr(settings, 'log_level', 'INFO').upper()
    if api_key and log_level in ('DEBUG', 'TRACE'):
        warnings.append(
            "SECURITY: DEBUG log level is active while ANTHROPIC_API_KEY is set. "
            "Ensure the key does not appear in any log format string."
        )

    return warnings


# ---------------------------------------------------------------------------
# Existing helpers — unchanged
# ---------------------------------------------------------------------------

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
