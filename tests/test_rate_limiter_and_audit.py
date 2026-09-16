import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
from app.sources.rate_limiter import SourceRateLimiter, get_source_rate_limits
from app.utils.sync_logger import get_default_log_file, log_sync_event, get_recent_sync_logs
from app.config import settings


@pytest.mark.asyncio
async def test_rate_limiter_dynamic_config():
    """Verify rate limiter reads settings dynamically."""
    limits = get_source_rate_limits()
    assert limits["linkedin"]["rate"] == settings.RATE_LIMIT_LINKEDIN_RATE
    assert limits["linkedin"]["per"] == settings.RATE_LIMIT_LINKEDIN_PER

    limiter = SourceRateLimiter("linkedin")
    assert limiter.rate == settings.RATE_LIMIT_LINKEDIN_RATE
    assert limiter.per == settings.RATE_LIMIT_LINKEDIN_PER
    assert limiter.min_interval == limiter.per / limiter.rate


@pytest.mark.asyncio
async def test_rate_limiter_redis_acquire():
    """Verify rate limiter sliding window executes without errors against mock Redis."""
    limiter = SourceRateLimiter("linkedin", rate=10, per=60.0)
    mock_redis = AsyncMock()
    mock_pipe = MagicMock()
    mock_pipe.execute = AsyncMock(return_value=[0, 2])  # current_count = 2, under rate limit
    mock_redis.pipeline = MagicMock(return_value=mock_pipe)

    waited = await limiter._acquire_redis(mock_redis)
    assert waited == 0.0
    mock_redis.zadd.assert_called_once()
    mock_redis.expire.assert_called_once()



def test_sync_logger_portable_path(tmp_path):
    """Verify sync logger handles relative and portable paths without machine-specific assumptions."""
    test_log = tmp_path / "sync_log.jsonl"
    event = {
        "source": "linkedin",
        "status": "success",
        "total_discovered": 10,
        "fresh_jobs": 8,
        "duration_ms": 1200.0,
    }
    logged = log_sync_event(event, log_file=test_log)
    assert logged["source"] == "linkedin"
    assert test_log.exists()

    recent = get_recent_sync_logs(limit=10, log_file=test_log)
    assert len(recent) == 1
    assert recent[0]["fresh_jobs"] == 8


@pytest.mark.asyncio
async def test_rate_limiter_backoff_and_cooldown():
    """Verify rate limiter triggers exponential cooldown when marked blocked."""
    limiter = SourceRateLimiter("linkedin")
    assert not limiter.is_cooling_down()

    limiter.mark_blocked(attempt=1, base_seconds=5.0)
    assert limiter.is_cooling_down()


@pytest.mark.asyncio
async def test_guest_session_manager(tmp_path):
    """Verify GuestSessionManager caches and reads public guest tokens."""
    from app.crawling.guest_session_manager import GuestSessionManager
    mgr = GuestSessionManager("test_source")
    mgr.session_file = tmp_path / "test_state.json"

    cookies = {"test_cookie": "xyz123"}
    mgr.save_cookies(cookies)

    loaded = mgr.load_cached_cookies()
    assert loaded.get("test_cookie") == "xyz123"

