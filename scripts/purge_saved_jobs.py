import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import delete
from app.database import async_session_factory
from app.models.saved_job import SavedJob
from app.core.redis import get_redis


async def purge_saved_jobs():
    print("Connecting to database...")
    async with async_session_factory() as session:
        stmt = delete(SavedJob)
        result = await session.execute(stmt)
        await session.commit()
        deleted_count = result.rowcount
        print(f"Purged {deleted_count} record(s) from saved_jobs table.")

    try:
        redis = await get_redis()
        if redis:
            keys = await redis.keys("cache:dashboard:*")
            if keys:
                await redis.delete(*keys)
                print(f"Flushed {len(keys)} dashboard cache key(s) from Redis.")
    except Exception as e:
        print(f"Redis cache flush note: {e}")

    print("Saved jobs purge complete.")


if __name__ == "__main__":
    asyncio.run(purge_saved_jobs())
