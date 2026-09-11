import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, Optional
import structlog
from sqlalchemy import select
from app.database import async_session_factory
from app.models.preference import Preference
from app.services.queue_service import task_queue

logger = structlog.get_logger(__name__)


class SchedulerService:
    """
    Automated Ingestion Scheduler.
    Polls user sync preferences and dispatches scheduled sync tasks via task_queue.
    Supports intervals: 6, 12, 24 hours.
    """

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._check_interval_seconds = 60  # check every minute

    def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("scheduler_service_started")

    def stop(self):
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("scheduler_service_stopped")

    async def _run_loop(self):
        while self._running:
            try:
                await self.check_and_trigger_scheduled_sync()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("scheduler_check_error", error=str(e))

            try:
                await asyncio.sleep(self._check_interval_seconds)
            except asyncio.CancelledError:
                break

    async def check_and_trigger_scheduled_sync(self) -> bool:
        """
        Queries preferences for active auto-sync. If time since last sync exceeds interval,
        enqueues a fresh sync job.
        """
        async with async_session_factory() as db:
            result = await db.execute(select(Preference).limit(1))
            pref = result.scalar_one_or_none()
            if not pref:
                return False

            if not pref.auto_sync_enabled or pref.sync_interval_hours <= 0:
                return False

            now = datetime.now(timezone.utc)
            interval_delta = timedelta(hours=pref.sync_interval_hours)

            if pref.last_auto_sync_at is not None:
                next_due = pref.last_auto_sync_at + interval_delta
                if now < next_due:
                    return False

            logger.info(
                "scheduler_triggering_auto_sync",
                sync_interval_hours=pref.sync_interval_hours,
                last_sync=str(pref.last_auto_sync_at),
            )

            # Update last_auto_sync_at timestamp
            pref.last_auto_sync_at = now
            await db.commit()

            # Enqueue task
            job_id = await task_queue.enqueue(
                task_type="sync_source",
                payload={"source": "all", "freshness_hours": pref.freshness_hours or 24},
            )
            if not job_id:
                logger.warning("scheduler_auto_sync_enqueue_failed_redis_offline")
            else:
                logger.info("scheduler_auto_sync_enqueued", job_id=job_id)
            return True

    async def get_schedule_info(self) -> dict[str, Any]:
        """Returns schedule configuration and next run timing for UI."""
        async with async_session_factory() as db:
            result = await db.execute(select(Preference).limit(1))
            pref = result.scalar_one_or_none()
            if not pref:
                return {
                    "auto_sync_enabled": True,
                    "sync_interval_hours": 24,
                    "last_auto_sync_at": None,
                    "next_run_at": None,
                    "seconds_until_next_run": None,
                }

            now = datetime.now(timezone.utc)
            next_run_at = None
            seconds_until = None
            if pref.auto_sync_enabled and pref.sync_interval_hours > 0:
                if pref.last_auto_sync_at:
                    next_run_dt = pref.last_auto_sync_at + timedelta(hours=pref.sync_interval_hours)
                    next_run_at = next_run_dt.isoformat()
                    seconds_until = max(0, int((next_run_dt - now).total_seconds()))
                else:
                    next_run_at = now.isoformat()
                    seconds_until = 0

            return {
                "auto_sync_enabled": pref.auto_sync_enabled,
                "sync_interval_hours": pref.sync_interval_hours,
                "last_auto_sync_at": pref.last_auto_sync_at.isoformat() if pref.last_auto_sync_at else None,
                "next_run_at": next_run_at,
                "seconds_until_next_run": seconds_until,
            }


scheduler_service = SchedulerService()
