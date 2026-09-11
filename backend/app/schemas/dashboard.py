from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field
from app.schemas.job import JobListItem


class DashboardFunnel(BaseModel):
    fresh_jobs_count: int = Field(0, description="Fresh jobs discovered in the last 24 hours")
    strong_matches_count: int = Field(0, description="Jobs with match score >= 70")
    excellent_matches_count: int = Field(0, description="Jobs with match score >= 85")


class ApplicationStatusSummary(BaseModel):
    total_tracked: int = 0
    saved: int = 0
    applied: int = 0
    interviewing: int = 0
    offered: int = 0
    rejected: int = 0


class SkillGapItem(BaseModel):
    skill: str
    frequency: int
    demand_percentage: float = 0.0


class SourceHealthSummary(BaseModel):
    healthy_count: int = 0
    total_sources: int = 0
    status: str = "ok"
    sources: dict[str, bool] = Field(default_factory=dict)
    details: dict[str, Any] = Field(default_factory=dict)


class SyncStatusSummary(BaseModel):
    last_sync_time: datetime | None = None
    status: str = "idle"
    duration_seconds: float = 0.0
    jobs_discovered: int = 0
    jobs_added: int = 0


class DashboardResponse(BaseModel):
    greeting: str
    user_name: str | None = None
    funnel: DashboardFunnel
    recommended_jobs: list[JobListItem] = Field(default_factory=list)
    new_jobs: list[JobListItem] = Field(default_factory=list)
    application_summary: ApplicationStatusSummary
    skill_gaps: list[SkillGapItem] = Field(default_factory=list)
    source_health: SourceHealthSummary
    sync_status: SyncStatusSummary
