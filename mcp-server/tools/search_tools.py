import sys
from pathlib import Path
from typing import Any

backend_dir = Path(__file__).resolve().parent.parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database import async_session_factory
from app.services.job_service import (
    get_search_history,
    record_search_query,
    search_jobs_db,
)
from app.services.user_service import get_or_create_default_user


async def handle_search_jobs(
    query: str | None = None,
    roles: list[str] | None = None,
    locations: list[str] | None = None,
    experience_min: int | None = None,
    experience_max: int | None = None,
    freshness_hours: int = 24,
    include_remote: bool = True,
    limit: int = 20,
) -> dict[str, Any]:
    """
    Searches for jobs matching criteria.
    Backend strictly enforces freshness (only jobs <= freshness_hours).
    """
    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)

        jobs = await search_jobs_db(
            db=db,
            query=query,
            roles=roles,
            locations=locations,
            experience_min=experience_min,
            experience_max=experience_max,
            freshness_hours=freshness_hours,
            include_remote=include_remote,
            limit=limit,
        )

        structured_q = {
            "query": query,
            "roles": roles,
            "locations": locations,
            "experience_min": experience_min,
            "experience_max": experience_max,
            "freshness_hours": freshness_hours,
            "include_remote": include_remote,
        }

        # Record search
        await record_search_query(
            db=db,
            user_id=user.id,
            query_text=query,
            structured_query=structured_q,
            sources_used=["database"],
            total_discovered=len(jobs),
            filtered_by_freshness=0,
            deduplicated=0,
            matched=len(jobs),
            fresh_results=len(jobs),
        )

        return {
            "fresh_jobs_found": len(jobs),
            "freshness_window_hours": freshness_hours,
            "timezone": "Asia/Kolkata",
            "jobs": jobs,
            "note": "Only jobs posted within the freshness window are returned. All links open original application pages.",
        }


async def handle_get_search_history(limit: int = 10) -> dict[str, Any]:
    """Retrieves recent search queries and their discovery statistics."""
    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)
        history = await get_search_history(db, user.id, limit=limit)
        return {"searches": history, "count": len(history)}
