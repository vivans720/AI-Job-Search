import asyncio
import random
import time
from typing import Optional
import structlog
import redis.asyncio as aioredis
from app.config import settings

logger = structlog.get_logger(__name__)

def get_source_rate_limits() -> dict[str, dict[str, float]]:
    return {
        "linkedin": {
            "rate": getattr(settings, "RATE_LIMIT_LINKEDIN_RATE", 10),
            "per": getattr(settings, "RATE_LIMIT_LINKEDIN_PER", 60.0),
            "jitter_min": 2.0,
            "jitter_max": 4.5,
        },
        "naukri": {
            "rate": getattr(settings, "RATE_LIMIT_NAUKRI_RATE", 15),
            "per": getattr(settings, "RATE_LIMIT_NAUKRI_PER", 60.0),
            "jitter_min": 1.5,
            "jitter_max": 3.5,
        },
        "internshala": {
            "rate": getattr(settings, "RATE_LIMIT_INTERNSHALA_RATE", 20),
            "per": getattr(settings, "RATE_LIMIT_INTERNSHALA_PER", 60.0),
            "jitter_min": 1.0,
            "jitter_max": 2.5,
        },
        "default": {"rate": 30, "per": 60.0, "jitter_min": 1.0, "jitter_max": 2.0},
    }

SOURCE_RATE_LIMITS = get_source_rate_limits()

_in_memory_locks: dict[str, asyncio.Lock] = {}
_in_memory_last_called: dict[str, float] = {}
_source_cooldowns: dict[str, float] = {}


class SourceRateLimiter:
    """
    Per-source async rate limiter with humanized jitter and exponential backoff.
    Uses Redis token/timestamp tracking if Redis is available;
    falls back to process-local async rate limiting.
    """

    def __init__(self, source_name: str, rate: Optional[int] = None, per: Optional[float] = None):
        self.source_name = source_name.lower()
        limits = get_source_rate_limits()
        cfg = limits.get(self.source_name, limits["default"])
        self.rate = rate or cfg["rate"]
        self.per = per or cfg["per"]
        self.jitter_min = cfg.get("jitter_min", 1.0)
        self.jitter_max = cfg.get("jitter_max", 2.5)
        self.min_interval = self.per / self.rate

    def mark_blocked(self, attempt: int = 1, base_seconds: float = 10.0):
        """Trigger exponential backoff with full jitter upon 429/403/999 detection."""
        jitter = random.uniform(1.0, 3.5)
        cooldown = min(120.0, (base_seconds * (2 ** max(0, attempt - 1))) + jitter)
        _source_cooldowns[self.source_name] = time.time() + cooldown
        logger.warning(
            "source_rate_limit_backoff_triggered",
            source=self.source_name,
            attempt=attempt,
            cooldown_sec=round(cooldown, 2),
        )

    def is_cooling_down(self) -> bool:
        return _source_cooldowns.get(self.source_name, 0.0) > time.time()

    async def acquire(self) -> float:
        """Enforces rate limit by delaying if needed before proceeding. Returns waited seconds."""
        # Wait out cooldown if source was recently blocked
        remaining_cooldown = _source_cooldowns.get(self.source_name, 0.0) - time.time()
        cooldown_waited = 0.0
        if remaining_cooldown > 0:
            logger.info("waiting_out_source_cooldown", source=self.source_name, remaining=round(remaining_cooldown, 2))
            await asyncio.sleep(remaining_cooldown)
            cooldown_waited = remaining_cooldown

        from app.core.redis import get_redis
        client: Optional[aioredis.Redis] = None
        should_close = False
        try:
            client = await get_redis()
            if not client:
                client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
                should_close = True
            await client.ping()
        except Exception:
            client = None

        waited = 0.0
        if client:
            try:
                waited = await self._acquire_redis(client)
            except Exception as e:
                logger.warning("redis_rate_limiter_failed_fallback_local", source=self.source_name, error=str(e))
                waited = await self._acquire_local()
            finally:
                if should_close and client:
                    try:
                        await client.aclose()
                    except Exception:
                        pass
        else:
            waited = await self._acquire_local()

        # Apply humanized randomized jitter interval
        jitter = random.uniform(self.jitter_min, self.jitter_max)
        await asyncio.sleep(jitter)
        return cooldown_waited + waited + jitter


    async def _acquire_redis(self, client: aioredis.Redis) -> float:
        key = f"rate_limit:source:{self.source_name}"
        now = time.time()
        # Clean timestamps older than window
        window_start = now - self.per
        pipe = client.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        results = await pipe.execute()
        current_count = results[1]
        waited = 0.0

        if current_count >= self.rate:
            # Get earliest entry in window
            oldest = await client.zrange(key, 0, 0, withscores=True)
            if oldest:
                oldest_time = oldest[0][1]
                sleep_sec = max(0.05, (oldest_time + self.per) - now)
                logger.info("source_rate_limited_sleeping_redis", source=self.source_name, sleep_sec=round(sleep_sec, 2))
                await asyncio.sleep(sleep_sec)
                waited = sleep_sec
                now = time.time()

        # Add current timestamp
        await client.zadd(key, {f"{now}": now})
        await client.expire(key, int(self.per * 2))
        return waited

    async def _acquire_local(self) -> float:
        if self.source_name not in _in_memory_locks:
            _in_memory_locks[self.source_name] = asyncio.Lock()

        waited = 0.0
        async with _in_memory_locks[self.source_name]:
            now = time.time()
            last = _in_memory_last_called.get(self.source_name, 0.0)
            elapsed = now - last
            if elapsed < self.min_interval:
                sleep_sec = self.min_interval - elapsed
                logger.debug("source_rate_limited_sleeping_local", source=self.source_name, sleep_sec=round(sleep_sec, 2))
                await asyncio.sleep(sleep_sec)
                waited = sleep_sec
            _in_memory_last_called[self.source_name] = time.time()
        return waited

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


def get_source_rate_limiter(source_name: str) -> SourceRateLimiter:
    return SourceRateLimiter(source_name)
