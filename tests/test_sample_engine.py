import pytest
from app.database import async_session_factory
from app.services.job_service import search_jobs_db
from app.sources.adapters.sample import SampleJobAdapter
from app.sources.base import JobSearchQuery
from app.sources.registry import SourceRegistry


@pytest.mark.asyncio
async def test_sample_adapter_search_and_health():
    adapter = SampleJobAdapter()
    assert await adapter.health_check() is True

    # Search without filters
    all_raw = await adapter.search(JobSearchQuery(limit=10))
    assert len(all_raw) == 10

    # Search with role filter
    ai_raw = await adapter.search(JobSearchQuery(roles=["AI Engineer"]))
    assert len(ai_raw) >= 1
    for r in ai_raw:
        assert "ai" in r.title.lower() or "ai" in r.description.lower()


@pytest.mark.asyncio
async def test_sample_adapter_normalization():
    adapter = SampleJobAdapter()
    raw_list = await adapter.search(JobSearchQuery(limit=1))
    assert len(raw_list) == 1

    norm = await adapter.normalize(raw_list[0])
    assert norm.normalized_title != ""
    assert norm.role_category != ""
    assert norm.normalized_location != ""
    assert norm.job_hash != ""
    assert norm.quality_score > 0.0


@pytest.mark.asyncio
async def test_source_registry_isolation():
    registry = SourceRegistry()
    adapter = SampleJobAdapter()
    registry.register(adapter)

    results, counts = await registry.search_all(JobSearchQuery(limit=5))
    assert len(results) == 5
    assert counts["sample"] == 5


@pytest.mark.asyncio
async def test_fresh_job_db_search_seeded():
    """Verify seeded jobs in PostgreSQL can be queried strictly within 24h freshness."""
    async with async_session_factory() as db:
        fresh_jobs = await search_jobs_db(db, freshness_hours=24, limit=20)
        assert len(fresh_jobs) > 0

        # All returned jobs must have age <= 24.0 hours
        for j in fresh_jobs:
            assert j["age_hours"] is not None
            assert j["age_hours"] <= 24.0
            assert j["application_url"].startswith("http")
