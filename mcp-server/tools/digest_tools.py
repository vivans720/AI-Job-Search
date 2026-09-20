import sys
import uuid
from pathlib import Path
from typing import Any, Optional

backend_dir = Path(__file__).resolve().parent.parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database import async_session_factory
from app.services.scheduled_search_service import ScheduledSearchService
from app.services.user_service import get_or_create_default_user


async def handle_get_daily_digests(limit: int = 7) -> dict[str, Any]:
    """Retrieves recent daily job digests and briefings for candidate review."""
    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)
        digests = await ScheduledSearchService.get_recent_digests(db, user.id, limit=limit)
        results = []
        for d in digests:
            results.append(
                {
                    "id": str(d.id),
                    "digest_date": d.digest_date.isoformat(),
                    "summary": d.summary,
                    "job_ids": d.job_ids,
                    "total_found": d.total_found,
                    "strong_matches_count": d.strong_matches_count,
                    "status": d.status,
                    "created_at": d.created_at.isoformat(),
                }
            )
        return {
            "status": "ok",
            "digests_count": len(results),
            "digests": results,
        }


async def handle_create_daily_digest(
    summary: str,
    job_ids: list[str],
    status: str = "DELIVERED",
    metadata_info: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Saves an autonomous morning Daily Job Digest into persistent candidate feed.
    Also records recommended job IDs into duplicate-prevention index.
    """
    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)
        digest = await ScheduledSearchService.create_digest_manual(
            db=db,
            user_id=user.id,
            summary=summary,
            job_ids=job_ids,
            status=status,
            metadata_info=metadata_info,
        )
        return {
            "status": "ok",
            "digest_id": str(digest.id),
            "summary_preview": digest.summary[:150] + "...",
            "job_count": len(job_ids),
            "digest_date": digest.digest_date.isoformat(),
        }


async def handle_run_scheduled_job_search(
    freshness_hours: int = 24,
    match_threshold: Optional[int] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Executes full scheduled autonomous job search pipeline:
    1. Reads candidate profile & preferences.
    2. Discovers fresh jobs excluding previously alerted postings.
    3. Scores & ranks jobs against candidate profile.
    4. Generates formatted morning briefing (or zero-match guidance).
    5. Saves digest and prevents duplicate re-alerts.
    """
    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)
        result = await ScheduledSearchService.run_scheduled_job_search(
            db=db,
            user_id=user.id,
            freshness_hours=freshness_hours,
            match_threshold_override=match_threshold,
            dry_run=dry_run,
        )
        return result
