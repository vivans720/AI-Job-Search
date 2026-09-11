import asyncio
import functools
import hashlib
import json
import structlog
from typing import Any, Callable, Optional
from app.core.redis import get_redis

logger = structlog.get_logger(__name__)


def make_cache_key(prefix: str, *args, **kwargs) -> str:
    key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    hashed = hashlib.sha256(key_data.encode("utf-8")).hexdigest()[:16]
    return f"cache:{prefix}:{hashed}"


def cached(ttl_seconds: int = 300, prefix: str = "query"):
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            redis = await get_redis()
            if not redis:
                return await func(*args, **kwargs)

            cache_key = make_cache_key(prefix, *args, **kwargs)
            try:
                cached_val = await redis.get(cache_key)
                if cached_val is not None:
                    logger.debug("cache_hit", key=cache_key)
                    return json.loads(cached_val)
            except Exception as e:
                logger.debug("cache_get_error", key=cache_key, error=str(e))

            result = await func(*args, **kwargs)

            try:
                if result is not None:
                    serialized = json.dumps(result, default=str)
                    await redis.set(cache_key, serialized, ex=ttl_seconds)
                    logger.debug("cache_set", key=cache_key, ttl=ttl_seconds)
            except Exception as e:
                logger.debug("cache_set_error", key=cache_key, error=str(e))

            return result
        return wrapper
    return decorator


async def invalidate_cache(pattern: str) -> int:
    redis = await get_redis()
    if not redis:
        return 0
    try:
        keys = []
        cursor = 0
        match_pattern = f"cache:{pattern}" if not pattern.startswith("cache:") else pattern
        while True:
            cursor, batch = await redis.scan(cursor=cursor, match=match_pattern, count=100)
            keys.extend(batch)
            if cursor == 0:
                break

        if keys:
            deleted = await redis.delete(*keys)
            logger.info("cache_invalidated", pattern=pattern, count=deleted)
            return deleted
        return 0
    except Exception as e:
        logger.warning("cache_invalidation_failed", pattern=pattern, error=str(e))
        return 0
