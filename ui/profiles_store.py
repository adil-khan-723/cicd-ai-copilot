"""
Persistent Jenkins profile store.
Profiles are saved to $DATA_DIR/profiles.json (default: ~/.devops-ai/profiles.json).
Each profile gets its own data directory: $DATA_DIR/profiles/{profile_id}/
Token values are stored in the file but never returned via API — only masked.
"""
from __future__ import annotations
import json
import uuid
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _data_dir() -> Path:
    import os
    data_dir = os.environ.get("DATA_DIR", "").strip()
    if not data_dir:
        data_dir = str(Path.home() / ".devops-ai")
    p = Path(data_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _profiles_path() -> Path:
    return _data_dir() / "profiles.json"


def _profile_dir(profile_id: str) -> Path:
    """Per-profile data directory. Created on first access."""
    d = _data_dir() / "profiles" / profile_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_active_profile_dir() -> Path:
    """Return the data directory for the currently active profile.
    Falls back to the root data dir if no profile is active."""
    for p in _load():
        if p.get("active"):
            return _profile_dir(p["id"])
    return _data_dir()


def _load() -> list[dict]:
    path = _profiles_path()
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except Exception:
        return []


def _save(profiles: list[dict]) -> None:
    _profiles_path().write_text(json.dumps(profiles, indent=2))


def list_profiles() -> list[dict]:
    """Return all profiles with token masked."""
    return [_mask(p) for p in _load()]


def get_active_profile() -> Optional[dict]:
    """Return the active profile (full, with token) or None."""
    for p in _load():
        if p.get("active"):
            return p
    return None


def add_profile(alias: str, jenkins_url: str, jenkins_user: str, jenkins_token: str) -> dict:
    profiles = _load()
    profile_id = str(uuid.uuid4())
    profile = {
        "id": profile_id,
        "alias": alias.strip(),
        "jenkins_url": jenkins_url.strip().rstrip("/"),
        "jenkins_user": jenkins_user.strip(),
        "jenkins_token": jenkins_token.strip(),
        "active": len(profiles) == 0,  # first profile auto-activates
    }
    profiles.append(profile)
    _save(profiles)
    # Create the profile-specific data directory immediately
    _profile_dir(profile_id)
    logger.info("Profile added: %s (%s) — data dir created", alias, jenkins_url)
    return _mask(profile)


def activate_profile(profile_id: str) -> bool:
    """Set profile as active, write credentials to .env, reload settings cache."""
    profiles = _load()
    target = next((p for p in profiles if p["id"] == profile_id), None)
    if not target:
        return False

    for p in profiles:
        p["active"] = p["id"] == profile_id
    _save(profiles)

    # Ensure profile dir exists (handles profiles created before this change)
    _profile_dir(profile_id)

    # Write to .env so get_settings() picks up the new credentials
    from ui.setup_handler import save_credentials
    save_credentials({
        "jenkins_url":   target["jenkins_url"],
        "jenkins_user":  target["jenkins_user"],
        "jenkins_token": target["jenkins_token"],
    })

    # Clear SSE bus history so the new profile starts with a clean feed
    from ui.event_bus import bus
    bus.clear_history()

    # Clear analysis cache so stale results from another profile don't appear
    from analyzer import cache
    cache.clear()

    logger.info("Profile activated: %s", target["alias"])
    return True


def delete_profile(profile_id: str) -> bool:
    profiles = _load()
    before = len(profiles)
    profiles = [p for p in profiles if p["id"] != profile_id]
    if len(profiles) == before:
        return False
    # If deleted profile was active, activate first remaining
    if profiles and not any(p.get("active") for p in profiles):
        profiles[0]["active"] = True
    _save(profiles)
    return True


def update_profile(profile_id: str, alias: str) -> bool:
    profiles = _load()
    for p in profiles:
        if p["id"] == profile_id:
            p["alias"] = alias.strip()
            _save(profiles)
            return True
    return False


def _mask(profile: dict) -> dict:
    return {k: v for k, v in profile.items() if k != "jenkins_token"}
