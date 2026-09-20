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
        # Auto-migrate application_preparations table if missing
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS application_preparations (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                resume_mode VARCHAR(50) DEFAULT 'EXISTING',
                resume_id UUID REFERENCES resumes(id) ON DELETE SET NULL,
                tailored_resume_content JSONB,
                cover_letter TEXT,
                question_answers JSONB DEFAULT '[]'::jsonb,
                status VARCHAR(50) DEFAULT 'DRAFT',
                metadata_info JSONB DEFAULT '{}'::jsonb,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_user_job_prep UNIQUE (user_id, job_id)
            )
        """))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_app_prep_user_id ON application_preparations(user_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_app_prep_job_id ON application_preparations(job_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_app_prep_status ON application_preparations(status)"))

        # Auto-migrate daily_digests table if missing
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS daily_digests (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                run_id UUID REFERENCES agent_runs(id) ON DELETE SET NULL,
                digest_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                summary TEXT NOT NULL,
                job_ids JSONB DEFAULT '[]'::jsonb,
                total_found INTEGER DEFAULT 0,
                strong_matches_count INTEGER DEFAULT 0,
                status VARCHAR(50) DEFAULT 'DELIVERED',
                metadata_info JSONB DEFAULT '{}'::jsonb,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_daily_digests_user_id ON daily_digests(user_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_daily_digests_digest_date ON daily_digests(digest_date)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_daily_digests_status ON daily_digests(status)"))

        # Auto-migrate digest_notified_jobs table if missing
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS digest_notified_jobs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                digest_id UUID REFERENCES daily_digests(id) ON DELETE SET NULL,
                notified_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_user_job_digest_notified UNIQUE (user_id, job_id)
            )
        """))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_digest_notified_user_id ON digest_notified_jobs(user_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_digest_notified_job_id ON digest_notified_jobs(job_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_digest_notified_notified_at ON digest_notified_jobs(notified_at)"))
