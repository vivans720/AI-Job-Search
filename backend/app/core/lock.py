import asyncio
import contextlib
import time
import uuid
import structlog
from typing import AsyncIterator, Optional
from app.core.redis import get_redis

logger = structlog.get_logger(__name__)

# Atomic release Lua script ensuring token match before delete
RELEASE_LOCK_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


class RedisLockError(Exception):
    pass


@contextlib.asynccontextmanager
async def redis_lock(
    name: str,
    timeout_seconds: int = 60,
    retry_interval: float = 0.2,
    max_wait_seconds: float = 0.0,
) -> AsyncIterator[bool]:
    redis = await get_redis()
    lock_key = f"lock:{name}"
    lock_token = str(uuid.uuid4())
    acquired = False

    if not redis:
        logger.debug("redis_unavailable_bypassing_lock", lock=name)
        yield True
        return

    start_time = time.monotonic()
    try:
        while True:
            # NX: set if not exists, PX: expiry milliseconds
            res = await redis.set(
                lock_key,
                lock_token,
                nx=True,
                px=int(timeout_seconds * 1000),
            )
            if res:
                acquired = True
                logger.debug("redis_lock_acquired", lock=name, token=lock_token)
                break

            if max_wait_seconds <= 0 or (time.monotonic() - start_time) >= max_wait_seconds:
                break

            await asyncio.sleep(retry_interval)

        if not acquired:
            logger.warning("redis_lock_failed_to_acquire", lock=name)
            raise RedisLockError(f"Could not acquire lock '{name}' within timeout")

        yield acquired

    finally:
        if acquired and redis:
            try:
                await redis.eval(RELEASE_LOCK_LUA, 1, lock_key, lock_token)
                logger.debug("redis_lock_released", lock=name, token=lock_token)
            except Exception as e:
                logger.warning("redis_lock_release_failed", lock=name, error=str(e))
