import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.models.agent_activity import AgentRun, AgentEvent

logger = structlog.get_logger(__name__)


class AgentActivityService:
    @staticmethod
    async def start_run(
        db: AsyncSession,
        user_id: uuid.UUID,
        trigger: str = "chat",
        summary: Optional[str] = None,
        metrics: Optional[dict[str, Any]] = None,
    ) -> AgentRun:
        run = AgentRun(
            user_id=user_id,
            status="running",
            trigger=trigger,
            summary=summary or "Agent session initialized",
            metrics=metrics or {},
            created_at=datetime.now(timezone.utc),
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)

        # Broadcast run started
        await AgentActivityService._publish_event(
            run_id=str(run.id),
            event_type="status_update",
            data={
                "run_id": str(run.id),
                "status": run.status,
                "trigger": run.trigger,
                "summary": run.summary,
                "created_at": run.created_at.isoformat(),
            },
        )
        return run

    @staticmethod
    async def log_event(
        db: AsyncSession,
        run_id: uuid.UUID,
        action_summary: str,
        event_type: str = "status_update",
        tool_name: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
        duration_ms: Optional[int] = None,
    ) -> AgentEvent:
        event = AgentEvent(
            run_id=run_id,
            event_type=event_type,
            tool_name=tool_name,
            action_summary=action_summary,
            payload=payload or {},
            duration_ms=duration_ms,
            created_at=datetime.now(timezone.utc),
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)

        # Broadcast event
        await AgentActivityService._publish_event(
            run_id=str(run_id),
            event_type=event_type,
            data={
                "id": str(event.id),
                "run_id": str(run_id),
                "event_type": event.event_type,
                "tool_name": event.tool_name,
                "action_summary": event.action_summary,
                "payload": event.payload,
                "duration_ms": event.duration_ms,
                "created_at": event.created_at.isoformat(),
            },
        )
        return event

    @staticmethod
    async def complete_run(
        db: AsyncSession,
        run_id: uuid.UUID,
        summary: Optional[str] = None,
        metrics: Optional[dict[str, Any]] = None,
    ) -> Optional[AgentRun]:
        stmt = select(AgentRun).where(AgentRun.id == run_id)
        result = await db.execute(stmt)
        run = result.scalar_one_or_none()
        if not run:
            return None

        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        if summary:
            run.summary = summary
        if metrics:
            merged = dict(run.metrics or {})
            merged.update(metrics)
            run.metrics = merged

        await db.commit()
        await db.refresh(run)

        await AgentActivityService._publish_event(
            run_id=str(run.id),
            event_type="status_update",
            data={
                "run_id": str(run.id),
                "status": run.status,
                "summary": run.summary,
                "metrics": run.metrics,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            },
        )
        return run

    @staticmethod
    async def fail_run(
        db: AsyncSession,
        run_id: uuid.UUID,
        error_message: str,
    ) -> Optional[AgentRun]:
        stmt = select(AgentRun).where(AgentRun.id == run_id)
        result = await db.execute(stmt)
        run = result.scalar_one_or_none()
        if not run:
            return None

        run.status = "failed"
        run.completed_at = datetime.now(timezone.utc)
        run.summary = f"Failed: {error_message}"

        await db.commit()
        await db.refresh(run)

        await AgentActivityService._publish_event(
            run_id=str(run.id),
            event_type="status_update",
            data={
                "run_id": str(run.id),
                "status": run.status,
                "summary": run.summary,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            },
        )
        return run

    @staticmethod
    async def get_run(db: AsyncSession, run_id: uuid.UUID) -> Optional[AgentRun]:
        stmt = select(AgentRun).where(AgentRun.id == run_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_runs(
        db: AsyncSession,
        user_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> list[AgentRun]:
        stmt = (
            select(AgentRun)
            .where(AgentRun.user_id == user_id)
            .order_by(AgentRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_run_events(
        db: AsyncSession, run_id: uuid.UUID
    ) -> list[AgentEvent]:
        stmt = (
            select(AgentEvent)
            .where(AgentEvent.run_id == run_id)
            .order_by(AgentEvent.created_at.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def _publish_event(run_id: str, event_type: str, data: dict[str, Any]) -> None:
        try:
            redis = await get_redis()
            if redis:
                channel = f"agent:run:{run_id}"
                message = json.dumps({"event_type": event_type, "data": data})
                await redis.publish(channel, message)
        except Exception as e:
            logger.warning("agent_event_publish_failed", error=str(e), run_id=run_id)
