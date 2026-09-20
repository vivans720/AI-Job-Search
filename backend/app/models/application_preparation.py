import uuid
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ApplicationPreparation(Base):
    __tablename__ = "application_preparations"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_user_job_prep"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Resume handling
    resume_mode: Mapped[str] = mapped_column(String(50), default="EXISTING")  # EXISTING | TAILORED
    resume_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True
    )
    tailored_resume_content: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Cover letter
    cover_letter: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Q&A screening questions
    question_answers: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)

    # Status & Autonomy gate
    # PREPARING | FILLING | READY_FOR_REVIEW | APPROVED | SUBMITTED | FAILED
    status: Mapped[str] = mapped_column(String(50), default="DRAFT", index=True)

    # Extra metadata (e.g. models used, tokens, source notes)
    metadata_info: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    job: Mapped["Job"] = relationship("Job")
    resume: Mapped["Resume | None"] = relationship("Resume")
