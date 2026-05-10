"""
Validates and persists Jenkins credentials from the setup wizard.

Writes directly to .env (creates it if absent).
Clears the settings cache so the next get_settings() call re-reads from disk.
Never logs credential values.
"""
import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_ENV_PATH = Path(".env")

_REQUIRED_FIELDS = [
    "jenkins_url",
    "jenkins_user",
    "jenkins_token",
]

_URL_RE = re.compile(r"^https?://.+")


class SetupError(ValueError):
    pass


def validate_setup_payload(payload: dict) -> None:
    """
    Raises SetupError describing which field is invalid.
    Does not return anything — raises on first failure.
    """
    for field in _REQUIRED_FIELDS:
        if not payload.get(field, "").strip():
            raise SetupError(f"'{field}' is required and cannot be empty.")

    if not _URL_RE.match(payload["jenkins_url"]):
        raise SetupError("'jenkins_url' must be a valid http/https URL.")


def save_credentials(payload: dict) -> None:
    """
    Write credentials to .env and reload settings cache.
    Existing .env keys are updated in-place; unknown keys are preserved.
    """
    validate_setup_payload(payload)

    mapping = {
        "JENKINS_URL": payload["jenkins_url"].strip(),
        "JENKINS_USER": payload["jenkins_user"].strip(),
        "JENKINS_TOKEN": payload["jenkins_token"].strip(),
    }

    _write_env(mapping)
    _clear_settings_cache()
    logger.info("Setup credentials saved for jenkins=%s", payload["jenkins_url"])


def save_llm_config(payload: dict) -> None:
    """
    Persist LLM provider + model + API key to .env. Empty api_key skipped
    so user can update provider/model without retyping the key.
    Never logs the key value.
    """
    provider = str(payload.get("provider", "")).strip().lower()
    if provider not in ("anthropic", "ollama"):
        raise SetupError("provider must be 'anthropic' or 'ollama'.")

    mapping: dict[str, str] = {"LLM_PROVIDER": provider}

    if provider == "anthropic":
        api_key = str(payload.get("anthropic_api_key", "")).strip()
        # Empty key => skip (preserve existing). Non-empty key => write.
        if api_key:
            if not api_key.startswith("sk-"):
                raise SetupError("anthropic_api_key must start with 'sk-'.")
            mapping["ANTHROPIC_API_KEY"] = api_key
        analysis_model = str(payload.get("anthropic_analysis_model", "")).strip()
        generation_model = str(payload.get("anthropic_generation_model", "")).strip()
        if analysis_model:
            mapping["ANTHROPIC_ANALYSIS_MODEL"] = analysis_model
        if generation_model:
            mapping["ANTHROPIC_GENERATION_MODEL"] = generation_model

    elif provider == "ollama":
        base_url = str(payload.get("ollama_base_url", "")).strip()
        if base_url:
            mapping["OLLAMA_BASE_URL"] = base_url
        analysis_model = str(payload.get("analysis_model", "")).strip()
        generation_model = str(payload.get("generation_model", "")).strip()
        if analysis_model:
            mapping["ANALYSIS_MODEL"] = analysis_model
        if generation_model:
            mapping["GENERATION_MODEL"] = generation_model

    _write_env(mapping)
    _clear_settings_cache()
    logger.info("LLM config saved (provider=%s, key_updated=%s)",
                provider, "yes" if "ANTHROPIC_API_KEY" in mapping else "no")


def _clear_settings_cache() -> None:
    from config import settings as _cfg
    _cfg._settings = None  # reset manual singleton so next call re-reads .env


def _write_env(updates: dict[str, str]) -> None:
    """Update or append key=value pairs in .env."""
    existing: dict[str, str] = {}
    lines: list[str] = []

    if _ENV_PATH.exists():
        for line in _ENV_PATH.read_text().splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key = stripped.split("=", 1)[0].strip().upper()
                existing[key] = line
            lines.append(line)

    for key, value in updates.items():
        new_line = f"{key}={value}"
        if key in existing:
            lines = [new_line if l.strip().upper().startswith(key + "=") else l for l in lines]
        else:
            lines.append(new_line)

    _ENV_PATH.write_text("\n".join(lines) + "\n")
