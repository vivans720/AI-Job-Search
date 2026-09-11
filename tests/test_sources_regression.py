import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient

from app.sources.registry import get_source_registry, reset_registry
from app.sources.base import JobSearchQuery, RawJob


@pytest.mark.asyncio
async def test_regression_existing_sources_registered():
    """Ensure Internshala, Naukri, and LinkedIn are present and enabled."""
    reset_registry()
    registry = get_source_registry()

    for name in ["internshala", "naukri", "linkedin"]:
        src = registry.get_source(name)
        assert src is not None, f"Expected {name} to be registered in SourceRegistry"
        assert src.enabled is True, f"Expected {name} to be enabled"

    # Indeed, Glassdoor, Wellfound, and Cutshort removed - not in registry
    assert registry.get_source("indeed") is None
    assert registry.get_source("glassdoor") is None
    assert registry.get_source("wellfound") is None
    assert registry.get_source("cutshort") is None


@pytest.mark.asyncio
async def test_sync_api_supports_new_sources(async_client: AsyncClient):
    """Verifies that /jobs/sync accepts active sources and all."""
    mock_stats = {
        "source": "linkedin",
        "total_discovered": 10,
        "fresh_jobs": 5,
        "canonical_saved": 3,
        "updated_existing": 0,
        "saved_jobs": 3,
        "saved_internships": 0,
        "sources_synced": ["linkedin"],
    }

    with patch(
        "app.sources.registry.SourceRegistry.sync_source_isolated",
        new_callable=AsyncMock,
        return_value=mock_stats,
    ):
        # 1. Test linkedin
        resp = await async_client.post("/api/v1/jobs/sync?source=linkedin")
        assert resp.status_code == 200
        data = resp.json()
        assert "linkedin" in data["sources_synced"]

        # 2. Test all
        resp = await async_client.post("/api/v1/jobs/sync?source=all")
        assert resp.status_code == 200

        # 3. Test removed indeed returns 404
        resp_indeed = await async_client.post("/api/v1/jobs/sync?source=indeed")
        assert resp_indeed.status_code == 404

        # 4. Test removed cutshort returns 404
        resp_cutshort = await async_client.post("/api/v1/jobs/sync?source=cutshort")
        assert resp_cutshort.status_code == 404


@pytest.mark.asyncio
async def test_sources_health_includes_crawler_infrastructure(async_client: AsyncClient):
    """Verifies that /sources/health includes infrastructure status."""
    with patch(
        "app.sources.registry.SourceRegistry.health_check_all",
        new_callable=AsyncMock,
        return_value={"internshala": True, "naukri": True, "linkedin": True},
    ):
        resp = await async_client.get("/api/v1/sources/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("ok", "degraded")
        assert "linkedin" in data["sources"]
        assert "internshala" in data["sources"]
        assert "naukri" in data["sources"]
        assert "indeed" not in data["sources"]
        assert "infrastructure" in data
        crawl4ai = data["infrastructure"]["crawl4ai"]
        assert isinstance(crawl4ai, dict)
        for key in ("installed", "enabled", "healthy", "provider", "live", "used_by"):
            assert key in crawl4ai
        # Verify Crawl4AI used_by matches active shared adapters
        assert "linkedin" in crawl4ai.get("used_by", [])