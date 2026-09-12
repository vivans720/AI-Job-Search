import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app
from app.database import get_db


@pytest.mark.asyncio
async def test_api_health_endpoints():
    mock_db = AsyncMock()
    mock_res_1 = MagicMock()
    mock_res_1.scalar.return_value = 1
    mock_res_ext = MagicMock()
    mock_res_ext.scalar.return_value = "vector"
    mock_db.execute.side_effect = [mock_res_1, mock_res_ext]

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Health probe
            resp = await client.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] in ["ok", "healthy"]
            assert data["database"] == "connected"
            assert data["pgvector"] is True

            # 2. LLM Health probe
            resp_llm = await client.get("/api/v1/health/llm")
            assert resp_llm.status_code == 200
            llm_data = resp_llm.json()
            assert "provider" in llm_data

            # 3. Sources health
            resp_sources = await client.get("/api/v1/sources/health")
            assert resp_sources.status_code == 200

            # 4. Sources schedule
            with patch("app.services.scheduler_service.scheduler_service.get_schedule_info", new_callable=AsyncMock) as mock_sched:
                mock_sched.return_value = {
                    "auto_sync_enabled": True,
                    "sync_interval_hours": 12,
                    "last_auto_sync_at": None,
                    "next_run_at": "2026-09-12T12:00:00Z",
                    "seconds_until_next_run": 3600,
                }
                resp_sched = await client.get("/api/v1/sources/schedule")
                assert resp_sched.status_code == 200
    finally:
        app.dependency_overrides.clear()
