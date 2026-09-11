import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from app.services.scheduler_service import SchedulerService


@pytest.mark.asyncio
async def test_scheduler_triggers_when_due():
    scheduler = SchedulerService()

    fake_pref = MagicMock()
    fake_pref.auto_sync_enabled = True
    fake_pref.sync_interval_hours = 6
    fake_pref.freshness_hours = 24
    # last run was 7 hours ago -> due now
    fake_pref.last_auto_sync_at = datetime.now(timezone.utc) - timedelta(hours=7)

    with patch("app.services.scheduler_service.async_session_factory") as mock_session_factory, \
         patch("app.services.scheduler_service.task_queue.enqueue", new_callable=AsyncMock) as mock_enqueue:
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_pref
        mock_db.execute.return_value = mock_result
        mock_session_factory.return_value.__aenter__.return_value = mock_db

        mock_enqueue.return_value = "job-uuid-123"

        triggered = await scheduler.check_and_trigger_scheduled_sync()
        assert triggered is True
        assert mock_enqueue.called
        assert fake_pref.last_auto_sync_at is not None


@pytest.mark.asyncio
async def test_scheduler_skips_when_not_due():
    scheduler = SchedulerService()

    fake_pref = MagicMock()
    fake_pref.auto_sync_enabled = True
    fake_pref.sync_interval_hours = 24
    # last run was 2 hours ago -> not due
    fake_pref.last_auto_sync_at = datetime.now(timezone.utc) - timedelta(hours=2)

    with patch("app.services.scheduler_service.async_session_factory") as mock_session_factory, \
         patch("app.services.scheduler_service.task_queue.enqueue", new_callable=AsyncMock) as mock_enqueue:
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_pref
        mock_db.execute.return_value = mock_result
        mock_session_factory.return_value.__aenter__.return_value = mock_db

        triggered = await scheduler.check_and_trigger_scheduled_sync()
        assert triggered is False
        assert not mock_enqueue.called


@pytest.mark.asyncio
async def test_scheduler_disabled():
    scheduler = SchedulerService()

    fake_pref = MagicMock()
    fake_pref.auto_sync_enabled = False
    fake_pref.sync_interval_hours = 0

    with patch("app.services.scheduler_service.async_session_factory") as mock_session_factory, \
         patch("app.services.scheduler_service.task_queue.enqueue", new_callable=AsyncMock) as mock_enqueue:
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_pref
        mock_db.execute.return_value = mock_result
        mock_session_factory.return_value.__aenter__.return_value = mock_db

        triggered = await scheduler.check_and_trigger_scheduled_sync()
        assert triggered is False
        assert not mock_enqueue.called
