import asyncio
import time
from typing import Optional
import structlog
import redis.asyncio as aioredis
from app.config import settings

logger = structlog.get_logger(__name__)

# Defaults: requests per minute per source
SOURCE_RATE_LIMITS = {
    "linkedin": {"rate": 5, "per": 60.0},     # 5 req/min (conservative)
    "naukri": {"rate": 15, "per": 60.0},      # 15 req/min
    "internshala": {"rate": 20, "per": 60.0}, # 20 req/min
    "default": {"rate": 30, "per": 60.0},
}

_in_memory_locks: dict[str, asyncio.Lock] = {}
_in_memory_last_called: dict[str, float] = {}


class SourceRateLimiter:
    """
    Per-source async rate limiter.
    Uses Redis token/timestamp tracking if Redis is available;
    falls back to process-local async rate limiting.
    """

    def __init__(self, source_name: str, rate: Optional[int] = None, per: Optional[float] = None):
        self.source_name = source_name.lower()
        cfg = SOURCE_RATE_LIMITS.get(self.source_name, SOURCE_RATE_LIMITS["default"])
        self.rate = rate or cfg["rate"]
        self.per = per or cfg["per"]
        self.min_interval = self.per / self.rate

    async def acquire(self) -> None:
        """Enforces rate limit by delaying if needed before proceeding."""
        # Check Redis availability
        client: Optional[aioredis.Redis] = None
        try:
            client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            await client.ping()
        except Exception:
            client = None

        if client:
            try:
                await self._acquire_redis(client)
                return
            except Exception as e:
                logger.warning("redis_rate_limiter_failed_fallback_local", source=self.source_name, error=str(e))
            finally:
                try:
                    await client.aclose()
                except Exception:
                    pass

        await self._acquire_local()

    async def _acquire_redis(self, client: aioredis.Redis) -> None:
        key = f"rate_limit:source:{self.source_name}"
        now = time.time()
        # Clean timestamps older than window
        window_start = now - self.per
        pipe = client.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        results = await pipe.execute()
        current_count = results[1]

        if current_count >= self.rate:
            # Get earliest entry in window
            oldest = await client.zrange(key, 0, 0, withscores=True)
            if oldest:
                oldest_time = oldest[0][1]
                sleep_sec = max(0.05, (oldest_time + self.per) - now)
                logger.info("source_rate_limited_sleeping_redis", source=self.source_name, sleep_sec=round(sleep_sec, 2))
                await asyncio.sleep(sleep_sec)
                now = time.time()

        # Add current timestamp
        await client.zadd(key, {f"{now}": now})
        await client.expire(key, int(self.per * 2))

    async def _acquire_local(self) -> None:
        if self.source_name not in _in_memory_locks:
            _in_memory_locks[self.source_name] = asyncio.Lock()

        async with _in_memory_locks[self.source_name]:
            now = time.time()
            last = _in_memory_last_called.get(self.source_name, 0.0)
            elapsed = now - last
            if elapsed < self.min_interval:
                sleep_sec = self.min_interval - elapsed
                logger.debug("source_rate_limited_sleeping_local", source=self.source_name, sleep_sec=round(sleep_sec, 2))
                await asyncio.sleep(sleep_sec)
            _in_memory_last_called[self.source_name] = time.time()

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


def get_source_rate_limiter(source_name: str) -> SourceRateLimiter:
    return SourceRateLimiter(source_name)
