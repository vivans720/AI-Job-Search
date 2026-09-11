from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
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
    except Exception as e:
        return {
            "status": "degraded",
            "database": "error",
            "pgvector": False,
            "error": str(e),
        }

    status = "ok" if (db_connected and pgvector_ready) else "degraded"
    return {
        "status": status,
        "database": "connected" if db_connected else "disconnected",
        "pgvector": pgvector_ready,
    }
