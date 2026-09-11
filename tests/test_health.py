import pytest
import httpx


@pytest.mark.asyncio
async def test_health_check_endpoint(async_client: httpx.AsyncClient):
    """Verify GET /api/health returns ok with database connected and pgvector true."""
    response = await async_client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert data["pgvector"] is True


@pytest.mark.asyncio
async def test_root_health_check(async_client: httpx.AsyncClient):
    """Verify GET /health also works directly."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert data["pgvector"] is True
