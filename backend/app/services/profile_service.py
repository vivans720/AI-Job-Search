import uuid
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.candidate_profile import CandidateProfile
from app.schemas.profile import CandidateProfileUpdate

logger = structlog.get_logger(__name__)


async def get_candidate_profile(db: AsyncSession, user_id: uuid.UUID) -> CandidateProfile | None:
    """Fetch active candidate profile for user."""
    stmt = select(CandidateProfile).where(CandidateProfile.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update_candidate_profile(
    db: AsyncSession, user_id: uuid.UUID, updates: CandidateProfileUpdate
) -> CandidateProfile:
    """
    Update profile with explicit manual edits.
    Edits are tracked in manual_overrides JSONB so future resume uploads don't overwrite them.
    """
    profile = await get_candidate_profile(db, user_id)
    if not profile:
        profile = CandidateProfile(user_id=user_id)
        db.add(profile)

    update_dict = updates.model_dump(exclude_unset=True)
    current_overrides = dict(profile.manual_overrides or {})

    for field, value in update_dict.items():
        if value is not None:
            setattr(profile, field, value)
            current_overrides[field] = True

    # Filter out excluded roles from target_roles
    if profile.excluded_roles and profile.target_roles:
        excluded_set = {r.lower() for r in profile.excluded_roles}
        profile.target_roles = [
            r for r in profile.target_roles if r.lower() not in excluded_set
        ]

    profile.manual_overrides = current_overrides
    await db.commit()
    await db.refresh(profile)
    logger.info("candidate_profile_updated", user_id=str(user_id), overrides=list(current_overrides.keys()))
    return profile


async def apply_resume_to_profile(
    db: AsyncSession,
    user_id: uuid.UUID,
    resume_id: uuid.UUID,
    extracted_data: dict[str, Any],
    embedding: list[float] | None = None,
) -> CandidateProfile:
    """
    Apply LLM-extracted resume data to candidate profile while preserving manual overrides
    and enforcing excluded_roles.
    """
    profile = await get_candidate_profile(db, user_id)
    if not profile:
        profile = CandidateProfile(user_id=user_id)
        db.add(profile)

    overrides = profile.manual_overrides or {}
    profile.source_resume_id = resume_id

    # Core taxonomy fields
    fields_to_sync = [
        "experience_level",
        "experience_years",
        "target_roles",
        "skills",
        "programming_languages",
        "frameworks",
        "databases",
        "cloud",
        "tools",
        "projects",
        "education",
        "work_experience",
        "certifications",
        "preferred_locations",
    ]

    for field in fields_to_sync:
        if field in extracted_data:
            val = extracted_data[field]
            if val is not None:
                if field == "skills":
                    # On resume upload, merge newly extracted skills with any existing skills
                    existing_skills = profile.skills or []
                    extracted_skills = val if isinstance(val, list) else []
                    merged_skills = list(dict.fromkeys(extracted_skills + existing_skills))
                    setattr(profile, "skills", merged_skills)
                    # Clear the override flag so the user sees the fresh resume skills
                    if "skills" in overrides:
                        overrides.pop("skills", None)
                elif field not in overrides:
                    if field == "experience_years":
                        try:
                            val = int(round(float(val)))
                        except (ValueError, TypeError):
                            val = 0
                    setattr(profile, field, val)

    profile.manual_overrides = overrides

    # Always enforce excluded roles
    if profile.excluded_roles and profile.target_roles:
        excluded_set = {r.lower() for r in profile.excluded_roles}
        profile.target_roles = [
            r for r in profile.target_roles if r.lower() not in excluded_set
        ]

    if embedding is not None:
        profile.embedding = embedding

    await db.commit()
    await db.refresh(profile)
    logger.info("resume_applied_to_candidate_profile", user_id=str(user_id), resume_id=str(resume_id))
    return profile
