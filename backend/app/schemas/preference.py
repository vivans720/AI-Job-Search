import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class PreferenceUpdate(BaseModel):
    freshness_hours: int | None = None
    experience_max_years: int | None = None
    preferred_technologies: list[str] | None = None
    preferred_industries: list[str] | None = None
    priority_companies: list[str] | None = None
    excluded_companies: list[str] | None = None
    match_threshold: int | None = None
    sync_interval_hours: int | None = None
    auto_sync_enabled: bool | None = None
    ai_provider: str | None = None
    ai_model: str | None = None
    ai_base_url: str | None = None
    ai_api_key: str | None = None


class PreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    freshness_hours: int
    experience_max_years: int
    preferred_technologies: list[str]
    preferred_industries: list[str]
    priority_companies: list[str]
    excluded_companies: list[str]
    match_threshold: int
    sync_interval_hours: int = 24
    auto_sync_enabled: bool = True
    last_auto_sync_at: datetime | None = None
    ai_provider: str | None = None
    ai_model: str | None = None
    ai_base_url: str | None = None
    has_custom_api_key: bool = False
    updated_at: datetime
