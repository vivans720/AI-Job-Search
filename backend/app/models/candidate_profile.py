import uuid
from datetime import datetime, timezone
from typing import Any
from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    source_resume_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True
    )
    experience_level: Mapped[str] = mapped_column(String(50), default="FRESHER")
    experience_years: Mapped[int] = mapped_column(Integer, default=0)

    target_roles: Mapped[list[str]] = mapped_column(JSONB, default=list)
    excluded_roles: Mapped[list[str]] = mapped_column(JSONB, default=list)

    skills: Mapped[list[str]] = mapped_column(JSONB, default=list)
    programming_languages: Mapped[list[str]] = mapped_column(JSONB, default=list)
    frameworks: Mapped[list[str]] = mapped_column(JSONB, default=list)
    databases: Mapped[list[str]] = mapped_column(JSONB, default=list)
    cloud: Mapped[list[str]] = mapped_column(JSONB, default=list)
    tools: Mapped[list[str]] = mapped_column(JSONB, default=list)

    projects: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    education: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    work_experience: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    certifications: Mapped[list[str]] = mapped_column(JSONB, default=list)

    preferred_locations: Mapped[list[str]] = mapped_column(JSONB, default=list)
    remote_preference: Mapped[bool] = mapped_column(Boolean, default=True)
    internship_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    fulltime_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    minimum_salary_lpa: Mapped[float | None] = mapped_column(Float, nullable=True)

    manual_overrides: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user: Mapped["User"] = relationship("User", back_populates="candidate_profile")
    source_resume: Mapped["Resume | None"] = relationship(
        "Resume", back_populates="candidate_profiles"
    )
