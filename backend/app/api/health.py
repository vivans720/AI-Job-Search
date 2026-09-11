from fastapi import APIRouter, Depends
from sqlalchemy import text
from app.config import settings
from app.database import get_db

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None


router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    db_connected = False
    pgvector_ready = False
    redis_connected = False

    try:
        result = await db.execute(text("SELECT 1;"))
        if result.scalar() == 1:
            db_connected = True

        ext_result = await db.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector';")
        )
        if ext_result.scalar() == "vector":
            pgvector_ready = True
    except Exception as e:
        db_connected = False
        pgvector_ready = False

    from app.core.redis import get_redis
    r = await get_redis()
    if r is not None:
        try:
            await r.ping()
            redis_connected = True
        except Exception:
            redis_connected = False
    else:
        redis_connected = False


    core_ok = db_connected and pgvector_ready
    return {
        "status": "ok" if core_ok else "degraded",
        "database": "connected" if db_connected else "disconnected",
        "pgvector": pgvector_ready,
        "redis": "connected" if redis_connected else "disconnected",
    }


