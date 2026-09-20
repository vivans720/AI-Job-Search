import sys
import uuid
from pathlib import Path
from typing import Any

backend_dir = Path(__file__).resolve().parent.parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database import async_session_factory
from app.services.agent_approval_service import AgentApprovalService
from app.services.application_prep_service import ApplicationPrepService
from app.services.user_service import get_or_create_default_user
from middleware.activity_logger import ensure_active_run


async def handle_prepare_application(
    job_id: str,
    resume_mode: str = "EXISTING",
    include_cover_letter: bool = True,
    questions: list[str] | None = None,
) -> dict[str, Any]:
    """
    Prepares a complete application for a job without submitting.
    Generates tailored/selected resume, cover letter, and answers to screening questions.
    Places the application in READY_FOR_REVIEW status for user approval.
    """
    try:
        parsed_id = uuid.UUID(job_id)
    except ValueError:
        return {"status": "error", "error": f"Invalid job_id format: '{job_id}'"}

    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)
        try:
            res = await ApplicationPrepService.prepare_full_application(
                db=db,
                user_id=user.id,
                job_id=parsed_id,
                resume_mode=resume_mode,
                include_cover_letter=include_cover_letter,
                questions=questions,
            )
            return res
        except Exception as e:
            return {"status": "error", "error": str(e)}


async def handle_prepare_resume(job_id: str, mode: str = "EXISTING") -> dict[str, Any]:
    """
    Prepares resume for target job.
    - mode='EXISTING': uses active primary resume as-is.
    - mode='TAILORED': re-frames experience and highlights relevant skills with strict anti-hallucination.
    """
    try:
        parsed_id = uuid.UUID(job_id)
    except ValueError:
        return {"status": "error", "error": f"Invalid job_id format: '{job_id}'"}

    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)
        try:
            return await ApplicationPrepService.prepare_resume_for_job(
                db=db, user_id=user.id, job_id=parsed_id, mode=mode
            )
        except Exception as e:
            return {"status": "error", "error": str(e)}


async def handle_generate_cover_letter(
    job_id: str, tone: str = "PROFESSIONAL", custom_notes: str | None = None
) -> dict[str, Any]:
    """Generates a targeted cover letter for a job drawing from profile and deep web research."""
    try:
        parsed_id = uuid.UUID(job_id)
    except ValueError:
        return {"status": "error", "error": f"Invalid job_id format: '{job_id}'"}

    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)
        try:
            return await ApplicationPrepService.generate_cover_letter(
                db=db, user_id=user.id, job_id=parsed_id, tone=tone, custom_notes=custom_notes
            )
        except Exception as e:
            return {"status": "error", "error": str(e)}


async def handle_generate_application_answers(
    job_id: str, questions: list[str]
) -> dict[str, Any]:
    """Generates answers to screening questions with factual grounding from candidate profile."""
    try:
        parsed_id = uuid.UUID(job_id)
    except ValueError:
        return {"status": "error", "error": f"Invalid job_id format: '{job_id}'"}

    if not questions:
        return {"status": "error", "error": "No questions provided"}

    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)
        try:
            return await ApplicationPrepService.generate_application_answers(
                db=db, user_id=user.id, job_id=parsed_id, questions=questions
            )
        except Exception as e:
            return {"status": "error", "error": str(e)}


async def handle_get_application_preparation(job_id: str) -> dict[str, Any]:
    """Retrieves prepared application artifacts (resume, cover letter, Q&A, review status)."""
    try:
        parsed_id = uuid.UUID(job_id)
    except ValueError:
        return {"status": "error", "error": f"Invalid job_id format: '{job_id}'"}

    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)
        prep = await ApplicationPrepService.get_preparation(
            db=db, user_id=user.id, job_id=parsed_id
        )
        if not prep:
            return {
                "status": "not_found",
                "job_id": job_id,
                "message": "No application prepared yet for this job.",
            }
        return {"status": "ok", "preparation": prep}


async def handle_fill_application(
    job_id: str,
    dry_run: bool = False,
    timeout_seconds: int = 45,
) -> dict[str, Any]:
    """
    Phase 10: Autonomously fills external application forms in browser.
    Maps candidate profile, resume, and answers to web inputs.
    Guaranteed programmatic barrier: NEVER clicks Submit and transitions to READY_FOR_REVIEW.
    """
    try:
        parsed_id = uuid.UUID(job_id)
    except ValueError:
        return {"status": "error", "error": f"Invalid job_id format: '{job_id}'"}

    from app.services.browser_application_service import BrowserApplicationService

    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)
        return await BrowserApplicationService.fill_application_form(
            db=db,
            user_id=user.id,
            job_id=parsed_id,
            dry_run=dry_run,
            timeout_seconds=timeout_seconds,
        )

