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
from app.services.browser_research_service import BrowserResearchService


async def handle_research_job_page(
    job_id: str,
    timeout_seconds: int = 25,
) -> dict[str, Any]:
    """
    Inspects live job posting URL using browser automation.
    Extracts deep context: requirements, qualifications, application forms, closure status.
    Stores findings into Job.raw_data['browser_research'].
    """
    try:
        parsed_id = uuid.UUID(job_id)
    except ValueError:
        return {"status": "error", "error": f"Invalid job_id format: '{job_id}'"}

    async with async_session_factory() as db:
        stmt = select(Job).where(Job.id == parsed_id)
        res = await db.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            return {"status": "error", "error": f"Job with ID {job_id} not found"}

        target_url = job.application_url or job.source_url
        if not target_url:
            return {"status": "error", "error": f"No URL found for job {job_id}"}

        research = await BrowserResearchService.inspect_page(
            url=target_url,
            timeout_seconds=timeout_seconds,
        )

        if research.get("status") == "ok":
            # Persist deep research findings in raw_data
            current_raw = dict(job.raw_data or {})
            current_raw["browser_research"] = {
                "final_url": research.get("final_url"),
                "page_title": research.get("page_title"),
                "is_closed": research.get("is_closed"),
                "has_apply_form": research.get("has_apply_form"),
                "researched_at": research.get("researched_at"),
                "char_count": research.get("char_count"),
                "engine": research.get("engine"),
                "snippet": (research.get("extracted_text") or "")[:500],
            }
            job.raw_data = current_raw
            await db.commit()

        return {
            "status": research.get("status", "error"),
            "job_id": str(job.id),
            "job_title": job.title,
            "company_name": job.company_name,
            "research": research,
        }


async def handle_get_job_research(job_id: str) -> dict[str, Any]:
    """Retrieves cached browser research insights for a job."""
    try:
        parsed_id = uuid.UUID(job_id)
    except ValueError:
        return {"status": "error", "error": f"Invalid job_id format: '{job_id}'"}

    async with async_session_factory() as db:
        stmt = select(Job).where(Job.id == parsed_id)
        res = await db.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            return {"status": "error", "error": f"Job with ID {job_id} not found"}

        research = (job.raw_data or {}).get("browser_research")
        if not research:
            return {
                "status": "not_found",
                "job_id": str(job.id),
                "message": "No browser research recorded yet. Call research_job_page first.",
            }

        return {
            "status": "ok",
            "job_id": str(job.id),
            "job_title": job.title,
            "company_name": job.company_name,
            "research": research,
        }
