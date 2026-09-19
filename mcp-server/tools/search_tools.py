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

        sanitized_jobs = []
        for j in jobs:
            clean_j = dict(j)
            clean_j.pop("_entity", None)
            sanitized_jobs.append(clean_j)

        return {
            "fresh_jobs_found": len(sanitized_jobs),
            "freshness_window_hours": freshness_hours,
            "timezone": "Asia/Kolkata",
            "jobs": sanitized_jobs,
            "note": "Only jobs posted within the freshness window are returned. All links open original application pages.",
        }


async def handle_get_search_history(limit: int = 10) -> dict[str, Any]:
    """Retrieves recent search queries and their discovery statistics."""
    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)
        history = await get_search_history(db, user.id, limit=limit)
        return {"searches": history, "count": len(history)}


async def handle_semantic_search_jobs(
    query: str,
    limit: int = 10,
    freshness_hours: int = 24,
) -> dict[str, Any]:
    """
    Performs semantic vector search over jobs using pgvector cosine distance.
    Matches meaning and intent of the query rather than exact keywords.
    """
    from app.services.job_service import semantic_search_jobs_db

    async with async_session_factory() as db:
        jobs = await semantic_search_jobs_db(
            db=db,
            query=query,
            limit=limit,
            freshness_hours=freshness_hours,
        )
        return {
            "query": query,
            "results_count": len(jobs),
            "freshness_window_hours": freshness_hours,
            "jobs": jobs,
        }


async def handle_sync_jobs(
    source: str = "ALL",
    freshness_hours: int = 24,
    skills: list[str] | None = None,
) -> dict[str, Any]:
    """
    Triggers job aggregation and synchronization from supported job boards.
    Enforces rate limits and non-blocking background queue ingestion.
    """
    from app.core.rate_limiter import check_rate_limit
    from app.services.preference_service import get_or_create_preferences
    from app.services.profile_service import get_candidate_profile
    from app.services.queue_service import task_queue

    # Rate limiting on sync: max 10 sync calls per 60s
    allowed, remaining = await check_rate_limit("sync_jobs", limit=10, window_seconds=60)
    if not allowed:
        return {
            "status": "rate_limited",
            "message": "Sync rate limit exceeded. Please wait a minute before requesting another sync.",
        }

    # Allowed freshness clamp
    allowed_freshness = [1, 4, 8, 12, 16, 24]
    effective_freshness = freshness_hours
    if effective_freshness not in allowed_freshness:
        effective_freshness = min(allowed_freshness, key=lambda x: abs(x - effective_freshness))

    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)
        resolved_skills: list[str] = []

        if skills:
            resolved_skills = [s.strip().lower() for s in skills if s and s.strip()]

        if not resolved_skills:
            prefs = await get_or_create_preferences(db, user.id)
            if prefs and getattr(prefs, "preferred_technologies", None):
                resolved_skills = [
                    s.strip().lower() for s in prefs.preferred_technologies if s and str(s).strip()
                ]

        if not resolved_skills:
            profile = await get_candidate_profile(db, user.id)
            if profile and profile.skills:
                resolved_skills = [s.strip().lower() for s in profile.skills[:5] if s and s.strip()]

        if not resolved_skills:
            resolved_skills = ["javascript", "typescript", "react", "node.js", "python"]

        payload = {
            "source": source.lower(),
            "freshness_hours": effective_freshness,
            "skills": resolved_skills,
            "user_id": str(user.id),
        }

        job_task_id = await task_queue.enqueue("sync_jobs", payload)

        return {
            "status": "enqueued",
            "task_id": job_task_id,
            "source": source,
            "freshness_hours": effective_freshness,
            "skills": resolved_skills,
            "message": f"Sync task enqueued for source '{source}' (freshness <= {effective_freshness}h).",
        }

