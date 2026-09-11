from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.resume import Resume
from app.schemas.preference import PreferenceResponse, PreferenceUpdate, SetupStatusResponse
from app.services.preference_service import (
    get_or_create_preferences,
    update_preferences,
)
from app.services.profile_service import get_candidate_profile
from app.services.user_service import get_or_create_default_user
from app.sources.registry import get_source_registry
from sqlalchemy import select

router = APIRouter(prefix="/preferences", tags=["Preferences"])


def _to_preference_response(pref) -> PreferenceResponse:
    return PreferenceResponse(
        id=pref.id,
        user_id=pref.user_id,
        freshness_hours=pref.freshness_hours,
        experience_max_years=pref.experience_max_years,
        preferred_technologies=pref.preferred_technologies or [],
        preferred_industries=pref.preferred_industries or [],
        priority_companies=pref.priority_companies or [],
        excluded_companies=pref.excluded_companies or [],
        match_threshold=pref.match_threshold,
        sync_interval_hours=pref.sync_interval_hours,
        auto_sync_enabled=pref.auto_sync_enabled,
        last_auto_sync_at=pref.last_auto_sync_at,
        ai_provider=pref.ai_provider,
        ai_model=pref.ai_model,
        ai_base_url=pref.ai_base_url,
        has_custom_api_key=bool(pref.ai_api_key and pref.ai_api_key.strip()),
        setup_completed=bool(getattr(pref, "setup_completed", False)),
        updated_at=pref.updated_at,
    )


@router.get("/setup-status", response_model=SetupStatusResponse)
async def get_setup_status(db: AsyncSession = Depends(get_db)):
    """Check readiness and onboarding status of current candidate."""
    user = await get_or_create_default_user(db)
    pref = await get_or_create_preferences(db, user.id)
    profile = await get_candidate_profile(db, user.id)

    # Check resume count
    resume_stmt = select(Resume).where(Resume.user_id == user.id)
    resume_res = await db.execute(resume_stmt)
    resumes = resume_res.scalars().all()
    has_resume = len(resumes) > 0

    has_profile = profile is not None and bool(
        profile.target_roles or profile.skills or profile.experience_years
    )

    registry = get_source_registry()
    has_sources = any(s.enabled for s in registry._sources.values()) if registry._sources else True

    has_ai_provider = bool(pref.ai_provider or pref.ai_model)

    profile_summary = None
    if profile:
        profile_summary = {
            "experience_level": profile.experience_level,
            "experience_years": profile.experience_years,
            "target_roles": profile.target_roles[:3] if profile.target_roles else [],
            "skills_count": len(profile.skills) if profile.skills else 0,
        }

    return SetupStatusResponse(
        setup_completed=bool(pref.setup_completed),
        has_profile=has_profile,
        has_resume=has_resume,
        has_ai_provider=has_ai_provider,
        has_sources=has_sources,
        user_id=user.id,
        profile_summary=profile_summary,
    )


@router.post("/complete-setup", response_model=PreferenceResponse)
async def complete_setup(db: AsyncSession = Depends(get_db)):
    """Mark onboarding wizard complete and unlock application."""
    user = await get_or_create_default_user(db)
    pref = await update_preferences(db, user.id, PreferenceUpdate(setup_completed=True))
    return _to_preference_response(pref)


@router.get("", response_model=PreferenceResponse)
async def get_preferences(db: AsyncSession = Depends(get_db)):
    """Fetch user search preferences."""
    user = await get_or_create_default_user(db)
    pref = await get_or_create_preferences(db, user.id)
    return _to_preference_response(pref)


@router.put("", response_model=PreferenceResponse)
async def update_user_preferences(
    updates: PreferenceUpdate, db: AsyncSession = Depends(get_db)
):
    """Update user search preferences."""
    user = await get_or_create_default_user(db)
    pref = await update_preferences(db, user.id, updates)
    return _to_preference_response(pref)
