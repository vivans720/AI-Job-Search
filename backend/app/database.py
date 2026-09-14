from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_pgvector() -> None:
    """Ensure pgvector extension is installed and schema columns are synchronized."""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        # Auto-migrate gateway and preference search columns if missing
        await conn.execute(text("""
            ALTER TABLE preferences
            ADD COLUMN IF NOT EXISTS ai_fallback_provider VARCHAR(100),
            ADD COLUMN IF NOT EXISTS ai_fallback_model VARCHAR(100),
            ADD COLUMN IF NOT EXISTS ai_provider_config JSONB,
            ADD COLUMN IF NOT EXISTS experience_level VARCHAR(50) DEFAULT 'ALL',
            ADD COLUMN IF NOT EXISTS preferred_locations JSONB DEFAULT '[]'::jsonb,
            ADD COLUMN IF NOT EXISTS role_type VARCHAR(50) DEFAULT 'ALL',
            ADD COLUMN IF NOT EXISTS source_boards JSONB DEFAULT '["LINKEDIN", "NAUKRI", "INTERNSHALA"]'::jsonb;
        """))
        # Auto-migrate match versioning columns if missing
        await conn.execute(text("""
            ALTER TABLE matches
            ADD COLUMN IF NOT EXISTS algorithm_version VARCHAR(32) DEFAULT 'v2.1',
            ADD COLUMN IF NOT EXISTS profile_version VARCHAR(64),
            ADD COLUMN IF NOT EXISTS preference_version VARCHAR(64),
            ADD COLUMN IF NOT EXISTS job_version VARCHAR(64);
        """))
