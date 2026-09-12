import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock
from app.main import app
from app.database import get_db
from app.core.logging import metrics, get_correlation_id, set_correlation_id
from app.services.job_ingestion_service import JobIngestionService
from app.sources.base import JobSource, RawJob, NormalizedJob, JobSearchQuery


@pytest.mark.asyncio
async def test_health_liveness():
    """Verify /health probe (both degraded without DB and ok with DB)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ["ok", "degraded"]
        assert "ai-job-agent-backend" in data["service"]


@pytest.mark.asyncio
async def test_ready_endpoint():
    """Verify /ready deep dependency probe."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "components" in data
        comps = data["components"]
        assert "database" in comps
        assert "redis" in comps
        assert "llm_provider" in comps
        assert "sources" in comps


@pytest.mark.asyncio
async def test_request_id_tracing_middleware():
    """Verify X-Request-ID correlation header propagation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Without incoming header -> generates one
        resp1 = await client.get("/health")
        assert "X-Request-ID" in resp1.headers
        assert len(resp1.headers["X-Request-ID"]) > 10

        # 2. With incoming header -> preserves it
        custom_id = "test-custom-trace-uuid-12345"
        resp2 = await client.get("/health", headers={"X-Request-ID": custom_id})
        assert resp2.headers["X-Request-ID"] == custom_id


@pytest.mark.asyncio
async def test_metrics_endpoints():
    """Verify /metrics JSON and Prometheus text outputs."""
    # Increment metric directly to guarantee non-empty data
    metrics.inc("jobs_discovered_total", 5, source="test_source")
    metrics.inc("jobs_deduplicated_total", 2, source="test_source")
    metrics.observe("sync_duration_seconds", 1.25, source="test_source")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # JSON format
        resp_json = await client.get("/metrics")
        assert resp_json.status_code == 200
        data = resp_json.json()
        assert "counters" in data
        assert "histograms" in data
        assert any("jobs_discovered_total" in k for k in data["counters"])

        # Prometheus format
        resp_prom = await client.get("/metrics?format=prometheus")
        assert resp_prom.status_code == 200
        assert "jobs_discovered_total" in resp_prom.text
        assert "sync_duration_seconds" in resp_prom.text
