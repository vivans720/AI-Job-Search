import json
import uuid
import structlog
from typing import Any, Optional
import redis.asyncio as aioredis
from app.config import settings

logger = structlog.get_logger(__name__)

_redis_pool: Optional[aioredis.Redis] = None


async def init_redis_pool() -> Optional[aioredis.Redis]:
    global _redis_pool
    if _redis_pool is not None:
        return _redis_pool
    try:
        _redis_pool = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=3.0,
            socket_connect_timeout=3.0,
            max_connections=20,
        )
        await _redis_pool.ping()
        logger.info("redis_pool_initialized", url=settings.REDIS_URL)
        return _redis_pool
    except Exception as e:
        logger.warning("redis_pool_init_failed", error=str(e), url=settings.REDIS_URL)
        _redis_pool = None
        return None


async def close_redis_pool() -> None:
    global _redis_pool
    if _redis_pool is not None:
        try:
            await _redis_pool.aclose()
            logger.info("redis_pool_closed")
        except Exception as e:
            logger.warning("redis_pool_close_error", error=str(e))
        finally:
            _redis_pool = None


async def get_redis() -> Optional[aioredis.Redis]:
    global _redis_pool
    if _redis_pool is None:
        return await init_redis_pool()
    return _redis_pool
