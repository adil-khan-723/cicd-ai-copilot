from __future__ import annotations
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config.settings import Settings

logger = logging.getLogger(__name__)


def validate_config(settings: Settings) -> None:
    """
    Soft-validate startup config. Never exits — server must boot so the user
    can fix missing config via the Settings UI without shell access.
    """
    if settings.llm_provider == "anthropic" and not settings.anthropic_api_key:
        logger.warning(
            "ANTHROPIC_API_KEY not set — LLM calls will fail until configured. "
            "Set it via Settings → LLM Configuration in the UI, or in .env. "
            "Get a key at https://console.anthropic.com"
        )


def warn_security_config(settings: Settings) -> None:
    """
    Emit logger.warning for security misconfigurations. Never raises.
    Intended to be called at startup after validate_config().
    """
    if not getattr(settings, 'webhook_secret', ''):
        logger.warning(
            "SECURITY: WEBHOOK_SECRET is not set — webhook requests are not authenticated. "
            "Set WEBHOOK_SECRET in .env to enable HMAC validation."
        )

    if not getattr(settings, 'jenkins_token', ''):
        logger.warning(
            "SECURITY: JENKINS_TOKEN is empty — Jenkins API calls will fail."
        )

    api_key = getattr(settings, 'anthropic_api_key', '')
    log_level = getattr(settings, 'log_level', 'INFO').upper()
    if api_key and log_level in ('DEBUG', 'TRACE'):
        logger.warning(
            "SECURITY: DEBUG log level is active while ANTHROPIC_API_KEY is set — "
            "ensure the key does not appear in any log format string."
        )
