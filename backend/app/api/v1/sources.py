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
    all_healthy = all(health_results.values()) if health_results else True

    try:
        from app.crawling.crawler_registry import get_crawler_capability
        capability = await get_crawler_capability()
    except Exception:
        capability = {"installed": False, "enabled": False, "healthy": False, "provider": "unknown", "live": False, "used_by": []}

    return {
        "status": "ok" if all_healthy else "degraded",
        "sources": health_results,
        "infrastructure": {
            "crawl4ai": capability,
        },
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
