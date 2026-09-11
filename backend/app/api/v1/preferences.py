from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.preference import PreferenceResponse, PreferenceUpdate
from app.services.preference_service import (
    get_or_create_preferences,
    update_preferences,
)
from app.services.user_service import get_or_create_default_user

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
        updated_at=pref.updated_at,
    )


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
