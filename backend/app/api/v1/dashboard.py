from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.database import get_db
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard_service import get_dashboard_data
from app.services.preference_service import get_or_create_preferences
from app.services.profile_service import get_candidate_profile
from app.services.user_service import get_or_create_default_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
) -> DashboardResponse:
    """
    Returns aggregated dashboard intelligence:
    - Funnel metrics (fresh -> strong matches -> excellent matches)
    - Top recommended jobs
    - Fresh newly ingested jobs
    - Application tracking pipeline counts
    - Identified skill gaps
    - Source adapter health & synchronization status
    """
    user = await get_or_create_default_user(db)
    profile = await get_candidate_profile(db, user.id)
    preferences = await get_or_create_preferences(db, user.id)

    return await get_dashboard_data(
        db=db,
        user_id=user.id,
        profile=profile,
        preferences=preferences,
    )
