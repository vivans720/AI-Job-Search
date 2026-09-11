import json
import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.database import async_session_factory
from app.models.job import Job
from app.sources.base import JobSearchQuery, RawJob, NormalizedJob, JobSource
from app.sources.registry import SourceRegistry, get_source_registry, reset_registry
from app.services.freshness_service import get_freshness_service, FreshnessService, IST
from app.services.job_ingestion_service import JobIngestionService
from app.utils.type_normalization import (
    is_nan,
    clean_text,
    clean_record_value,
    make_json_serializable,
)
from app.sources.adapters.internshala import InternshalaAdapter
from app.sources.adapters.linkedin import LinkedInAdapter
from app.utils.http_client import HTTPResult


# ==============================================================================
# 1. Type Normalization & Serialization Tests (Indeed Root Cause)
# ==============================================================================

def test_is_nan_detection():
    """Confirms float('nan') is reliably detected, while None and primitives are not."""
    assert is_nan(float("nan")) is True
    assert is_nan(None) is False
    assert is_nan(0) is False
    assert is_nan(0.0) is False
    assert is_nan("nan") is False
    assert is_nan([]) is False
    assert is_nan({}) is False


def test_clean_text_safe_stripping():
    """Confirms clean_text handles float('nan'), None, ints, floats, and strings without strip() errors."""
    assert clean_text(float("nan")) is None
    assert clean_text(None) is None
    assert clean_text("") is None
    assert clean_text("   ") is None
    assert clean_text("  Senior Python Dev  ") == "Senior Python Dev"
    assert clean_text(12345) == "12345"
    assert clean_text(0.0) == "0.0"


def test_clean_record_value_deep():
    """Confirms recursive cleaning replaces NaNs with None and preserves valid datatypes."""
    input_data = {
        "title": "Backend Engineer",
        "missing_url": float("nan"),
        "date_posted": date(2026, 9, 6),
        "tags": ["python", float("nan"), "fastapi"],
        "nested": {
            "rate": float("nan"),
            "count": 10,
            "active": True,
        },
    }
    cleaned = clean_record_value(input_data)
    assert cleaned["title"] == "Backend Engineer"
    assert cleaned["missing_url"] is None
    assert cleaned["date_posted"] == date(2026, 9, 6)
    assert cleaned["tags"] == ["python", None, "fastapi"]
    assert cleaned["nested"]["rate"] is None
    assert cleaned["nested"]["count"] == 10
    assert cleaned["nested"]["active"] is True


def test_make_json_serializable_dates_and_nans():
    """Confirms date and datetime objects are converted to ISO strings and dumpable by standard json."""
    payload = {
        "id": uuid.uuid4(),
        "today": date(2026, 9, 6),
        "now": datetime(2026, 9, 6, 10, 0, 0, tzinfo=timezone.utc),
        "bad_val": float("nan"),
        "items": [date(2026, 9, 5), {"nested_date": date(2026, 9, 4)}],
    }
    serializable = make_json_serializable(payload)
    assert serializable["today"] == "2026-09-06"
    assert "2026-09-06T10:00:00" in serializable["now"]
    assert serializable["bad_val"] is None
    assert serializable["items"][0] == "2026-09-05"
    assert serializable["items"][1]["nested_date"] == "2026-09-04"

    # Must serialize without TypeError
    dumped = json.dumps(serializable)
    assert isinstance(dumped, str)



# ==============================================================================
# 2. Database JSONB Ingestion with Date Objects (PostgreSQL Serialization Crash)
# ==============================================================================

class DummyJobSource(JobSource):
    source_name = "linkedin"
    enabled = True

    def __init__(self, raw_job: RawJob):
        self.raw_job = raw_job

    async def search(self, query: JobSearchQuery) -> list[RawJob]:
        return [self.raw_job]

    async def get_job(self, job_id: str) -> NormalizedJob | None:
        return None

    async def health_check(self) -> bool:
        return True

    async def normalize(self, raw: RawJob) -> NormalizedJob | None:
        return NormalizedJob(
            source=raw.source,
            source_job_id=raw.source_job_id,
            title=raw.title,
            normalized_title=raw.title,
            role_category="BACKEND",
            company_name=raw.company_name,
            normalized_company=raw.company_name,
            description=raw.description,
            location=raw.location,
            normalized_location=raw.location,
            remote_type=raw.remote_type,
            employment_type=raw.employment_type,
            experience_min=0,
            experience_max=1,
            application_url=raw.application_url,
            source_url=raw.source_url,
            job_hash=f"hash-{raw.source_job_id}",
            raw_data=raw.raw_payload,
            required_skills=["Django", "Python"],
            preferred_skills=["Docker"],
            posted_at=datetime.now(timezone.utc) - timedelta(hours=2),
            posted_at_raw="2 hours ago",
            posted_at_confidence="HIGH",
        )


@pytest.mark.asyncio
async def test_job_ingestion_with_date_in_raw_data():
    """
    Direct regression test for:
    TypeError: Object of type date is not JSON serializable
    during asyncpg JSONB persistence in JobIngestionService.
    """
    ingestion_service = JobIngestionService()
    test_id = f"test-date-regress-{uuid.uuid4().hex[:8]}"

    raw_job = RawJob(
        source="linkedin",
        source_job_id=test_id,
        title="Junior Django Developer",
        company_name="Date Test Corp",
        location="Pune",
        application_url=f"https://example.com/apply/{test_id}",
        source_url=f"https://linkedin.com/jobs/view/{test_id}",
        description="Fresh graduate or junior developer with 0-1 year experience in Django. We use Python, Docker, and PostgreSQL.",
        salary_raw="₹ 5,00,000",
        posted_time_raw="4 hours ago",
        raw_payload={
            "job_id": test_id,
            "date_posted": date(2026, 9, 6),  # Raw date object that caused asyncpg crash
            "scraped_at_date": date(2026, 9, 6),
            "meta": {
                "created_date": date(2026, 9, 5),
            },
        },
    )

    try:
        async with async_session_factory() as probe_conn:
            from sqlalchemy import text
            await probe_conn.execute(text("SELECT 1"))
    except (PermissionError, OSError, Exception):
        pytest.skip("Database socket not accessible in sandbox")

    async with async_session_factory() as session:
        # Step 1: Initial Ingest
        source = DummyJobSource(raw_job)
        stats = await ingestion_service.ingest_source(session, source, JobSearchQuery())
        assert stats["canonical_saved"] == 1
        assert stats["total_discovered"] == 1

        # Step 2: Fetch and verify DB record
        from sqlalchemy import select
        res = await session.execute(select(Job).where(Job.source_job_id == test_id))
        saved_job = res.scalar_one_or_none()
        assert saved_job is not None
        assert saved_job.raw_data["date_posted"] == "2026-09-06"
        assert saved_job.raw_data["meta"]["created_date"] == "2026-09-05"

        # Step 3: Re-ingest (triggers the update branch, which also serializes raw_data)
        stats2 = await ingestion_service.ingest_source(session, source, JobSearchQuery())
        assert stats2["updated_existing"] == 1

        # Cleanup
        await session.delete(saved_job)
        await session.commit()


def test_job_ingestion_service_sanitizes_raw_data_unit():
    """Unit test verifying make_json_serializable cleans dates and NaNs from raw_data."""
    raw_payload = {
        "date_posted": date(2026, 9, 6),
        "nested": {"scraped_at": date(2026, 9, 5)},
        "bad": float("nan"),
    }
    cleaned = make_json_serializable(raw_payload)
    assert cleaned["date_posted"] == "2026-09-06"
    assert cleaned["nested"]["scraped_at"] == "2026-09-05"
    assert cleaned["bad"] is None

    dumped = json.dumps(cleaned)
    assert "2026-09-06" in dumped


# ==============================================================================
# 3. Freshness Service & LinkedIn Recency Precision
# ==============================================================================

def test_freshness_service_recency_hours_precision():
    """
    Confirms '10 hours ago', '14 hours ago', '22 hours ago', '23 hours ago'
    are classified as FRESH with HIGH confidence, while > 24h are STALE.
    """
    svc = FreshnessService(freshness_hours=24)
    ref_time = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)

    # Fresh posting hours
    for h in [1, 5, 10, 14, 22, 23]:
        text = f"{h} hours ago"
        dt, conf = svc.parse_recency_string(text, reference_now=ref_time)
        assert dt is not None
        assert conf == "HIGH"
        is_fresh, reason, age = svc.evaluate_freshness(dt, conf, reference_now=ref_time)
        assert is_fresh is True, f"Failed for {text}: age={age}, reason={reason}"
        assert reason == "fresh"
        assert abs(age - h) < 0.1

    # Stale posting hours (> 24h)
    for h in [25, 30, 48]:
        text = f"{h} hours ago"
        dt, conf = svc.parse_recency_string(text, reference_now=ref_time)
        assert dt is not None
        is_fresh, reason, age = svc.evaluate_freshness(dt, conf, reference_now=ref_time)
        assert is_fresh is False
        assert "stale_age_" in reason or "low_confidence_" in reason

    # 1 day ago / 1d ago -> Rescued into fresh (<24h)
    dt_1d, conf_1d = svc.parse_recency_string("1 day ago", reference_now=ref_time)
    assert dt_1d is not None
    is_fresh_1d, _, age_1d = svc.evaluate_freshness(dt_1d, conf_1d, reference_now=ref_time)
    assert is_fresh_1d is True
    assert age_1d <= 24.0

    # 2 days ago -> Stale
    dt_2d, conf_2d = svc.parse_recency_string("2 days ago", reference_now=ref_time)
    is_fresh_2d, _, _ = svc.evaluate_freshness(dt_2d, conf_2d, reference_now=ref_time)
    assert is_fresh_2d is False


@pytest.mark.asyncio
async def test_linkedin_normalization_prioritizes_relative_recency_over_date_only():
    """
    Confirms LinkedIn cards with datetime="YYYY-MM-DD" + "14 hours ago"
    use the relative recency timestamp rather than date-only midnight (which added 23h false age).
    """
    adapter = LinkedInAdapter()
    ref_scrape = datetime(2026, 9, 6, 10, 0, 0, tzinfo=timezone.utc)

    raw = RawJob(
        source="linkedin",
        source_job_id="li-regress-14h",
        title="Software Engineer - Early Career",
        company_name="Tech India",
        location="Bengaluru, Karnataka, India",
        application_url="https://in.linkedin.com/jobs/view/4012345678",
        source_url="https://in.linkedin.com/jobs/view/4012345678",
        description="Entry level role for Python, FastAPI, and Docker engineers with 0-2 years experience. We are building microservices and hiring backend engineers in Bengaluru.",
        posted_time_raw="14 hours ago",
        scraped_at=ref_scrape,
        raw_data={
            "datetime_attr": "2026-09-05",  # Date-only attribute in HTML <time> tag
        },
    )

    norm = await adapter.normalize(raw)
    assert norm is not None
    svc = FreshnessService(freshness_hours=24)
    assert svc.is_fresh(norm.posted_at, norm.posted_at_confidence, reference_now=ref_scrape) is True
    assert norm.posted_at_confidence == "HIGH"

    # Age calculated relative to scraped_at should be exactly ~14 hours, NOT 34 hours!
    age_from_scrape = (ref_scrape - norm.posted_at).total_seconds() / 3600.0
    assert 13.5 <= age_from_scrape <= 14.5
    assert norm.scraped_at != norm.posted_at


# ==============================================================================

# ==============================================================================
# 4. Internshala ACCOUNT_HOLD Structured Block Handling
# ==============================================================================

@pytest.mark.asyncio
async def test_internshala_adapter_account_hold_clean_abort():
    """
    Confirms Internshala ACCOUNT_HOLD state:
    1. Marks adapter.status = 'blocked'
    2. Aborts search cleanly returning []
    3. Causes health_check() to return False
    4. Does not throw unhandled exception
    """
    adapter = InternshalaAdapter()
    query = JobSearchQuery(roles=["Python Developer"])

    with patch.object(adapter, "_fetch_url", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = "Your account has been put on hold due to security policies."
        jobs = await adapter.search(query)
        assert jobs == []
        assert adapter.status == "blocked"
        assert "ACCOUNT_HOLD" in adapter.last_error

        # Health check should now reflect blocked status
        is_healthy = await adapter.health_check()
        assert is_healthy is False


# ==============================================================================
# 6. Source Registry Multi-Source Isolation & Structured Status
# ==============================================================================

@pytest.mark.asyncio
async def test_registry_sync_all_isolated_partial_success():
    """
    Confirms sync_all_isolated reports 'partial_success' when one source succeeds
    and another source is blocked.
    """
    registry = SourceRegistry()

    # Mock Source A: Internshala (Succeeds)
    mock_internshala = MagicMock()
    mock_internshala.source_name = "internshala"
    mock_internshala.enabled = True
    mock_internshala.status = "ok"
    mock_internshala.search = AsyncMock(return_value=[])
    mock_internshala.normalize = AsyncMock(return_value=None)

    # Mock Source B: Naukri (Blocked - triggers partial_success)
    mock_naukri = MagicMock()
    mock_naukri.source_name = "naukri"
    mock_naukri.enabled = True
    mock_naukri.status = "blocked"
    mock_naukri.last_error = "Rate limited (HTTP 429)"
    mock_naukri.search = AsyncMock(return_value=[])
    mock_naukri.normalize = AsyncMock(return_value=None)

    registry.register(mock_internshala)
    registry.register(mock_naukri)

    # Ingestion mock
    mock_ingestion = MagicMock()
    async def mock_ingest(db, source, query):
        if source.source_name == "internshala":
            return {
                "source": "internshala",
                "total_discovered": 10,
                "canonical_saved": 4,
                "updated_existing": 1,
            }
        else:
            raise RuntimeError("Rate limited (HTTP 429)")
    mock_ingestion.ingest_source = AsyncMock(side_effect=mock_ingest)

    mock_db = MagicMock()
    mock_db.rollback = AsyncMock()
    query = JobSearchQuery()

    result = await registry.sync_all_isolated(mock_db, mock_ingestion, query)

    assert result["status"] == "partial_success"
    assert "internshala" in result["sources"]
    assert "naukri" in result["sources"]
    assert result["sources"]["internshala"]["status"] == "success"
    assert result["sources"]["internshala"]["discovered"] == 10
    assert result["sources"]["internshala"]["accepted"] == 5
    assert result["sources"]["naukri"]["status"] == "failed"
    assert "429" in result["sources"]["naukri"]["error"]
    assert result["total_discovered"] == 10
    assert result["canonical_saved"] == 4


@pytest.mark.asyncio
async def test_registry_sync_all_isolated_all_blocked():
    """Confirms sync_all_isolated reports 'blocked' when all sources are blocked."""
    registry = SourceRegistry()

    mock_src = MagicMock()
    mock_src.source_name = "internshala"
    mock_src.enabled = True
    mock_src.status = "blocked"
    mock_src.last_error = "ACCOUNT_HOLD"
    registry.register(mock_src)

    mock_ingestion = MagicMock()
    mock_ingestion.ingest_source = AsyncMock(return_value={"total_discovered": 0, "canonical_saved": 0, "updated_existing": 0})

    result = await registry.sync_all_isolated(MagicMock(), mock_ingestion, JobSearchQuery())
    assert result["status"] == "blocked"
    assert result["sources"]["internshala"]["status"] == "blocked"


# ==============================================================================
# 7. Jobs Sync API Contract (/api/v1/jobs/sync)
# ==============================================================================

@pytest.mark.asyncio
async def test_jobs_sync_api_structured_response_contract():
    """
    Confirms /api/v1/jobs/sync response contains:
    - 'status': one of ['success', 'partial_success', 'blocked', 'failed']
    - 'sources': dict containing per-source status and counters
    - All legacy counters for backwards compatibility
    """
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # Test with internshala single-source query
            res = await ac.post("/api/v1/jobs/sync?source=internshala")
            assert res.status_code == 200
            data = res.json()

            # Contract checks
            assert "status" in data
            assert data["status"] in ("success", "partial_success", "blocked", "failed")
            assert "sources" in data
            assert isinstance(data["sources"], dict)
            assert "internshala" in data["sources"]
            assert "status" in data["sources"]["internshala"]
            assert "discovered" in data["sources"]["internshala"]
            assert "accepted" in data["sources"]["internshala"]

            # Backwards compatibility checks
            assert "total_discovered" in data
            assert "fresh_jobs" in data
            assert "canonical_saved" in data
            assert "sources_synced" in data
            assert "source" in data
    except (PermissionError, OSError):
        pytest.skip("Database socket not accessible (e.g. running inside sandbox)")
