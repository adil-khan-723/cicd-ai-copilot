from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config.settings import Settings


def validate_config(settings: Settings) -> None:
    if settings.llm_provider == "anthropic" and not settings.anthropic_api_key:
        raise SystemExit(
            "ERROR: ANTHROPIC_API_KEY not set.\n"
            "Set it in .env or as an environment variable.\n"
            "Get your key at https://console.anthropic.com"
        )
