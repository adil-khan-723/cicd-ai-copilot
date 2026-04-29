"""
MD5-keyed LLM response cache.
Uses Redis when available (REDIS_URL in env), falls back to in-memory dict.
TTL = 24 hours.
"""
import hashlib
import json
import logging
import os
import time

logger = logging.getLogger(__name__)

_TTL_SECONDS = 604800  # 7 days — safety net; cache cleared on every startup anyway

# In-memory fallback store: {md5_key: {"result": dict, "expires_at": float}}
_mem: dict[str, dict] = {}

# Redis client — None means use in-memory fallback
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


def cache_key(context: str) -> str:
    return hashlib.md5(context.encode()).hexdigest()


def get(context: str) -> dict | None:
    key = cache_key(context)

    if _redis_client is not None:
        try:
            raw = _redis_client.get(f"llm:{key}")
            if raw:
                logger.debug("Redis cache hit for key %s", key[:8])
                return json.loads(raw)
        except Exception as exc:
            logger.warning("Redis get failed (%s) — trying memory cache", exc)

    # Memory fallback
    entry = _mem.get(key)
    if entry is None:
        return None
    if time.time() > entry["expires_at"]:
        del _mem[key]
        logger.debug("Memory cache expired for key %s", key[:8])
        return None
    logger.debug("Memory cache hit for key %s", key[:8])
    return entry["result"]


def set(context: str, result: dict) -> None:
    key = cache_key(context)

    if _redis_client is not None:
        try:
            _redis_client.setex(f"llm:{key}", _TTL_SECONDS, json.dumps(result))
            logger.debug("Redis cached key %s", key[:8])
            return
        except Exception as exc:
            logger.warning("Redis set failed (%s) — falling back to memory", exc)

    _mem[key] = {"result": result, "expires_at": time.time() + _TTL_SECONDS}
    logger.debug("Memory cached key %s", key[:8])


def clear() -> None:
    """Clear all cache entries. Clears both Redis (if connected) and memory."""
    _mem.clear()
    if _redis_client is not None:
        try:
            keys = _redis_client.keys("llm:*")
            if keys:
                _redis_client.delete(*keys)
        except Exception as exc:
            logger.warning("Redis clear failed: %s", exc)
