import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class DailyDigestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    run_id: Optional[uuid.UUID] = None
    digest_date: datetime
    summary: str
    job_ids: list[str] = Field(default_factory=list)
    total_found: int = 0
    strong_matches_count: int = 0
    status: str
    metadata_info: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class DailyDigestListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    digest_date: datetime
    summary_preview: str
    job_count: int
    strong_matches_count: int
    status: str
    created_at: datetime


class CreateDailyDigestRequest(BaseModel):
    summary: str
    job_ids: list[str] = Field(default_factory=list)
    status: str = "DELIVERED"
    metadata_info: Optional[dict[str, Any]] = None


class ScheduledSearchTriggerRequest(BaseModel):
    freshness_hours: int = 24
    match_threshold: Optional[int] = None
    dry_run: bool = False
