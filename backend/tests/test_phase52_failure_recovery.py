import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.core.resilience import CircuitBreaker, CircuitBreakerOpenError, retry_with_backoff, get_circuit_breaker
from app.core.cache import cached, _MEMORY_CACHE
from app.intelligence.base import clean_and_extract_json
from app.services.job_ingestion_service import JobIngestionService, DEAD_LETTER_QUARANTINE
from app.sources.base import JobSource, RawJob, NormalizedJob, JobSearchQuery


@pytest.mark.asyncio
async def test_retry_with_backoff_success():
    call_count = 0

    @retry_with_backoff(retries=3, base_delay_sec=0.01, jitter=False)
    async def flaky_call():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("transient error")
        return "ok"

    result = await flaky_call()
    assert result == "ok"
    assert call_count == 3


@pytest.mark.asyncio
async def test_retry_with_backoff_exhaustion():
    call_count = 0

    @retry_with_backoff(retries=2, base_delay_sec=0.01, jitter=False)
    async def always_fails():
        nonlocal call_count
        call_count += 1
        raise RuntimeError("fatal crash")

    with pytest.raises(RuntimeError):
        await always_fails()
    assert call_count == 2


@pytest.mark.asyncio
async def test_circuit_breaker_trips_open_and_recovers():
    breaker = CircuitBreaker("test_service", failure_threshold=2, recovery_timeout_sec=0.1)

    async def fail_op():
        raise ConnectionRefusedError("endpoint unreachable")

    # 1. First failure -> state remains CLOSED
    with pytest.raises(ConnectionRefusedError):
        await breaker.call(fail_op)
    assert breaker.state == "CLOSED"

    # 2. Second failure -> trips OPEN
    with pytest.raises(ConnectionRefusedError):
        await breaker.call(fail_op)
    assert breaker.state == "OPEN"

    # 3. Next call blocked immediately without executing
    with pytest.raises(CircuitBreakerOpenError):
        await breaker.call(fail_op)

    # 4. Wait for recovery timeout -> transitions to HALF_OPEN
    await asyncio.sleep(0.12)
    assert breaker.can_execute() is True

    # 5. Successful calls reset to CLOSED
    async def success_op():
        return "success"

    await breaker.call(success_op)
    await breaker.call(success_op)
    assert breaker.state == "CLOSED"


@pytest.mark.asyncio
async def test_cache_graceful_degradation_redis_down():
    with patch("app.core.cache.get_redis", return_value=None):
        _MEMORY_CACHE.clear()

        call_counter = 0

        @cached(ttl_seconds=60, prefix="test_degrade")
        async def fetch_expensive_data(param: str):
            nonlocal call_counter
            call_counter += 1
            return {"data": param, "count": call_counter}

        # 1. First invocation: populates in-memory cache
        res1 = await fetch_expensive_data("foo")
        assert res1["data"] == "foo"
        assert res1["count"] == 1
        assert call_counter == 1

        # 2. Second invocation: hits in-memory cache without redis
        res2 = await fetch_expensive_data("foo")
        assert res2["count"] == 1
        assert call_counter == 1


def test_malformed_json_fallback_handling():
    # Valid markdown json
    res1 = clean_and_extract_json('```json\n{"skills": ["Python"]}\n```')
    assert res1 == {"skills": ["Python"]}

    # Malformed text without braces
    res2 = clean_and_extract_json("I am an LLM and I cannot return JSON.")
    assert res2 == {}

    # Truncated broken JSON
    res3 = clean_and_extract_json('{"skills": ["Python", "Java"')
    assert res3 == {}


@pytest.mark.asyncio
async def test_source_circuit_breaker_isolation():
    service = JobIngestionService()
    failing_source = MagicMock(spec=JobSource)
    failing_source.source_name = "failing_crawl_source"
    failing_source.search = AsyncMock(side_effect=TimeoutError("Connection timed out to job board"))

    # Trip breaker for this source
    breaker = get_circuit_breaker("source:failing_crawl_source", failure_threshold=2, recovery_timeout_sec=10.0)
    breaker.state = "OPEN"
    breaker.last_failure_time = 9999999999.0

    mock_db = AsyncMock()
    result = await service.ingest_source(mock_db, failing_source)
    assert result["status"] == "degraded_circuit_open"
    assert result["saved_canonical"] == 0


@pytest.mark.asyncio
async def test_dead_letter_quarantine_on_savepoint_error():
    DEAD_LETTER_QUARANTINE.clear()
    service = JobIngestionService()

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    corrupt_job = NormalizedJob(
        title="Corrupted Test Job",
        normalized_title="software engineer",
        role_category="BACKEND",
        company_name="Acme Inc",
        normalized_company="acme inc",
        source="test_source",
        source_job_id="test_123",
        source_url="https://example.com/jobs/123",
        application_url="https://example.com/jobs/123/apply",
        job_hash="corrupted_hash_123",
        description="Engineering role with Python and FastAPI",
        location="Remote",
        normalized_location="remote",
        remote_type="REMOTE",
        employment_type="FULL_TIME",
        posted_at=now,
        posted_at_confidence="HIGH",
    )

    # Ingest with broken session that raises inside begin_nested savepoint
    class BrokenSavepoint:
        async def __aenter__(self):
            raise RuntimeError("DB Constraint Failure")
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    mock_db = AsyncMock()
    mock_db.begin_nested = MagicMock(return_value=BrokenSavepoint())

    # Mock source to return 1 raw job that normalizes to corrupt_job
    source = MagicMock(spec=JobSource)
    source.source_name = "test_source"
    raw_job = RawJob(
        source="test_source",
        source_job_id="test_123",
        title="Corrupted Test Job",
        company_name="Acme Inc",
        description="Engineering role with Python and FastAPI",
        source_url="https://example.com/jobs/123",
        raw_payload={},
    )
    source.search = AsyncMock(return_value=[raw_job])
    source.normalize = AsyncMock(return_value=corrupt_job)

    # Ensure breaker is closed
    breaker = get_circuit_breaker("source:test_source")
    breaker.state = "CLOSED"

    await service.ingest_source(mock_db, source)
    assert len(DEAD_LETTER_QUARANTINE) >= 1
    assert DEAD_LETTER_QUARANTINE[-1]["title"] == "Corrupted Test Job"
    assert "DB Constraint Failure" in DEAD_LETTER_QUARANTINE[-1]["error"]
