import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Preference(Base):
    __tablename__ = "preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    freshness_hours: Mapped[int] = mapped_column(Integer, default=24)
    experience_max_years: Mapped[int] = mapped_column(Integer, default=2)

    preferred_technologies: Mapped[list[str]] = mapped_column(JSONB, default=list)
    preferred_industries: Mapped[list[str]] = mapped_column(JSONB, default=list)
    priority_companies: Mapped[list[str]] = mapped_column(JSONB, default=list)
    excluded_companies: Mapped[list[str]] = mapped_column(JSONB, default=list)

    match_threshold: Mapped[int] = mapped_column(Integer, default=60)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user: Mapped["User"] = relationship("User", back_populates="preferences")
