import time
from fastapi import APIRouter, Depends, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import get_db

router = APIRouter(tags=["Health"])


@router.get("/health")
async def liveness_probe(db: AsyncSession = Depends(get_db)):
    """
    Liveness & basic health probe (backwards-compatible with tests & monitoring).
    Returns 200 OK immediately with basic connectivity indicators.
    """
    db_connected = False
    pgvector_ready = False

    try:
        result = await db.execute(text("SELECT 1;"))
        if result.scalar() == 1:
            db_connected = True

        ext_result = await db.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector';")
        )
        if ext_result.scalar() == "vector":
            pgvector_ready = True
    except Exception:
        db_connected = False
        pgvector_ready = False

    from app.core.redis import get_redis
    redis_client = await get_redis()
    redis_connected = False
    if redis_client is not None:
        try:
            await redis_client.ping()
            redis_connected = True
        except Exception:
            redis_connected = False

    core_ok = db_connected and pgvector_ready
    return {
        "status": "ok" if core_ok else "degraded",
        "service": "ai-job-agent-backend",
        "database": "connected" if db_connected else "disconnected",
        "pgvector": pgvector_ready,
        "redis": "connected" if redis_connected else "disconnected",
        "timestamp": time.time(),
    }


@router.get("/ready")
async def readiness_probe(db: AsyncSession = Depends(get_db)):
    """
    Deep readiness probe checking core dependencies:
    - PostgreSQL connectivity
    - pgvector extension availability
    - Redis connectivity & ping
    - LLM provider reachability
    - Crawlers availability
    """
    components: dict[str, dict] = {}
    is_ready = True

    # 1. Database & pgvector
    db_ok = False
    pgv_ok = False
    db_latency_ms = None
    t0 = time.perf_counter()
    try:
        res = await db.execute(text("SELECT 1;"))
        if res.scalar() == 1:
            db_ok = True
        ext_res = await db.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector';")
        )
        if ext_res.scalar() == "vector":
            pgv_ok = True
        db_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    except Exception as e:
        db_ok = False
        pgv_ok = False
        components["database"] = {"status": "error", "error": str(e)}

    if db_ok:
        components["database"] = {
            "status": "ok",
            "pgvector": "installed" if pgv_ok else "missing",
            "latency_ms": db_latency_ms,
        }
    if not (db_ok and pgv_ok):
        is_ready = False

    # 2. Redis
    from app.core.redis import get_redis
    redis_client = await get_redis()
    if redis_client is not None:
        try:
            t0 = time.perf_counter()
            await redis_client.ping()
            latency = round((time.perf_counter() - t0) * 1000, 2)
            components["redis"] = {"status": "ok", "latency_ms": latency}
        except Exception as e:
            components["redis"] = {"status": "degraded", "error": str(e)}
    else:
        components["redis"] = {"status": "offline", "note": "redis not initialized"}

    # 3. LLM Provider Reachability
    try:
        from app.intelligence.llm_provider import get_llm_provider
        provider = get_llm_provider()
        llm_diag = await provider.test_connection()
        components["llm_provider"] = {
            "status": "ok" if llm_diag.get("reachable") else "degraded",
            "provider": llm_diag.get("provider", settings.LLM_PROVIDER),
            "model": llm_diag.get("model", getattr(provider, "model", "unknown")),
            "latency_ms": llm_diag.get("latency_ms"),
            "reachable": llm_diag.get("reachable", False),
        }
    except Exception as e:
        components["llm_provider"] = {"status": "degraded", "error": str(e)}

    # 4. Sources / Crawlers Registry
    try:
        from app.sources.registry import source_registry
        sources_status = {
            "internshala": settings.SOURCE_INTERNSHALA_ENABLED,
            "naukri": settings.SOURCE_NAUKRI_ENABLED,
            "linkedin": settings.SOURCE_LINKEDIN_ENABLED,
            "crawl4ai": settings.CRAWL4AI_ENABLED,
        }
        components["sources"] = {
            "status": "ok",
            "enabled": sources_status,
        }
    except Exception as e:
        components["sources"] = {"status": "degraded", "error": str(e)}

    return {
        "status": "ready" if is_ready else "degraded",
        "components": components,
    }


@router.get("/metrics")
async def metrics_endpoint(format: str = "json"):
    """
    Exposes operational metrics.
    format='json' (default): Structured JSON dictionary
    format='prometheus': Prometheus text exposition format
    """
    from app.core.logging import metrics
    if format == "prometheus":
        return PlainTextResponse(metrics.generate_prometheus(), media_type="text/plain; version=0.0.4")
    return metrics.get_summary()
