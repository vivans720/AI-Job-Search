import uuid
from datetime import datetime, timezone
from typing import Any
from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    resume_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship("User", back_populates="resumes")
    candidate_profiles: Mapped[list["CandidateProfile"]] = relationship(
        "CandidateProfile", back_populates="source_resume"
    )
