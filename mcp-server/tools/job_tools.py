import sys
import uuid
from pathlib import Path
from typing import Any

backend_dir = Path(__file__).resolve().parent.parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database import async_session_factory
from app.services.job_service import (
    get_job_by_id,
    get_saved_jobs_for_user,
    save_or_update_job_status,
)
from app.services.user_service import get_or_create_default_user


async def handle_get_job(job_id: str) -> dict[str, Any]:
    """Returns full details of a specific job by ID."""
    try:
        parsed_id = uuid.UUID(job_id)
    except ValueError:
        return {"error": f"Invalid job_id format: '{job_id}'"}

    async with async_session_factory() as db:
        job = await get_job_by_id(db, parsed_id)
        if not job:
            return {"error": f"Job with ID {job_id} not found"}
        return job


async def handle_save_job(job_id: str, notes: str | None = None) -> dict[str, Any]:
    """Saves a job for the candidate to review and apply manually."""
    try:
        parsed_id = uuid.UUID(job_id)
    except ValueError:
        return {"error": f"Invalid job_id format: '{job_id}'"}

    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)
        return await save_or_update_job_status(db, user.id, parsed_id, status="SAVED", notes=notes)


async def handle_ignore_job(job_id: str) -> dict[str, Any]:
    """Marks a job as ignored so it will not clutter recommendations."""
    try:
        parsed_id = uuid.UUID(job_id)
    except ValueError:
        return {"error": f"Invalid job_id format: '{job_id}'"}

    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)
        return await save_or_update_job_status(db, user.id, parsed_id, status="IGNORED")


async def handle_update_application_status(
    job_id: str, status: str, notes: str | None = None
) -> dict[str, Any]:
    """
    Updates the candidate's manual application tracking status.
    Valid statuses: DISCOVERED, SAVED, VIEWED, APPLIED, INTERVIEW, REJECTED, OFFER, IGNORED.
    IMPORTANT: The agent never automatically applies. Status is updated based on user confirmation.
    """
    try:
        parsed_id = uuid.UUID(job_id)
    except ValueError:
        return {"error": f"Invalid job_id format: '{job_id}'"}

    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)
        try:
            return await save_or_update_job_status(
                db, user.id, parsed_id, status=status, notes=notes
            )
        except ValueError as e:
            return {"error": str(e)}


async def handle_get_saved_jobs(status: str | None = None) -> dict[str, Any]:
    """Returns saved jobs and tracked applications for the candidate."""
    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)
        saved = await get_saved_jobs_for_user(db, user.id, status=status)
        return {"saved_jobs": saved, "count": len(saved)}


async def handle_get_jobs(job_ids: list[str]) -> dict[str, Any]:
    """Returns details for multiple jobs by their IDs."""
    valid_uuids = []
    invalid_ids = []
    for jid in job_ids:
        try:
            valid_uuids.append(uuid.UUID(jid))
        except ValueError:
            invalid_ids.append(jid)

    from app.services.job_service import get_jobs_by_ids

    async with async_session_factory() as db:
        jobs = await get_jobs_by_ids(db, valid_uuids)
        return {
            "jobs": jobs,
            "count": len(jobs),
            "invalid_ids": invalid_ids,
        }


async def handle_dismiss_job(job_id: str, reason: str | None = None) -> dict[str, Any]:
    """Marks a job as dismissed/ignored so it is removed from active recommendations."""
    return await handle_ignore_job(job_id=job_id)


async def handle_get_pipeline(status: str | None = None) -> dict[str, Any]:
    """
    Returns the candidate's application pipeline.
    Optionally filter by status (SAVED, VIEWED, APPLIED, INTERVIEW, OFFER, REJECTED).
    """
    return await handle_get_saved_jobs(status=status)


async def handle_get_application(job_id: str) -> dict[str, Any]:
    """
    Returns application status, stage, notes, and details for a specific tracked job.
    """
    try:
        parsed_id = uuid.UUID(job_id)
    except ValueError:
        return {"error": f"Invalid job_id format: '{job_id}'"}

    from sqlalchemy import select
    from app.models.saved_job import SavedJob

    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)
        stmt = select(SavedJob).where(SavedJob.user_id == user.id, SavedJob.job_id == parsed_id)
        res = await db.execute(stmt)
        saved = res.scalar_one_or_none()
        job = await get_job_by_id(db, parsed_id)

        if not job:
            return {"error": f"Job with ID {job_id} not found"}

        return {
            "job_id": str(job["id"]),
            "title": job["title"],
            "company": job["company"],
            "application_url": job["application_url"],
            "status": saved.status if saved else "DISCOVERED",
            "notes": saved.notes if saved else None,
            "updated_at": saved.updated_at.isoformat() if (saved and saved.updated_at) else None,
        }


async def handle_update_application(
    job_id: str, status: str, notes: str | None = None
) -> dict[str, Any]:
    """
    Updates the application stage and candidate notes for a specific job.
    Never submits applications automatically; updates tracking state based on candidate intent.
    """
    return await handle_update_application_status(job_id=job_id, status=status, notes=notes)

