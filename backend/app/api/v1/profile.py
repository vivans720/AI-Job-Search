from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.profile import CandidateProfileResponse, CandidateProfileUpdate
from app.services.profile_service import (
    get_candidate_profile,
    update_candidate_profile,
)
from app.services.user_service import get_or_create_default_user

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get("", response_model=CandidateProfileResponse)
async def get_profile(db: AsyncSession = Depends(get_db)):
    """Fetch current structured candidate profile."""
    user = await get_or_create_default_user(db)
    profile = await get_candidate_profile(db, user.id)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Candidate profile not found. Please upload a resume first.",
        )
    return profile


@router.put("", response_model=CandidateProfileResponse)
async def update_profile(
    updates: CandidateProfileUpdate, db: AsyncSession = Depends(get_db)
):
    """Manually update candidate profile (updates recorded as overrides)."""
    user = await get_or_create_default_user(db)
    return await update_candidate_profile(db, user.id, updates)
