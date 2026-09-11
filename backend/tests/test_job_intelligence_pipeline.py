import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.candidate_profile import CandidateProfile
from app.models.company import Company
from app.models.job import Job
from app.models.preference import Preference
from app.models.user import User
from app.services.job_ingestion_service import JobIngestionService
from app.sources.base import JobSearchQuery, JobSource, NormalizedJob, RawJob


class MockSource(JobSource):
    source_name = "test_source"

    async def search(self, query: JobSearchQuery) -> list[RawJob]:
        return [
            RawJob(
                source="test_source",
                source_job_id="test-job-43-1",
                title="Full Stack Python Developer",
                company_name="Acme Tech",
                location="Bengaluru, India",
                description="We need a strong Python developer with FastAPI, React, Docker, and SQL experience.",
                source_url="https://example.com/jobs/1",
                application_url="https://example.com/apply/1",
            )
        ]

    async def get_job(self, url: str) -> RawJob | None:
        return None

    async def normalize(self, raw: RawJob) -> NormalizedJob | None:
        return NormalizedJob(
            source=raw.source,
            source_job_id=raw.source_job_id,
            title=raw.title,
            normalized_title="Full Stack Developer",
            role_category="FULL_STACK",
            company_name=raw.company_name,
            normalized_company="acme tech",
            description=raw.description,
            location=raw.location,
            normalized_location="Bengaluru",
            remote_type="ONSITE",
            employment_type="FULL_TIME",
            experience_min=0,
            experience_max=2,
            experience_confidence="HIGH",
            posted_at=datetime.now(timezone.utc),
            posted_at_confidence="HIGH",
            source_url=raw.source_url,
            application_url=raw.application_url or raw.source_url,
            job_hash="test-hash-43-1",
            required_skills=[],  # Intentionally empty to test AI/hybrid skill extraction & normalization
            preferred_skills=[],
        )

    async def health_check(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_job_intelligence_pipeline_e2e():
    """Verify Phase 43: Ingestion -> AI extraction -> normalization -> embedding -> persistence -> matching."""
    service = JobIngestionService()
    source = MockSource()

    class AsyncContextManagerMock:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    mock_db = AsyncMock()
    mock_db.begin_nested = MagicMock(return_value=AsyncContextManagerMock())

    # Mock DB executions
    def make_mock_result(scalar_value):
        res = MagicMock()
        res.scalar_one_or_none.return_value = scalar_value
        return res

    mock_company = Company(id=uuid.uuid4(), name="Acme Tech", normalized_name="acme tech")
    mock_user = User(id=uuid.uuid4(), email="candidate@example.com")
    mock_profile = CandidateProfile(
        id=uuid.uuid4(),
        user_id=mock_user.id,
        experience_level="FRESHER",
        experience_years=1,
        skills=["python", "fastapi", "react"],
        target_roles=["Full Stack Developer"],
    )
    mock_prefs = Preference(user_id=mock_user.id, freshness_hours=24)

    # Sequence of DB execute calls:
    # 1. Company query -> None (new company)
    # 2. Existing Job query -> None (new job)
    # 3. User query -> mock_user
    # 4. Profile query -> mock_profile
    # 5. Prefs query -> mock_prefs
    # 6. Subsequent queries for match calculation
    mock_db.execute.side_effect = [
        make_mock_result(None),          # company lookup
        make_mock_result(None),          # existing job lookup
        make_mock_result(mock_user),     # user lookup
        make_mock_result(mock_profile),  # profile lookup
        make_mock_result(mock_prefs),    # prefs lookup
        make_mock_result(None),          # match record lookup
    ]

    stats = await service.ingest_source(mock_db, source)

    assert stats["source"] == "test_source"
    assert stats["total_discovered"] == 1
    assert stats["canonical_saved"] == 1
    assert stats["ai_extracted_skills"] >= 1
    assert stats["embeddings_generated"] == 1
    assert stats["matches_evaluated"] == 1
    assert mock_db.commit.call_count >= 1
