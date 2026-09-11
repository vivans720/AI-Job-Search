import uuid
from datetime import datetime, timezone
from typing import Any
from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    source_job_id: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_title: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    role_category: Mapped[str | None] = mapped_column(String(50), index=True, nullable=True)

    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    company_name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)

    description: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    normalized_location: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    remote_type: Mapped[str] = mapped_column(String(50), default="ONSITE")
    employment_type: Mapped[str] = mapped_column(String(50), default="FULL_TIME")

    experience_min: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    experience_max: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    experience_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    experience_confidence: Mapped[str] = mapped_column(String(20), default="LOW")
    description_confidence: Mapped[str] = mapped_column(String(20), default="HIGH")

    salary_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_currency: Mapped[str] = mapped_column(String(10), default="INR")
    salary_period: Mapped[str] = mapped_column(String(20), default="YEAR")
    salary_raw: Mapped[str | None] = mapped_column(String(255), nullable=True)

    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    posted_at_raw: Mapped[str | None] = mapped_column(String(100), nullable=True)
    posted_at_confidence: Mapped[str] = mapped_column(String(20), default="LOW")

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    application_url: Mapped[str] = mapped_column(String(2048), nullable=False)

    job_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    required_skills: Mapped[list[str]] = mapped_column(JSONB, default=list)
    preferred_skills: Mapped[list[str]] = mapped_column(JSONB, default=list)

    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    company: Mapped["Company | None"] = relationship("Company", back_populates="jobs")
    saved_jobs: Mapped[list["SavedJob"]] = relationship("SavedJob", back_populates="job", cascade="all, delete-orphan")
    matches: Mapped[list["Match"]] = relationship("Match", back_populates="job", cascade="all, delete-orphan")
