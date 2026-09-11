import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from app.sources.errors import (
    ErrorCategory,
    RateLimitBlockError,
    TransientNetworkError,
    ParseExtractionError,
    classify_error,
)
from app.sources.rate_limiter import SourceRateLimiter
from app.sources.base import JobSearchQuery, JobSource, SourceCrawlMetrics
from app.sources.registry import SourceRegistry


def test_classify_error_rate_limit():
    exc = Exception("HTTP 429 Too Many Requests: Rate limit exceeded")
    classified = classify_error(exc, source="linkedin", status_code=429)
    assert isinstance(classified, RateLimitBlockError)
    assert classified.category == ErrorCategory.RATE_LIMIT_BLOCK
    assert classified.retryable is False
    assert classified.status_code == 429


def test_classify_error_transient_network():
    exc = Exception("Connection reset by peer; timeout waiting for headers")
    classified = classify_error(exc, source="naukri")
    assert isinstance(classified, TransientNetworkError)
    assert classified.category == ErrorCategory.TRANSIENT_NETWORK
    assert classified.retryable is True


def test_classify_error_parse_failure():
    exc = KeyError("job_id not found in JSON payload")
    classified = classify_error(exc, source="naukri")
    assert isinstance(classified, ParseExtractionError)
    assert classified.category == ErrorCategory.PARSE_EXTRACTION
    assert classified.retryable is False


@pytest.mark.asyncio
async def test_rate_limiter_local():
    limiter = SourceRateLimiter("test_source", rate=50, per=1.0)
    t0 = asyncio.get_event_loop().time()
    await limiter.acquire()
    await limiter.acquire()
    t1 = asyncio.get_event_loop().time()
    assert (t1 - t0) >= 0.015  # min_interval 1/50 = 0.02s


@pytest.mark.asyncio
async def test_partial_failure_isolation_in_registry():
    """Verify that if one source fails with 429/blocked, remaining sources continue and succeed."""
    registry = SourceRegistry()

    # Failing source (e.g. LinkedIn 429)
    bad_source = MagicMock(spec=JobSource)
    bad_source.source_name = "linkedin"
    bad_source.enabled = True
    bad_source.status = "blocked"
    bad_source.last_error = "429 Too Many Requests"
    bad_source.last_error_category = "rate_limit_block"
    bad_source.reset_metrics = MagicMock()
    bad_source.get_metrics = MagicMock(return_value=SourceCrawlMetrics(source="linkedin", status="blocked", retries_count=2))

    # Successful source (e.g. Naukri)
    good_source = MagicMock(spec=JobSource)
    good_source.source_name = "naukri"
    good_source.enabled = True
    good_source.status = "ok"
    good_source.last_error = None
    good_source.last_error_category = None
    good_source.reset_metrics = MagicMock()
    good_source.get_metrics = MagicMock(return_value=SourceCrawlMetrics(source="naukri", status="ok", raw_discovered=5, duration_ms=120.0))

    registry.register(bad_source)
    registry.register(good_source)

    mock_db = AsyncMock()
    mock_ingestion_service = MagicMock()

    async def fake_ingest(db, src, q):
        if src.source_name == "linkedin":
            return {
                "source": "linkedin",
                "status": "blocked",
                "error": "429 Too Many Requests",
                "total_discovered": 0,
                "canonical_saved": 0,
                "updated_existing": 0,
            }
        return {
            "source": "naukri",
            "status": "success",
            "total_discovered": 5,
            "canonical_saved": 3,
            "updated_existing": 2,
        }

    mock_ingestion_service.ingest_source = AsyncMock(side_effect=fake_ingest)

    with patch("app.core.lock.redis_lock"):
        result = await registry.sync_all_isolated(mock_db, mock_ingestion_service)

    # Result should have partial_success status because Naukri succeeded and LinkedIn was blocked
    assert result["status"] == "partial_success"
    assert "naukri" in result["sources_synced"]
    assert result["sources"]["naukri"]["status"] == "success"
    assert result["sources"]["naukri"]["discovered"] == 5
    assert result["sources"]["linkedin"]["status"] == "blocked"
    assert result["sources"]["linkedin"]["error_category"] == "rate_limit_block"
