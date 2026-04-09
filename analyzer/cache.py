"""
MD5-keyed in-memory response cache for LLM analysis results.
Key = MD5 hash of the context string. TTL = 1 hour.
"""
import hashlib
import time
import logging

logger = logging.getLogger(__name__)

_TTL_SECONDS = 3600  # 1 hour

# Cache structure: {md5_key: {"result": dict, "expires_at": float}}
_cache: dict[str, dict] = {}


def cache_key(context: str) -> str:
    return hashlib.md5(context.encode()).hexdigest()


def get(context: str) -> dict | None:
    key = cache_key(context)
    entry = _cache.get(key)
    if entry is None:
        return None
    if time.time() > entry["expires_at"]:
        del _cache[key]
        logger.debug("Cache expired for key %s", key[:8])
        return None
    logger.debug("Cache hit for key %s", key[:8])
    return entry["result"]


def set(context: str, result: dict) -> None:
    key = cache_key(context)
    _cache[key] = {
        "result": result,
        "expires_at": time.time() + _TTL_SECONDS,
    }
    logger.debug("Cached result for key %s", key[:8])


def clear() -> None:
    """Clear all cache entries (useful for testing)."""
    _cache.clear()
