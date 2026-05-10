"""
Persistent multi-LLM-key store.
Saved to $DATA_DIR/llm_keys.json. Provider-agnostic — each key tagged with provider
so the UI can group/sort. Activating a key writes it to .env (ANTHROPIC_API_KEY,
OPENAI_API_KEY, etc.) and clears the settings cache so the next call hot-reloads.
Key values are stored in the file but never returned via API — only masked.
"""
from __future__ import annotations
import json
import uuid
import time
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Provider → .env var that holds the active key for that provider.
# Add new providers here when wiring them into the codebase.
_PROVIDER_ENV_VAR = {
    "anthropic": "ANTHROPIC_API_KEY",
}

VALID_PROVIDERS = tuple(_PROVIDER_ENV_VAR.keys())


def _data_dir() -> Path:
    import os
    data_dir = os.environ.get("DATA_DIR", "").strip()
    if not data_dir:
        data_dir = str(Path.home() / ".devops-ai")
    p = Path(data_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _keys_path() -> Path:
    return _data_dir() / "llm_keys.json"


def _load() -> list[dict]:
    path = _keys_path()
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except Exception:
        return []


def _save(keys: list[dict]) -> None:
    _keys_path().write_text(json.dumps(keys, indent=2))


def _mask(key: dict) -> dict:
    out = {k: v for k, v in key.items() if k != "key"}
    raw = key.get("key", "")
    out["key_preview"] = _preview(raw)
    return out


def _preview(raw: str) -> str:
    if not raw:
        return ""
    if len(raw) <= 12:
        return "•" * len(raw)
    return f"{raw[:7]}…{raw[-4:]}"


def list_keys() -> list[dict]:
    """All keys with secret masked. Sorted by provider then created_at."""
    keys = [_mask(k) for k in _load()]
    keys.sort(key=lambda k: (k.get("provider", ""), k.get("created_at", 0)))
    return keys


def get_active_key(provider: str) -> Optional[dict]:
    """Active key for a provider (full, with secret) or None."""
    provider = provider.lower().strip()
    for k in _load():
        if k.get("provider") == provider and k.get("active"):
            return k
    return None


def get_key_by_id(key_id: str) -> Optional[dict]:
    """Lookup a key by id (full, with secret) or None."""
    for k in _load():
        if k.get("id") == key_id:
            return k
    return None


def add_key(name: str, provider: str, key: str) -> dict:
    """
    Create a new key. First key for a provider auto-activates.
    Raises ValueError on bad input. Returns masked key.
    """
    name = (name or "").strip()
    provider = (provider or "").strip().lower()
    key = (key or "").strip()

    if not name:
        raise ValueError("Key name is required.")
    if provider not in VALID_PROVIDERS:
        raise ValueError(f"provider must be one of {VALID_PROVIDERS}.")
    if not key:
        raise ValueError("Key value is required.")
    if provider == "anthropic" and not key.startswith("sk-"):
        raise ValueError("Anthropic key must start with 'sk-'.")

    keys = _load()
    # Name must be unique within a provider for clear UX
    if any(k.get("provider") == provider and k.get("name") == name for k in keys):
        raise ValueError(f"A key named '{name}' already exists for {provider}.")

    has_active_for_provider = any(
        k.get("provider") == provider and k.get("active") for k in keys
    )
    new_key = {
        "id": str(uuid.uuid4()),
        "name": name,
        "provider": provider,
        "key": key,
        "created_at": int(time.time()),
        "active": not has_active_for_provider,
    }
    keys.append(new_key)
    _save(keys)

    if new_key["active"]:
        _write_env_for_provider(provider, key)

    logger.info("LLM key added: name=%s provider=%s active=%s", name, provider, new_key["active"])
    return _mask(new_key)


def activate_key(key_id: str) -> bool:
    """
    Set this key as active for its provider, deactivate others of same provider,
    write to .env, clear settings cache. Returns False if key_id not found.
    """
    keys = _load()
    target = next((k for k in keys if k.get("id") == key_id), None)
    if not target:
        return False

    provider = target["provider"]
    for k in keys:
        if k.get("provider") == provider:
            k["active"] = (k["id"] == key_id)
    _save(keys)

    _write_env_for_provider(provider, target["key"])
    logger.info("LLM key activated: name=%s provider=%s", target["name"], provider)
    return True


def delete_key(key_id: str) -> tuple[bool, str]:
    """
    Returns (ok, error_msg). Refuses to delete the active key for a provider —
    user must activate another first. Prevents accidental loss of LLM access.
    """
    keys = _load()
    target = next((k for k in keys if k.get("id") == key_id), None)
    if not target:
        return False, "Key not found."
    if target.get("active"):
        return False, "Cannot delete the active key. Activate another key first."

    keys = [k for k in keys if k.get("id") != key_id]
    _save(keys)
    logger.info("LLM key deleted: name=%s provider=%s", target["name"], target["provider"])
    return True, ""


def _write_env_for_provider(provider: str, key: str) -> None:
    """Write key to .env under the provider's env var, clear settings cache."""
    env_var = _PROVIDER_ENV_VAR.get(provider)
    if not env_var:
        logger.warning("No env var mapping for provider '%s' — skipping .env write", provider)
        return
    from ui.setup_handler import _write_env, _clear_settings_cache
    _write_env({env_var: key})
    _clear_settings_cache()
