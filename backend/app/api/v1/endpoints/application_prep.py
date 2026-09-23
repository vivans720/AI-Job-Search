import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.application_prep_service import ApplicationPrepService
from app.services.user_service import get_or_create_default_user

router = APIRouter(prefix="/applications/prep", tags=["Application Preparation"])


class PrepareResumeRequest(BaseModel):
    mode: str = Field(default="EXISTING", description="EXISTING or TAILORED")


class GenerateCoverLetterRequest(BaseModel):
    tone: str = Field(default="PROFESSIONAL")
    custom_notes: str | None = None


class GenerateAnswersRequest(BaseModel):
    questions: list[str] = Field(..., min_length=1)


class PrepareFullApplicationRequest(BaseModel):
    resume_mode: str = Field(default="EXISTING")
    include_cover_letter: bool = True
    questions: list[str] | None = None


class UpdateStatusRequest(BaseModel):
    status: str = Field(..., description="DRAFT, READY_FOR_REVIEW, or APPROVED")


@router.get("/{job_id}")
async def get_application_prep(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await get_or_create_default_user(db)
    prep = await ApplicationPrepService.get_preparation(db, user.id, job_id)
    if not prep:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No application preparation found for job {job_id}",
        )
    return prep


@router.post("/{job_id}")
async def prepare_full_application(
    job_id: uuid.UUID,
    payload: PrepareFullApplicationRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await get_or_create_default_user(db)
    try:
        return await ApplicationPrepService.prepare_full_application(
            db=db,
            user_id=user.id,
            job_id=job_id,
            resume_mode=payload.resume_mode,
            include_cover_letter=payload.include_cover_letter,
            questions=payload.questions,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{job_id}/resume")
async def prepare_resume(
    job_id: uuid.UUID,
    payload: PrepareResumeRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await get_or_create_default_user(db)
    try:
        return await ApplicationPrepService.prepare_resume_for_job(
            db=db, user_id=user.id, job_id=job_id, mode=payload.mode
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{job_id}/cover-letter")
async def generate_cover_letter(
    job_id: uuid.UUID,
    payload: GenerateCoverLetterRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await get_or_create_default_user(db)
    try:
        return await ApplicationPrepService.generate_cover_letter(
            db=db,
            user_id=user.id,
            job_id=job_id,
            tone=payload.tone,
            custom_notes=payload.custom_notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{job_id}/answers")
async def generate_answers(
    job_id: uuid.UUID,
    payload: GenerateAnswersRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await get_or_create_default_user(db)
    try:
        return await ApplicationPrepService.generate_application_answers(
            db=db,
            user_id=user.id,
            job_id=job_id,
            questions=payload.questions,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{job_id}/status")
async def update_status(
    job_id: uuid.UUID,
    payload: UpdateStatusRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await get_or_create_default_user(db)
    try:
        return await ApplicationPrepService.update_preparation_status(
            db=db,
            user_id=user.id,
            job_id=job_id,
            status=payload.status,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{job_id}/resume/pdf")
async def download_resume_pdf(
    job_id: uuid.UUID,
    mode: str = "EXISTING",
    db: AsyncSession = Depends(get_db),
):
    from fastapi.responses import Response

    user = await get_or_create_default_user(db)
    try:
        pdf_bytes = await ApplicationPrepService.export_resume_pdf(
            db=db,
            user_id=user.id,
            job_id=job_id,
            mode=mode,
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="Resume_{job_id}.pdf"'
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{job_id}/cover-letter/pdf")
async def download_cover_letter_pdf(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    from fastapi.responses import Response

    user = await get_or_create_default_user(db)
    try:
        pdf_bytes = await ApplicationPrepService.export_cover_letter_pdf(
            db=db,
            user_id=user.id,
            job_id=job_id,
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="Cover_Letter_{job_id}.pdf"'
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

