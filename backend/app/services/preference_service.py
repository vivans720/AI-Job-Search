import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.preference import Preference
from app.schemas.preference import PreferenceUpdate

logger = structlog.get_logger(__name__)


async def get_or_create_preferences(db: AsyncSession, user_id: uuid.UUID) -> Preference:
    stmt = select(Preference).where(Preference.user_id == user_id)
    result = await db.execute(stmt)
    pref = result.scalar_one_or_none()

    if not pref:
        pref = Preference(user_id=user_id)
        db.add(pref)
        await db.commit()
        await db.refresh(pref)

    return pref


async def update_preferences(
    db: AsyncSession, user_id: uuid.UUID, updates: PreferenceUpdate
) -> Preference:
    pref = await get_or_create_preferences(db, user_id)
    update_dict = updates.model_dump(exclude_unset=True)

    for field, value in update_dict.items():
        if value is not None:
            setattr(pref, field, value)

    await db.commit()
    await db.refresh(pref)
    logger.info("preferences_updated", user_id=str(user_id))
    return pref
