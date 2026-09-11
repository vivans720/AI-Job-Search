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
    updated_at: datetime
