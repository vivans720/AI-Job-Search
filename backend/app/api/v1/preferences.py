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


@router.get("", response_model=PreferenceResponse)
async def get_preferences(db: AsyncSession = Depends(get_db)):
    """Fetch user search preferences."""
    user = await get_or_create_default_user(db)
    return await get_or_create_preferences(db, user.id)


@router.put("", response_model=PreferenceResponse)
async def update_user_preferences(
    updates: PreferenceUpdate, db: AsyncSession = Depends(get_db)
):
    """Update user search preferences."""
    user = await get_or_create_default_user(db)
    return await update_preferences(db, user.id, updates)
