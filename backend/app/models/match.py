import uuid
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint("job_id", "profile_id", name="uq_job_profile_match"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False
    )

    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    skill_score: Mapped[float] = mapped_column(Float, default=0.0)
    semantic_score: Mapped[float] = mapped_column(Float, default=0.0)
    experience_score: Mapped[float] = mapped_column(Float, default=0.0)
    role_score: Mapped[float] = mapped_column(Float, default=0.0)
    location_score: Mapped[float] = mapped_column(Float, default=0.0)
    preference_score: Mapped[float] = mapped_column(Float, default=0.0)

    matched_skills: Mapped[list[str]] = mapped_column(JSONB, default=list)
    missing_skills: Mapped[list[str]] = mapped_column(JSONB, default=list)
    transferable_skills: Mapped[list[str]] = mapped_column(JSONB, default=list)

    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    confidence_label: Mapped[str] = mapped_column(String(20), default="HIGH")  # HIGH, MEDIUM, LOW

    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation: Mapped[str] = mapped_column(String(50), default="CONSIDER")  # STRONG_MATCH, GOOD_MATCH, CONSIDER, LOW_PRIORITY, SKIP

    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    algorithm_version: Mapped[str | None] = mapped_column(String(32), nullable=True, default="v2.1", index=True)
    profile_version: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    preference_version: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    job_version: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    job: Mapped["Job"] = relationship("Job", back_populates="matches")
