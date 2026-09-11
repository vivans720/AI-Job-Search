import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_sources_health_endpoint(async_client: AsyncClient):
    with patch(
        "app.sources.registry.SourceRegistry.health_check_all",
        new_callable=AsyncMock,
        return_value={"internshala": True, "naukri": True, "x": True},
    ):
        resp = await async_client.get("/api/v1/sources/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["sources"]["internshala"] is True
        assert data["sources"]["naukri"] is True
        assert data["sources"]["x"] is True


@pytest.mark.asyncio
async def test_sources_health_degraded_endpoint(async_client: AsyncClient):
    with patch(
        "app.sources.registry.SourceRegistry.health_check_all",
        new_callable=AsyncMock,
        return_value={"internshala": True, "naukri": False, "x": True},
    ):
        resp = await async_client.get("/api/v1/sources/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["sources"]["naukri"] is False


@pytest.mark.asyncio
async def test_sources_history_endpoint(async_client: AsyncClient):
    sample_logs = [
        {
            "timestamp": "2026-09-05T10:00:00Z",
            "source": "internshala",
            "total_discovered": 15,
            "canonical_saved": 5,
        }
    ]
    with patch("app.api.v1.sources.get_recent_sync_logs", return_value=sample_logs):
        resp = await async_client.get("/api/v1/sources/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["history"][0]["source"] == "internshala"
