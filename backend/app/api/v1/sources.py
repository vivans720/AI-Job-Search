from typing import Any
from fastapi import APIRouter
import structlog

from app.sources.registry import get_source_registry
from app.utils.sync_logger import get_recent_sync_logs

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/sources", tags=["Sources"])


@router.get("/health")
async def get_sources_health() -> dict[str, Any]:
    """
    Probes all enabled job source adapters and returns their live health / connectivity status.
    """
    registry = get_source_registry()
    health_results = await registry.health_check_all()
    source_details = {}
    from app.sources.rate_limiter import SOURCE_RATE_LIMITS
    for name, src in registry._sources.items():
        metrics = src.get_metrics().model_dump() if hasattr(src, "get_metrics") else {}
        limits = SOURCE_RATE_LIMITS.get(name, SOURCE_RATE_LIMITS.get("default", {}))
        source_details[name] = {
            "healthy": health_results.get(name, False),
            "enabled": src.enabled,
            "status": getattr(src, "status", "ok"),
            "last_error": getattr(src, "last_error", None),
            "last_error_category": getattr(src, "last_error_category", None),
            "rate_limit": f"{limits.get('rate', 0)} req/{int(limits.get('per', 60))}s",
            "metrics": metrics,
        }

    all_healthy = all(health_results.values()) if health_results else False
    from app.config import settings
    capability = settings.CRAWL4AI_ENABLED

    return {
        "status": "ok" if all_healthy else "degraded",
        "sources": health_results,
        "details": source_details,
        "infrastructure": {
            "crawl4ai": capability,
        },
    }


@router.get("/schedule")
async def get_schedule_status() -> dict[str, Any]:
    """
    Returns automated sync schedule status, interval, and next scheduled execution.
    """
    from app.services.scheduler_service import scheduler_service
    return await scheduler_service.get_schedule_info()


@router.post("/schedule/trigger")
async def trigger_scheduled_sync_now() -> dict[str, Any]:
    """
    Manually triggers the scheduler's sync routine immediately.
    """
    from app.services.scheduler_service import scheduler_service
    enqueued = await scheduler_service.check_and_trigger_scheduled_sync()
    info = await scheduler_service.get_schedule_info()
    return {
        "triggered": enqueued,
        "schedule": info,
        "message": "Scheduled sync triggered." if enqueued else "Sync not due or auto-sync disabled.",
    }


@router.get("/history")
async def get_sync_history(limit: int = 20) -> dict[str, Any]:
    """
    Returns recent sync run audit events from data/sync_log.jsonl.
    """
    logs = get_recent_sync_logs(limit=limit)
    return {
        "count": len(logs),
        "history": logs,
    }
