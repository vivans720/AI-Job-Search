import uuid
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SearchRecord(Base):
    __tablename__ = "searches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    query_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_query: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    sources_used: Mapped[list[str]] = mapped_column(JSONB, default=list)

    total_discovered: Mapped[int] = mapped_column(Integer, default=0)
    filtered_by_freshness: Mapped[int] = mapped_column(Integer, default=0)
    deduplicated: Mapped[int] = mapped_column(Integer, default=0)
    matched: Mapped[int] = mapped_column(Integer, default=0)
    fresh_results: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
