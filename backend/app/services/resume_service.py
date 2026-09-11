import hashlib
import uuid
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.intelligence.embedding_provider import get_embedding_provider
from app.intelligence.extractors import (
    extract_candidate_profile_from_text,
    extract_text_from_bytes,
)
from app.models.resume import Resume
from app.services.profile_service import apply_resume_to_profile

logger = structlog.get_logger(__name__)


async def get_resumes_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[Resume]:
    stmt = select(Resume).where(Resume.user_id == user_id).order_by(Resume.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_resume_by_id(db: AsyncSession, resume_id: uuid.UUID, user_id: uuid.UUID) -> Resume | None:
    stmt = select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def process_and_save_resume(
    db: AsyncSession,
    user_id: uuid.UUID,
    file_bytes: bytes,
    filename: str,
    file_path: str | None = None,
) -> tuple[Resume, dict[str, Any]]:
    """
    Extracts text, parses structured candidate profile via LLM, computes BGE embedding,
    persists resume, and updates candidate profile.
    """
    resume_hash = hashlib.sha256(file_bytes).hexdigest()
    logger.info("processing_resume", filename=filename, hash=resume_hash)

    # 1. Text extraction
    raw_text = extract_text_from_bytes(file_bytes, filename)
    if not raw_text.strip():
        raise ValueError(f"Could not extract any text from resume file {filename}")

    # 2. LLM structured extraction
    extracted_data = await extract_candidate_profile_from_text(raw_text)

    # 3. Dense embedding via local BGE model
    # Combine skills, roles, projects, and summary for a rich semantic profile embedding
    embedding_text = (
        f"Roles: {', '.join(extracted_data.get('target_roles', []))}\n"
        f"Skills: {', '.join(extracted_data.get('skills', []))}\n"
        f"Summary: {extracted_data.get('summary', '')}\n"
        f"Experience: {extracted_data.get('experience_level', 'FRESHER')}"
    )
    embedder = get_embedding_provider()
    embedding = embedder.embed(embedding_text)

    # 4. Save Resume entity
    # Deactivate previous active resumes
    stmt = select(Resume).where(Resume.user_id == user_id, Resume.is_active == True)  # noqa: E712
    existing_resumes = (await db.execute(stmt)).scalars().all()
    for r in existing_resumes:
        r.is_active = False

    resume = Resume(
        id=uuid.uuid4(),
        user_id=user_id,
        filename=filename,
        file_path=file_path,
        raw_text=raw_text,
        extracted_data=extracted_data,
        resume_hash=resume_hash,
        embedding=embedding,
        is_active=True,
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)

    # 5. Apply extracted data to CandidateProfile (respecting manual overrides)
    await apply_resume_to_profile(
        db=db,
        user_id=user_id,
        resume_id=resume.id,
        extracted_data=extracted_data,
        embedding=embedding,
    )

    logger.info("resume_processed_successfully", resume_id=str(resume.id), user_id=str(user_id))
    return resume, extracted_data
