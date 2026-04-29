"""
MD5-keyed LLM response cache, scoped per active profile.
Uses Redis when available (REDIS_URL in env), falls back to in-memory dict.
TTL = 7 days. Cache is cleared on profile switch.
"""
import hashlib
import json
import logging
import os
import time

logger = logging.getLogger(__name__)

_TTL_SECONDS = 604800  # 7 days

# In-memory fallback: {profile_id: {md5_key: {"result": dict, "expires_at": float}}}
_mem: dict[str, dict] = {}

_redis_client = None

try:
    import redis as _redis_lib
    _url = os.environ.get("REDIS_URL", "").strip()
    if _url:
        _r = _redis_lib.from_url(_url, socket_connect_timeout=2, decode_responses=True)
        _r.ping()
        _redis_client = _r
        logger.info("Redis cache connected: %s", _url)
    else:
        logger.debug("REDIS_URL not set — using in-memory cache")
except Exception as exc:
    logger.warning("Redis unavailable (%s) — falling back to in-memory cache", exc)
    _redis_client = None


def _profile_id() -> str:
    """Return active profile ID, or 'default' if none active."""
    try:
        from ui.profiles_store import get_active_profile
        p = get_active_profile()
        return p["id"] if p else "default"
    except Exception:
        return "default"


def cache_key(context: str) -> str:
    return hashlib.md5(context.encode()).hexdigest()


def get(context: str) -> dict | None:
    key = cache_key(context)
    pid = _profile_id()

    if _redis_client is not None:
        try:
            raw = _redis_client.get(f"llm:{pid}:{key}")
            if raw:
                logger.debug("Redis cache hit for profile=%s key=%s", pid[:8], key[:8])
                return json.loads(raw)
        except Exception as exc:
            logger.warning("Redis get failed (%s) — trying memory cache", exc)

    entry = _mem.get(pid, {}).get(key)
    if entry is None:
        return None
    if time.time() > entry["expires_at"]:
        _mem.get(pid, {}).pop(key, None)
        logger.debug("Memory cache expired for profile=%s key=%s", pid[:8], key[:8])
        return None
    logger.debug("Memory cache hit for profile=%s key=%s", pid[:8], key[:8])
    return entry["result"]


def set(context: str, result: dict) -> None:
    key = cache_key(context)
    pid = _profile_id()

    if _redis_client is not None:
        try:
            _redis_client.setex(f"llm:{pid}:{key}", _TTL_SECONDS, json.dumps(result))
            logger.debug("Redis cached profile=%s key=%s", pid[:8], key[:8])
            return
        except Exception as exc:
            logger.warning("Redis set failed (%s) — falling back to memory", exc)

    if pid not in _mem:
        _mem[pid] = {}
    _mem[pid][key] = {"result": result, "expires_at": time.time() + _TTL_SECONDS}
    logger.debug("Memory cached profile=%s key=%s", pid[:8], key[:8])


def clear() -> None:
    """Clear cache for the active profile only."""
    pid = _profile_id()
    _mem.pop(pid, None)
    if _redis_client is not None:
        try:
            keys = _redis_client.keys(f"llm:{pid}:*")
            if keys:
                _redis_client.delete(*keys)
        except Exception as exc:
            logger.warning("Redis clear failed: %s", exc)


def clear_all() -> None:
    """Clear cache for all profiles (used on startup)."""
    _mem.clear()
    if _redis_client is not None:
        try:
            keys = _redis_client.keys("llm:*")
            if keys:
                _redis_client.delete(*keys)
        except Exception as exc:
            logger.warning("Redis clear_all failed: %s", exc)
