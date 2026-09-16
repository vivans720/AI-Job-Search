import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.queue_service import QueueService, TaskJob


@pytest.mark.asyncio
async def test_queue_service_progress_tracking():
    mock_redis = AsyncMock()
    stored_data = {}

    async def mock_set(key, val, ex=None):
        stored_data[key] = val

    async def mock_get(key):
        return stored_data.get(key)

    mock_redis.set.side_effect = mock_set
    mock_redis.get.side_effect = mock_get

    with patch("app.services.queue_service.get_redis", return_value=mock_redis):
        qs = QueueService()
        job_id = "test-job-progress-1"

        # Update status with per-source progress
        progress_data = {
            "linkedin": {"status": "running", "discovered": 15, "saved": 4},
            "naukri": {"status": "pending", "discovered": 0, "saved": 0},
        }
        await qs.set_job_status(job_id, status="running", progress=progress_data)

        # Retrieve status
        status = await qs.get_job_status(job_id)
        assert status is not None
        assert status["status"] == "running"
        assert status["progress"]["linkedin"]["discovered"] == 15
        assert status["progress"]["linkedin"]["saved"] == 4
        assert status["progress"]["naukri"]["status"] == "pending"


@pytest.mark.asyncio
async def test_source_schedule_api_endpoint():
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    with patch("app.services.scheduler_service.scheduler_service.get_schedule_info", new_callable=AsyncMock) as mock_info:
        mock_info.return_value = {
            "auto_sync_enabled": True,
            "sync_interval_hours": 12,
            "last_auto_sync_at": None,
            "next_run_at": "2026-09-12T12:00:00Z",
            "seconds_until_next_run": 3600,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.get("/api/v1/sources/schedule")
            assert res.status_code == 200
            data = res.json()
            assert data["auto_sync_enabled"] is True
            assert data["sync_interval_hours"] == 12


@pytest.mark.asyncio
async def test_queue_service_cancellation():
    mock_redis = AsyncMock()
    stored_data = {}

    async def mock_set(key, val, ex=None):
        stored_data[key] = val

    async def mock_get(key):
        return stored_data.get(key)

    mock_redis.set.side_effect = mock_set
    mock_redis.get.side_effect = mock_get

    with patch("app.services.queue_service.get_redis", return_value=mock_redis):
        qs = QueueService()
        job_id = "test-job-cancel-1"

        assert not await qs.is_job_cancelled(job_id)
        ok = await qs.cancel_job(job_id)
        assert ok is True
        assert await qs.is_job_cancelled(job_id)

        status = await qs.get_job_status(job_id)
        assert status is not None
        assert status["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_job_sync_api_endpoint():
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    with patch("app.services.queue_service.task_queue.get_job_status", new_callable=AsyncMock) as mock_status, \
         patch("app.services.queue_service.task_queue.cancel_job", new_callable=AsyncMock) as mock_cancel:
        mock_status.return_value = {"job_id": "test-job-123", "status": "running"}
        mock_cancel.return_value = True

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.post("/api/v1/jobs/sync/cancel/test-job-123")
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "cancelled"
            assert data["job_id"] == "test-job-123"
