import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.preference import Preference
from app.schemas.preference import PreferenceUpdate
from app.intelligence.llm_provider import reset_ai_provider_cache

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

    provider_config = dict(pref.ai_provider_config or {})
    target_provider = update_dict.get("ai_provider", pref.ai_provider)

    # 1. If updating API key for a provider, persist in ai_provider_config
    if "ai_api_key" in update_dict and update_dict["ai_api_key"] is not None:
        key_val = update_dict["ai_api_key"].strip()
        if target_provider:
            if target_provider not in provider_config:
                provider_config[target_provider] = {}
            provider_config[target_provider]["api_key"] = key_val
            provider_config[target_provider]["configured"] = bool(key_val)

    # 2. If provider switched but no explicit key provided in payload, restore previously configured key
    if "ai_provider" in update_dict and "ai_api_key" not in update_dict:
        saved_provider_info = provider_config.get(target_provider, {})
        if saved_provider_info.get("api_key"):
            update_dict["ai_api_key"] = saved_provider_info["api_key"]

    pref.ai_provider_config = provider_config

    for field, value in update_dict.items():
        if value is not None:
            setattr(pref, field, value)

    await db.commit()
    await db.refresh(pref)
    reset_ai_provider_cache()
    logger.info("preferences_updated", user_id=str(user_id), provider=pref.ai_provider)
    return pref
