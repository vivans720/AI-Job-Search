from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

from app.schemas.match import MatchBreakdown


class JobListItem(BaseModel):
    id: str
    title: str
    company: str
    company_logo_url: str | None = None
    location: str | None = None
    normalized_location: str | None = None
    remote_type: str = "ONSITE"
    employment_type: str = "FULL_TIME"
    salary: str = "Not disclosed"
    salary_min: float | None = None
    salary_max: float | None = None
    experience: str = "0-1 years"
    experience_min: int | None = None
    experience_max: int | None = None
    experience_confidence: str = "LOW"
    description_confidence: str = "HIGH"
    posted_at: str | None = None
    age_hours: float | None = None
    source: str
    application_url: str
    required_skills: list[str] = Field(default_factory=list)
    quality_score: float = 0.0
    match: MatchBreakdown | None = None
    saved_status: str | None = None
    other_sources: list[dict[str, Any]] = Field(default_factory=list)


class JobDetail(JobListItem):
    description: str
    preferred_skills: list[str] = Field(default_factory=list)
    source_url: str
    posted_at_confidence: str = "LOW"


class JobRankRequest(BaseModel):
    job_ids: list[str]


class JobStatusUpdateRequest(BaseModel):
    status: str
    notes: str | None = None


class BatchJobStatusUpdateRequest(BaseModel):
    job_ids: list[str]
    status: str
    notes: str | None = None


class BatchJobStatusResponse(BaseModel):
    updated_count: int
    status: str
    job_ids: list[str]


class SavedJobResponse(BaseModel):
    saved_id: str
    job_id: str
    title: str
    company: str
    location: str | None = None
    salary: str = "Not disclosed"
    status: str
    notes: str | None = None
    application_url: str
    posted_at: str | None = None
    updated_at: str
    match_score: float | None = None
    match_recommendation: str | None = None
    match_explanation: str | None = None


class JobSyncRequest(BaseModel):
    source: str = "all"
    freshness_hours: int = 24
    skills: list[str] | None = None
