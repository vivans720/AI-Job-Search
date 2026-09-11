from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


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
