import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    resumes: Mapped[list["Resume"]] = relationship(
        "Resume", back_populates="user", cascade="all, delete-orphan"
    )
    candidate_profile: Mapped["CandidateProfile | None"] = relationship(
        "CandidateProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    preferences: Mapped["Preference | None"] = relationship(
        "Preference", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
