import uuid
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import DateTime, ForeignKey, Integer, String
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
    sync_interval_hours: Mapped[int] = mapped_column(Integer, default=24)
    auto_sync_enabled: Mapped[bool] = mapped_column(default=False)
    last_auto_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # Dynamic AI Provider Overrides (Phase 39 & Gateway Phase)
    ai_provider: Mapped[str | None] = mapped_column(nullable=True, default=None)
    ai_model: Mapped[str | None] = mapped_column(nullable=True, default=None)
    ai_base_url: Mapped[str | None] = mapped_column(nullable=True, default=None)
    ai_api_key: Mapped[str | None] = mapped_column(nullable=True, default=None)
    ai_fallback_provider: Mapped[str | None] = mapped_column(nullable=True, default=None)
    ai_fallback_model: Mapped[str | None] = mapped_column(nullable=True, default=None)
    ai_provider_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=None)

    # First-Launch Onboarding (Phase 42)
    setup_completed: Mapped[bool] = mapped_column(default=False)

    # Search Preferences (R1)
    experience_level: Mapped[str] = mapped_column(String(50), default="ALL")
    preferred_locations: Mapped[list[str]] = mapped_column(JSONB, default=list)
    role_type: Mapped[str] = mapped_column(String(50), default="ALL")
    source_boards: Mapped[list[str]] = mapped_column(
        JSONB, default=lambda: ["LINKEDIN", "NAUKRI", "INTERNSHALA"]
    )

    # Configurable Agent Autonomy (Phase 7)
    autonomy_policy: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=lambda: {
            "search": "autonomous",
            "analyze": "autonomous",
            "save_job": "approval_required",
            "dismiss_job": "approval_required",
            "update_pipeline_status": "approval_required",
        },
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user: Mapped["User"] = relationship("User", back_populates="preferences")

    def __init__(self, **kwargs):
        kwargs.setdefault("freshness_hours", 24)
        kwargs.setdefault("experience_max_years", 2)
        kwargs.setdefault("match_threshold", 60)
        kwargs.setdefault("sync_interval_hours", 24)
        kwargs.setdefault("auto_sync_enabled", False)
        kwargs.setdefault("setup_completed", False)
        kwargs.setdefault("experience_level", "ALL")
        kwargs.setdefault("role_type", "ALL")
        kwargs.setdefault("preferred_locations", [])
        kwargs.setdefault("source_boards", ["LINKEDIN", "NAUKRI", "INTERNSHALA"])
        kwargs.setdefault("preferred_technologies", [])
        kwargs.setdefault("preferred_industries", [])
        kwargs.setdefault("priority_companies", [])
        kwargs.setdefault("excluded_companies", [])
        super().__init__(**kwargs)
