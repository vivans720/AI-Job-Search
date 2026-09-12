import uuid
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.resume import ResumeResponse
from app.services.resume_service import (
    get_resume_by_id,
    get_resumes_for_user,
    process_and_save_resume,
)
from app.services.user_service import get_or_create_default_user

router = APIRouter(prefix="/resumes", tags=["Resumes"])


@router.post("", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload and parse a resume file (PDF or DOCX) with security validation."""
    from app.core.security import validate_resume_upload

    user = await get_or_create_default_user(db)
    file_bytes = await file.read()
    raw_filename = file.filename or "resume.pdf"

    # Security validation (file size, mime/extension, magic bytes, safe naming)
    ext, secure_disk_name = validate_resume_upload(raw_filename, file_bytes)

    try:
        resume, _ = await process_and_save_resume(
            db=db,
            user_id=user.id,
            file_bytes=file_bytes,
            filename=raw_filename,
        )
        return resume
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process resume: {str(e)}")


@router.get("", response_model=list[ResumeResponse])
async def list_resumes(db: AsyncSession = Depends(get_db)):
    """List all uploaded resumes for the active user."""
    user = await get_or_create_default_user(db)
    return await get_resumes_for_user(db, user.id)


@router.get("/active", response_model=ResumeResponse)
async def get_active_resume(db: AsyncSession = Depends(get_db)):
    """Fetch the latest active resume for the user."""
    user = await get_or_create_default_user(db)
    resumes = await get_resumes_for_user(db, user.id)
    if not resumes:
        raise HTTPException(status_code=404, detail="No active resume found")
    return resumes[0]


@router.get("/{resume_id}", response_model=ResumeResponse)
async def get_resume(resume_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Fetch single resume by ID."""
    user = await get_or_create_default_user(db)
    resume = await get_resume_by_id(db, resume_id, user.id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    return resume


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(resume_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a resume by ID."""
    user = await get_or_create_default_user(db)
    resume = await get_resume_by_id(db, resume_id, user.id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    await db.delete(resume)
    await db.commit()
    return None
