from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field, field_validator


class SkillPartition(BaseModel):
    matched: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


class TransferableDetail(BaseModel):
    candidate_skill: str
    job_skill: str
    credit: float


class MatchBreakdown(BaseModel):
    overall_score: float
    skill_score: float
    semantic_score: float = 0.0
    experience_score: float = 0.0
    role_score: float = 0.0
    location_score: float = 0.0
    preference_score: float = 0.0
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    transferable_skills: list[str] = Field(default_factory=list)
    required_skills: SkillPartition | None = None
    preferred_skills: SkillPartition | None = None
    transferable_details: list[TransferableDetail] = Field(default_factory=list)
    experience_eligible: bool = True
    location_eligible: bool = True
    confidence: float = 1.0
    confidence_label: str = "HIGH"
    explanation: str | None = None
    recommendation: str  # STRONG_MATCH, GOOD_MATCH, CONSIDER, LOW_PRIORITY, SKIP

    @field_validator("required_skills", "preferred_skills", mode="before")
    @classmethod
    def coerce_skill_partition(cls, v: Any) -> Any:
        if isinstance(v, list):
            return SkillPartition(matched=[], missing=v) if v else None
        return v


class TransferableMatchItem(BaseModel):
    job_skill: str
    candidate_skill: str
    rationale: str
    credit: float


class ExperienceStatus(BaseModel):
    eligible: bool
    candidate_years: float
    required_min: float | None = None
    required_max: float | None = None
    summary: str


class LocationStatus(BaseModel):
    eligible: bool
    job_location: str
    remote_type: str | None = None
    candidate_locations: list[str] = Field(default_factory=list)
    remote_allowed: bool = True
    summary: str


class WhyThisJobResponse(BaseModel):
    job_id: str
    job_title: str
    company_name: str
    overall_score: float
    verdict: str  # APPLY, CONSIDER, SKIP
    recommendation: str  # STRONG_MATCH, GOOD_MATCH, CONSIDER, LOW_PRIORITY, SKIP
    headline: str
    strong_matches: list[str] = Field(default_factory=list)
    transferable_matches: list[TransferableMatchItem] = Field(default_factory=list)
    missing_critical: list[str] = Field(default_factory=list)
    missing_nice_to_have: list[str] = Field(default_factory=list)
    experience_status: ExperienceStatus
    location_status: LocationStatus
    recommendation_text: str
    rejection_reasons: list[str] = Field(default_factory=list)
    interview_talking_points: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    confidence_label: str = "HIGH"
    is_llm_generated: bool = False

