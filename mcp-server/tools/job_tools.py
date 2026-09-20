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
from app.services.agent_approval_service import AgentApprovalService
from app.services.job_service import (
    get_job_by_id,
    get_saved_jobs_for_user,
    save_or_update_job_status,
)
from app.services.user_service import get_or_create_default_user
from middleware.activity_logger import ensure_active_run


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


async def handle_save_job(
    job_id: str, notes: str | None = None, reason: str | None = None
) -> dict[str, Any]:
    """Saves a job for the candidate. Subject to autonomy policy approval gate."""
    try:
        parsed_id = uuid.UUID(job_id)
    except ValueError:
        return {"error": f"Invalid job_id format: '{job_id}'"}

    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)
        job_stmt = select(Job).where(Job.id == parsed_id)
        job_res = await db.execute(job_stmt)
        if not job_res.scalar_one_or_none():
            return {"error": f"Job with ID {job_id} not found"}

        is_auto = await AgentApprovalService.check_is_action_autonomous(db, user.id, "save_job")
        if not is_auto:
            run_id = await ensure_active_run()
            apprv = await AgentApprovalService.create_approval_request(
                db=db,
                user_id=user.id,
                action_type="SAVE_JOB",
                job_id=parsed_id,
                payload={"job_id": job_id, "notes": notes},
                reason=reason or "Agent recommendation to bookmark job for candidate",
                run_id=run_id,
            )
            return {
                "status": "APPROVAL_REQUIRED",
                "approval_id": str(apprv.id),
                "action": "save_job",
                "job_id": job_id,
                "message": f"Action 'save_job' requires user approval. Approval request queued (ID: {apprv.id}).",
            }

        return await save_or_update_job_status(db, user.id, parsed_id, status="SAVED", notes=notes)


async def handle_batch_save_jobs(
    job_ids: list[str], notes: str | None = None, reason: str | None = None
) -> dict[str, Any]:
    """Saves multiple jobs recommended by the agent, respecting approval gate."""
    if not job_ids:
        return {"error": "No job_ids provided"}

    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)
        is_auto = await AgentApprovalService.check_is_action_autonomous(db, user.id, "save_job")
        if not is_auto:
            run_id = await ensure_active_run()
            apprv = await AgentApprovalService.create_approval_request(
                db=db,
                user_id=user.id,
                action_type="BATCH_SAVE",
                job_id=None,
                payload={"job_ids": job_ids, "notes": notes},
                reason=reason or f"Agent recommended saving batch of {len(job_ids)} jobs",
                run_id=run_id,
            )
            return {
                "status": "APPROVAL_REQUIRED",
                "approval_id": str(apprv.id),
                "action": "batch_save_jobs",
                "job_count": len(job_ids),
                "message": f"Saving {len(job_ids)} jobs requires user approval. Approval request queued (ID: {apprv.id}).",
            }

        saved_count = 0
        for jid_str in job_ids:
            try:
                jid = uuid.UUID(jid_str)
                await save_or_update_job_status(db, user.id, jid, status="SAVED", notes=notes)
                saved_count += 1
            except Exception:
                pass
        return {"status": "SUCCESS", "saved_count": saved_count}


async def handle_ignore_job(job_id: str, reason: str | None = None) -> dict[str, Any]:
    """Marks a job as ignored so it will not clutter recommendations. Gated by policy."""
    try:
        parsed_id = uuid.UUID(job_id)
    except ValueError:
        return {"error": f"Invalid job_id format: '{job_id}'"}

    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)
        is_auto = await AgentApprovalService.check_is_action_autonomous(db, user.id, "dismiss_job")
        if not is_auto:
            run_id = await ensure_active_run()
            apprv = await AgentApprovalService.create_approval_request(
                db=db,
                user_id=user.id,
                action_type="DISMISS_JOB",
                job_id=parsed_id,
                payload={"job_id": job_id, "reason": reason},
                reason=reason or "Agent suggests dismissing job",
                run_id=run_id,
            )
            return {
                "status": "APPROVAL_REQUIRED",
                "approval_id": str(apprv.id),
                "action": "dismiss_job",
                "job_id": job_id,
                "message": f"Dismissing job requires user approval. Approval request queued (ID: {apprv.id}).",
            }

        return await save_or_update_job_status(db, user.id, parsed_id, status="IGNORED", notes=reason)


async def handle_update_application_status(
    job_id: str, status: str, notes: str | None = None, reason: str | None = None
) -> dict[str, Any]:
    """
    Updates candidate tracking status.
    Gated by update_pipeline_status policy. Never automatically applies without confirmation.
    """
    try:
        parsed_id = uuid.UUID(job_id)
    except ValueError:
        return {"error": f"Invalid job_id format: '{job_id}'"}

    upper_status = status.upper()
    from app.services.job_service import VALID_STATUSES
    if upper_status not in VALID_STATUSES:
        return {"error": f"Invalid status '{status}'. Must be one of: {sorted(list(VALID_STATUSES))}"}

    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)
        # Check job existence
        job_stmt = select(Job).where(Job.id == parsed_id)
        job_res = await db.execute(job_stmt)
        if not job_res.scalar_one_or_none():
            return {"error": f"Job with ID {job_id} not found"}

        is_auto = await AgentApprovalService.check_is_action_autonomous(
            db, user.id, "update_pipeline_status"
        )
        # APPLIED status is strictly gated on user confirmation regardless of autonomy policy
        if upper_status == "APPLIED" or not is_auto:
            run_id = await ensure_active_run()
            action_reason = (
                reason
                or ("Candidate confirmation required: Transitioning to 'APPLIED' requires explicit user verification that the application was submitted."
                    if upper_status == "APPLIED"
                    else f"Agent proposed moving job status to {upper_status}")
            )
            apprv = await AgentApprovalService.create_approval_request(
                db=db,
                user_id=user.id,
                action_type="UPDATE_PIPELINE_STATUS",
                job_id=parsed_id,
                payload={"job_id": job_id, "status": upper_status, "notes": notes},
                reason=action_reason,
                run_id=run_id,
            )
            message = (
                f"Transitioning to 'APPLIED' strictly requires candidate confirmation. Approval request queued (ID: {apprv.id})."
                if upper_status == "APPLIED"
                else f"Updating pipeline status to '{status}' requires user approval. Approval request queued (ID: {apprv.id})."
            )
            return {
                "status": "APPROVAL_REQUIRED",
                "approval_id": str(apprv.id),
                "action": "update_pipeline_status",
                "target_status": upper_status,
                "job_id": job_id,
                "message": message,
            }

        try:
            return await save_or_update_job_status(
                db, user.id, parsed_id, status=upper_status, notes=notes
            )
        except ValueError as e:
            return {"error": str(e)}


async def handle_check_approval_status(approval_id: str) -> dict[str, Any]:
    """Checks the resolution status of an approval request."""
    try:
        parsed_id = uuid.UUID(approval_id)
    except ValueError:
        return {"error": f"Invalid approval_id format: '{approval_id}'"}

    from sqlalchemy import select
    from app.models.agent_approval import AgentApproval

    async with async_session_factory() as db:
        stmt = select(AgentApproval).where(AgentApproval.id == parsed_id)
        res = await db.execute(stmt)
        apprv = res.scalar_one_or_none()
        if not apprv:
            return {"error": f"Approval with ID {approval_id} not found"}

        return {
            "approval_id": str(apprv.id),
            "status": apprv.status,
            "action_type": apprv.action_type,
            "resolved_at": apprv.resolved_at.isoformat() if apprv.resolved_at else None,
            "resolution_notes": apprv.resolution_notes,
        }


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
    return await handle_ignore_job(job_id=job_id, reason=reason)


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

