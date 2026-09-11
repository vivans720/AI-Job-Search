import time
import structlog
from typing import Optional, Tuple
from app.core.redis import get_redis

logger = structlog.get_logger(__name__)

# Sliding-window rate limiter via Redis sorted set (ZSET)
SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local clear_before = now - window

-- Remove old events outside the window
redis.call('ZREMRANGEBYSCORE', key, 0, clear_before)

-- Count current events in window
local current_requests = redis.call('ZCARD', key)

if current_requests < limit then
    redis.call('ZADD', key, now, now)
    redis.call('EXPIRE', key, math.ceil(window))
    return {1, limit - current_requests - 1}
else
    return {0, 0}
end
"""


async def check_rate_limit(
    identifier: str,
    limit: int = 30,
    window_seconds: int = 60,
) -> Tuple[bool, int]:
    """
    Returns (is_allowed, remaining_quota)
    """
    redis = await get_redis()
    if not redis:
        # Fail open if Redis is down
        return True, limit

    key = f"ratelimit:{identifier}"
    now = time.time()
    try:
        res = await redis.eval(SLIDING_WINDOW_LUA, 1, key, now, window_seconds, limit)
        allowed = bool(res[0] == 1)
        remaining = int(res[1])
        return allowed, remaining
    except Exception as e:
        logger.warning("rate_limit_eval_error", identifier=identifier, error=str(e))
        return True, limit
