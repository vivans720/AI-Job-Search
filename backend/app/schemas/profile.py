import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class CandidateProfileUpdate(BaseModel):
    experience_level: str | None = None
    experience_years: int | None = None
    target_roles: list[str] | None = None
    excluded_roles: list[str] | None = None
    skills: list[str] | None = None
    programming_languages: list[str] | None = None
    frameworks: list[str] | None = None
    databases: list[str] | None = None
    cloud: list[str] | None = None
    tools: list[str] | None = None
    preferred_locations: list[str] | None = None
    remote_preference: bool | None = None
    internship_allowed: bool | None = None
    fulltime_allowed: bool | None = None
    minimum_salary_lpa: float | None = None


class CandidateProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    source_resume_id: uuid.UUID | None
    experience_level: str
    experience_years: int
    target_roles: list[str]
    excluded_roles: list[str]
    skills: list[str]
    programming_languages: list[str]
    frameworks: list[str]
    databases: list[str]
    cloud: list[str]
    tools: list[str]
    projects: list[dict[str, Any]]
    education: list[dict[str, Any]]
    work_experience: list[dict[str, Any]]
    certifications: list[str]
    preferred_locations: list[str]
    remote_preference: bool
    internship_allowed: bool
    fulltime_allowed: bool
    minimum_salary_lpa: float | None
    manual_overrides: dict[str, Any]
    created_at: datetime
    updated_at: datetime
