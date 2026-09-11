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
