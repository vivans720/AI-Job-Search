import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_FRESHNESS = (1, 4, 8, 12, 16, 24)
ALLOWED_EXPERIENCE = ("ALL", "FRESHER", "0_1", "1_2", "2_3", "3_PLUS")
ALLOWED_ROLE_TYPES = ("ALL", "JOBS", "INTERNSHIPS")
ALLOWED_SOURCE_BOARDS = ("LINKEDIN", "NAUKRI", "INTERNSHALA", "INDEED")


class PreferenceUpdate(BaseModel):
    freshness_hours: int | None = None
    experience_max_years: int | None = None
    experience_level: str | None = None
    match_threshold: int | None = Field(default=None, ge=0, le=100)
    preferred_locations: list[str] | None = None
    role_type: str | None = None
    source_boards: list[str] | None = None
    preferred_technologies: list[str] | None = None
    preferred_industries: list[str] | None = None
    priority_companies: list[str] | None = None
    excluded_companies: list[str] | None = None
    sync_interval_hours: int | None = None
    auto_sync_enabled: bool | None = None
    ai_provider: str | None = None
    ai_model: str | None = None
    ai_base_url: str | None = None
    ai_api_key: str | None = None
    ai_fallback_provider: str | None = None
    ai_fallback_model: str | None = None
    setup_completed: bool | None = None

    @field_validator("freshness_hours")
    @classmethod
    def validate_freshness(cls, v: int | None) -> int | None:
        if v is not None and v not in ALLOWED_FRESHNESS:
            raise ValueError(f"freshness_hours must be one of {ALLOWED_FRESHNESS}, got {v}")
        return v

    @field_validator("experience_level")
    @classmethod
    def validate_experience_level(cls, v: str | None) -> str | None:
        if v is not None and v.upper() not in ALLOWED_EXPERIENCE:
            raise ValueError(f"experience_level must be one of {ALLOWED_EXPERIENCE}, got {v}")
        return v.upper() if v is not None else None

    @field_validator("role_type")
    @classmethod
    def validate_role_type(cls, v: str | None) -> str | None:
        if v is not None and v.upper() not in ALLOWED_ROLE_TYPES:
            raise ValueError(f"role_type must be one of {ALLOWED_ROLE_TYPES}, got {v}")
        return v.upper() if v is not None else None

    @field_validator("source_boards")
    @classmethod
    def validate_source_boards(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            normalized = []
            for b in v:
                b_norm = b.strip().upper()
                if b_norm not in ALLOWED_SOURCE_BOARDS:
                    raise ValueError(f"Invalid source board '{b}'. Allowed: {ALLOWED_SOURCE_BOARDS}")
                normalized.append(b_norm)
            return normalized
        return v


class PreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    freshness_hours: int = 24
    experience_max_years: int = 2
    experience_level: str = "ALL"
    match_threshold: int = 60
    preferred_locations: list[str] = []
    role_type: str = "ALL"
    source_boards: list[str] = ["LINKEDIN", "NAUKRI", "INTERNSHALA"]
    preferred_technologies: list[str] = []
    preferred_industries: list[str] = []
    priority_companies: list[str] = []
    excluded_companies: list[str] = []
    sync_interval_hours: int = 24
    auto_sync_enabled: bool = True
    last_auto_sync_at: datetime | None = None
    ai_provider: str | None = None
    ai_model: str | None = None
    ai_base_url: str | None = None
    ai_fallback_provider: str | None = None
    ai_fallback_model: str | None = None
    has_custom_api_key: bool = False
    configured_providers: list[str] = []
    setup_completed: bool = False
    updated_at: datetime


class SetupStatusResponse(BaseModel):
    setup_completed: bool
    has_profile: bool
    has_resume: bool
    has_ai_provider: bool
    has_sources: bool
    user_id: uuid.UUID
    profile_summary: dict | None = None
