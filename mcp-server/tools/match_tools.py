import sys
import uuid
from pathlib import Path
from typing import Any

backend_dir = Path(__file__).resolve().parent.parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from app.database import async_session_factory
from app.models.job import Job
from app.services.matching_service import get_matching_service
from app.services.preference_service import get_or_create_preferences
from app.services.profile_service import get_candidate_profile
from app.services.user_service import get_or_create_default_user


async def handle_match_job(job_id: str) -> dict[str, Any]:
    """Evaluates and returns 6-dimension match breakdown for a job against candidate profile."""
    try:
        parsed_id = uuid.UUID(job_id)
    except ValueError:
        return {"error": f"Invalid job_id format: '{job_id}'"}

    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)
        profile = await get_candidate_profile(db, user.id)
        if not profile:
            return {"error": "Candidate profile not found. Please upload resume first."}

        prefs = await get_or_create_preferences(db, user.id)
        job = (await db.execute(select(Job).where(Job.id == parsed_id))).scalar_one_or_none()
        if not job:
            return {"error": f"Job with ID {job_id} not found"}

        eval_data = get_matching_service().evaluate_job(job, profile, prefs)
        return {
            "job_id": str(job.id),
            "title": job.title,
            "company": job.company_name,
            "application_url": job.application_url,
            "match": eval_data,
        }


async def handle_rank_jobs(job_ids: list[str]) -> dict[str, Any]:
    """Ranks a list of job IDs by calculated match score descending."""
    valid_uuids = []
    for jid in job_ids:
        try:
            valid_uuids.append(uuid.UUID(jid))
        except ValueError:
            continue

    if not valid_uuids:
        return {"ranked_jobs": []}

    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)
        profile = await get_candidate_profile(db, user.id)
        if not profile:
            return {"ranked_jobs": []}

        prefs = await get_or_create_preferences(db, user.id)
        matching_svc = get_matching_service()

        stmt = select(Job).where(Job.id.in_(valid_uuids))
        jobs = (await db.execute(stmt)).scalars().all()

        scored = []
        for j in jobs:
            m = matching_svc.evaluate_job(j, profile, prefs)
            scored.append(
                {
                    "job_id": str(j.id),
                    "title": j.title,
                    "company": j.company_name,
                    "score": m["overall_score"],
                    "recommendation": m["recommendation"],
                    "application_url": j.application_url,
                    "matched_skills": m["matched_skills"],
                    "missing_skills": m["missing_skills"],
                    "transferable_skills": m["transferable_skills"],
                    "quality_score": j.quality_score,
                    "posted_at": j.posted_at.isoformat() if j.posted_at else None,
                }
            )

        # Sort by score desc, then quality desc
        scored.sort(key=lambda x: (x["score"], x["quality_score"]), reverse=True)
        return {"ranked_jobs": scored}
