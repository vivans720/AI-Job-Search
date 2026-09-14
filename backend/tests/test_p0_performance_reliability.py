import uuid
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from app.models.job import Job
from app.models.candidate_profile import CandidateProfile
from app.models.preference import Preference
from app.models.match import Match
from app.services.matching_service import MatchingService, get_matching_service
from app.services.job_ingestion_service import JobIngestionService
from app.sources.base import JobSource, JobSearchQuery, RawJob, NormalizedJob


# ---------------------------------------------------------------------------
# 1. No N+1 query test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_n_plus_one_in_search_endpoint():
    """Verify search_jobs_endpoint does not issue N queries for N jobs."""
    from app.api.v1.jobs import search_jobs_endpoint
    from starlette.responses import Response

    mock_db = AsyncMock()

    # Fake user, profile, prefs
    user_id = uuid.uuid4()
    profile_id = uuid.uuid4()
    mock_user = MagicMock(id=user_id)
    mock_profile = CandidateProfile(
        id=profile_id,
        user_id=user_id,
        skills=["python", "fastapi"],
        target_roles=["Backend Engineer"],
        experience_years=1,
    )
    mock_prefs = Preference(user_id=user_id, freshness_hours=24)

    # 15 jobs
    mock_jobs_data = []
    for i in range(15):
        j_id = uuid.uuid4()
        job_obj = Job(
            id=j_id,
            title=f"Backend Engineer {i}",
            company_name=f"Company {i}",
            location="Bengaluru",
            remote_type="REMOTE",
            required_skills=["python"],
            posted_at=datetime.now(timezone.utc),
            posted_at_confidence="HIGH",
            source="internshala",
            application_url=f"https://example.com/job/{i}",
        )
        mock_jobs_data.append({
            "id": str(j_id),
            "title": job_obj.title,
            "company": job_obj.company_name,
            "location": job_obj.location,
            "remote_type": job_obj.remote_type,
            "employment_type": "FULL_TIME",
            "experience": "0-1 years",
            "source": "internshala",
            "application_url": job_obj.application_url,
            "posted_at": job_obj.posted_at.isoformat(),
            "quality_score": 80.0,
            "_entity": job_obj,
        })

    # Saved status mock
    saved_mock = MagicMock()
    saved_mock.all.return_value = []

    # Existing matches mock (empty to force bulk calculate)
    matches_mock = MagicMock()
    matches_mock.scalars.return_value.all.return_value = []

    # Mock execute returns
    execute_calls = []
    async def mock_execute(stmt, *args, **kwargs):
        execute_calls.append(str(stmt))
        sql = str(stmt).lower()
        if "saved_jobs" in sql:
            return saved_mock
        elif "matches" in sql:
            return matches_mock
        return MagicMock()

    mock_db.execute.side_effect = mock_execute

    with patch("app.api.v1.jobs.get_or_create_default_user", return_value=mock_user), \
         patch("app.api.v1.jobs.get_candidate_profile", return_value=mock_profile), \
         patch("app.api.v1.jobs.get_or_create_preferences", return_value=mock_prefs), \
         patch("app.api.v1.jobs.search_jobs_db", return_value=mock_jobs_data):

        resp = Response()
        results = await search_jobs_endpoint(
            response=resp,
            query=None,
            role=None,
            location=None,
            experience_min=None,
            experience_max=None,
            freshness_hours=24,
            include_remote=True,
            strict_location=False,
            sort_by="match",
            source=None,
            exclude_unpaid=False,
            view="all",
            min_score=None,
            page=1,
            page_size=50,
            limit=None,
            exclude_rejected=True,
            db=mock_db,
        )

        assert len(results) == 15
        assert all("match" in r and r["match"] is not None for r in results)

        # Confirm there are NO queries like "SELECT ... FROM jobs WHERE jobs.id = :id"
        individual_job_queries = [c for c in execute_calls if "from jobs" in c.lower() and "where jobs.id =" in c.lower()]
        assert len(individual_job_queries) == 0, f"Found N+1 job queries: {individual_job_queries}"


# ---------------------------------------------------------------------------
# 2. Match Cache hit, miss, and multi-dimensional invalidation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_match_cache_hit_and_invalidation():
    matching_svc = MatchingService()

    user_id = uuid.uuid4()
    profile = CandidateProfile(
        id=uuid.uuid4(),
        user_id=user_id,
        skills=["python", "fastapi"],
        target_roles=["Backend Engineer"],
        experience_years=2,
        preferred_locations=["Bengaluru"],
        minimum_salary_lpa=10.0,
    )

    job = Job(
        id=uuid.uuid4(),
        title="Senior Python Engineer",
        company_name="Acme Corp",
        location="Bengaluru",
        remote_type="REMOTE",
        required_skills=["python", "fastapi"],
        preferred_skills=["docker"],
        experience_min=2,
        experience_max=4,
    )

    prefs = Preference(
        user_id=user_id,
        priority_companies=["Acme Corp"],
        excluded_companies=[],
        experience_max_years=3,
        freshness_hours=24,
    )

    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    # Pass 1: Miss -> calculates and returns match
    mock_res_empty = MagicMock()
    mock_res_empty.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res_empty

    match1 = await matching_svc.get_or_calculate_match(mock_db, job, profile, prefs)
    assert match1.overall_score >= 70.0
    assert match1.algorithm_version == matching_svc.ALGORITHM_VERSION
    assert match1.profile_version == matching_svc.compute_profile_version(profile)
    assert match1.job_version == matching_svc.compute_job_version(job)
    assert match1.preference_version == matching_svc.compute_preference_version(prefs)

    # Pass 2: Cache Hit -> returned without re-evaluating
    mock_res_hit = MagicMock()
    mock_res_hit.scalar_one_or_none.return_value = match1
    mock_db.execute.return_value = mock_res_hit

    with patch.object(matching_svc, "evaluate_job", wraps=matching_svc.evaluate_job) as spy_eval:
        match2 = await matching_svc.get_or_calculate_match(mock_db, job, profile, prefs)
        assert match2.id == match1.id
        spy_eval.assert_not_called()

    # Invalidation 1: Profile version changes (skills updated)
    profile_updated = CandidateProfile(
        id=profile.id,
        user_id=user_id,
        skills=["go", "kubernetes"],  # Skills completely changed
        target_roles=["Backend Engineer"],
        experience_years=2,
    )
    assert matching_svc.compute_profile_version(profile_updated) != match1.profile_version

    with patch.object(matching_svc, "evaluate_job", wraps=matching_svc.evaluate_job) as spy_eval:
        match_prof_update = await matching_svc.get_or_calculate_match(mock_db, job, profile_updated, prefs)
        spy_eval.assert_called_once()
        assert match_prof_update.profile_version == matching_svc.compute_profile_version(profile_updated)

    # Invalidation 2: Job version changes (job skills updated)
    job_updated = Job(
        id=job.id,
        title=job.title,
        company_name=job.company_name,
        location=job.location,
        remote_type=job.remote_type,
        required_skills=["rust", "c++"],  # Job skills changed
        experience_min=2,
        experience_max=4,
    )
    assert matching_svc.compute_job_version(job_updated) != match1.job_version

    with patch.object(matching_svc, "evaluate_job", wraps=matching_svc.evaluate_job) as spy_eval:
        match_job_update = await matching_svc.get_or_calculate_match(mock_db, job_updated, profile, prefs)
        spy_eval.assert_called_once()
        assert match_job_update.job_version == matching_svc.compute_job_version(job_updated)

    # Invalidation 3: Preference version changes (company excluded)
    prefs_updated = Preference(
        user_id=user_id,
        priority_companies=[],
        excluded_companies=["Acme Corp"],  # Excluded company
        experience_max_years=3,
        freshness_hours=24,
    )
    assert matching_svc.compute_preference_version(prefs_updated) != match1.preference_version

    with patch.object(matching_svc, "evaluate_job", wraps=matching_svc.evaluate_job) as spy_eval:
        match_pref_update = await matching_svc.get_or_calculate_match(mock_db, job, profile, prefs_updated)
        spy_eval.assert_called_once()
        assert match_pref_update.preference_version == matching_svc.compute_preference_version(prefs_updated)


# ---------------------------------------------------------------------------
# 3. Multiple users cannot reuse each other's cached matches
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multi_user_isolation():
    matching_svc = MatchingService()

    user_a_id = uuid.uuid4()
    profile_a = CandidateProfile(
        id=uuid.uuid4(),
        user_id=user_a_id,
        skills=["python"],
        target_roles=["Backend Engineer"],
    )

    user_b_id = uuid.uuid4()
    profile_b = CandidateProfile(
        id=uuid.uuid4(),
        user_id=user_b_id,
        skills=["java"],
        target_roles=["Java Developer"],
    )

    job = Job(
        id=uuid.uuid4(),
        title="Python Developer",
        company_name="Tech Co",
        required_skills=["python"],
    )

    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    # User A matches
    mock_res_a = MagicMock()
    mock_res_a.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res_a
    match_a = await matching_svc.get_or_calculate_match(mock_db, job, profile_a)

    # User B matches
    mock_res_b = MagicMock()
    mock_res_b.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res_b
    match_b = await matching_svc.get_or_calculate_match(mock_db, job, profile_b)

    assert match_a.profile_id == profile_a.id
    assert match_b.profile_id == profile_b.id
    assert match_a.profile_id != match_b.profile_id
    assert match_a.overall_score != match_b.overall_score


# ---------------------------------------------------------------------------
# 4. Discovery succeeds when LLM enrichment / deep extraction fails
# ---------------------------------------------------------------------------

class MockFailingSource(JobSource):
    source_name = "failing_mock"
    enabled = True

    async def search(self, query: JobSearchQuery) -> list[RawJob]:
        return [
            RawJob(
                source=self.source_name,
                source_job_id="mock-101",
                title="Software Engineer",
                company_name="Apex Global",
                description="We need a great software engineer.",
                location="Bengaluru",
                remote_type="REMOTE",
                employment_type="FULL_TIME",
                posted_time_raw="1 hour ago",
                source_url="https://example.com/job/101",
                application_url="https://example.com/job/101",
            )
        ]

    def parse_html(self, html: str) -> list[RawJob]:
        return []

    async def get_job(self, url: str) -> RawJob | None:
        return None

    async def health_check(self) -> bool:
        return True

    async def normalize(self, raw: RawJob) -> NormalizedJob | None:
        return NormalizedJob(
            source=self.source_name,
            source_job_id=raw.source_job_id,
            title=raw.title,
            normalized_title="Software Engineer",
            company_name=raw.company_name,
            normalized_company="Apex Global",
            description=raw.description,
            role_category="Engineering",
            location=raw.location,
            normalized_location="Bengaluru",
            remote_type="REMOTE",
            employment_type="FULL_TIME",
            posted_at=datetime.now(timezone.utc),
            posted_at_confidence="HIGH",
            source_url=raw.source_url,
            application_url=raw.application_url,
            job_hash="mock-hash-101",
        )


@pytest.mark.asyncio
async def test_discovery_succeeds_when_ai_fails():
    ingestion_service = JobIngestionService()

    # Simulate skill extraction failure / timeout
    mock_extractor = MagicMock()
    mock_extractor.extract_skills = AsyncMock(side_effect=TimeoutError("AI Provider timeout"))
    ingestion_service.skill_extractor = mock_extractor

    # Simulate embedding failure
    mock_embedder = MagicMock()
    mock_embedder.embed_batch.side_effect = Exception("Embedding service unreachable")
    ingestion_service.embedding_provider = mock_embedder

    mock_db = AsyncMock()
    mock_db.begin_nested = MagicMock()
    mock_nested = AsyncMock()
    mock_db.begin_nested.return_value.__aenter__ = AsyncMock(return_value=mock_nested)
    mock_db.begin_nested.return_value.__aexit__ = AsyncMock()
    mock_db.commit = AsyncMock()

    # Mock DB company and job existence checks
    comp_res = MagicMock()
    comp_res.scalar_one_or_none.return_value = None
    job_res = MagicMock()
    job_res.scalar_one_or_none.return_value = None

    async def mock_exec(stmt, *args, **kwargs):
        s = str(stmt).lower()
        if "companies" in s:
            return comp_res
        elif "jobs" in s:
            return job_res
        return MagicMock(scalar_one_or_none=lambda: None)

    mock_db.execute.side_effect = mock_exec

    source = MockFailingSource()
    stats = await ingestion_service.ingest_source(mock_db, source, JobSearchQuery())

    # Verify discovery still persisted canonical job successfully
    assert stats["total_discovered"] == 1
    assert stats["canonical_saved"] == 1
    assert mock_db.commit.called
