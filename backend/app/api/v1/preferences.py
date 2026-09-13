from datetime import datetime, timezone
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
from app.config import settings
from sqlalchemy import select

router = APIRouter(prefix="/preferences", tags=["Preferences"])


def _to_preference_response(pref) -> PreferenceResponse:
    cfg = pref.ai_provider_config or {}
    configured_set = set()
    for prov_name, p_data in cfg.items():
        if isinstance(p_data, dict) and p_data.get("configured"):
            configured_set.add(prov_name)
    if pref.ai_provider and pref.ai_api_key and pref.ai_api_key.strip():
        configured_set.add(pref.ai_provider)

    return PreferenceResponse(
        id=pref.id,
        user_id=pref.user_id,
        freshness_hours=getattr(pref, "freshness_hours", 24) or 24,
        experience_max_years=getattr(pref, "experience_max_years", 2) if getattr(pref, "experience_max_years", None) is not None else 2,
        experience_level=getattr(pref, "experience_level", "ALL") or "ALL",
        preferred_locations=getattr(pref, "preferred_locations", []) or [],
        role_type=getattr(pref, "role_type", "ALL") or "ALL",
        source_boards=pref.source_boards if getattr(pref, "source_boards", None) is not None else ["LINKEDIN", "NAUKRI", "INTERNSHALA"],
        preferred_technologies=getattr(pref, "preferred_technologies", []) or [],
        preferred_industries=getattr(pref, "preferred_industries", []) or [],
        priority_companies=getattr(pref, "priority_companies", []) or [],
        excluded_companies=getattr(pref, "excluded_companies", []) or [],
        match_threshold=getattr(pref, "match_threshold", 60) if getattr(pref, "match_threshold", None) is not None else 60,
        sync_interval_hours=getattr(pref, "sync_interval_hours", 24) if getattr(pref, "sync_interval_hours", None) is not None else 24,
        auto_sync_enabled=bool(getattr(pref, "auto_sync_enabled", True)) if getattr(pref, "auto_sync_enabled", None) is not None else True,
        last_auto_sync_at=getattr(pref, "last_auto_sync_at", None),
        ai_provider=getattr(pref, "ai_provider", None),
        ai_model=getattr(pref, "ai_model", None),
        ai_base_url=getattr(pref, "ai_base_url", None),
        ai_fallback_provider=getattr(pref, "ai_fallback_provider", None),
        ai_fallback_model=getattr(pref, "ai_fallback_model", None),
        has_custom_api_key=bool(getattr(pref, "ai_api_key", None) and pref.ai_api_key.strip()),
        configured_providers=sorted(list(configured_set)),
        setup_completed=bool(getattr(pref, "setup_completed", False)),
        updated_at=getattr(pref, "updated_at", None) or datetime.now(timezone.utc),
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

    has_ai_provider = bool(pref.ai_provider or pref.ai_model or settings.LLM_PROVIDER)

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
