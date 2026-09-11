"""
Tests for Recall-First Architecture Invariants:
1. Title retention (unconventional engineering titles like 'Product Engineer', 'Solutions Engineer' never dropped).
2. Skill retention (0 matched skills never drops job, returns score & breakdown with is_excluded=False).
3. Experience parsing ('5 days a week' preserved with confidence='LOW', not parsed as 5 years).
4. LinkedIn detail hydration failure (fallback preserves job with description_confidence='LOW').
5. 24h strict freshness cutoff boundary in Asia/Kolkata (IST).
6. Multi-source deduplication (merging secondary source metadata into other_sources).
7. Low AI score (e.g. 20% SKIP) retained and retrievable.
8. Unpaid vs Salary unknown distinction (unknown salary is NOT classified as unpaid).
9. Schema serialization with recall-first metadata.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import pytest

from app.models.candidate_profile import CandidateProfile
from app.models.job import Job
from app.models.preference import Preference
from app.schemas.job import JobListItem
from app.services.dedup_service import select_canonical_job
from app.services.freshness_service import FreshnessService, IST
from app.services.matching_service import MatchingService
from app.sources.adapters.linkedin import LinkedInAdapter
from app.sources.base import NormalizedJob, RawJob
from app.utils.normalization import is_unpaid_salary_text, parse_experience_requirement


def test_title_retention_unconventional_titles():
    """Invariant 1: Unconventional titles like 'Product Engineer', 'Solutions Engineer' are not excluded."""
    matcher = MatchingService()
    profile = CandidateProfile(
        target_roles=["Full Stack Developer", "Backend Developer", "Software Engineer"],
        skills=["Python", "FastAPI", "React"],
        experience_years=1,
        preferred_locations=["Remote", "Bengaluru"],
        remote_preference=True,
    )

    unconventional_titles = [
        "Product Engineer",
        "Solutions Engineer",
        "Web Engineer",
        "Application Developer",
        "Platform Engineer",
    ]

    for title in unconventional_titles:
        job = Job(
            title=title,
            company_name="Acme Tech",
            location="Remote",
            remote_type="REMOTE",
            employment_type="FULL_TIME",
            required_skills=["Python", "FastAPI"],
            experience_min=1,
            experience_max=2,
            experience_confidence="HIGH",
            description_confidence="HIGH",
        )
        eval_res = matcher.evaluate_job(job, profile)
        assert eval_res["is_excluded"] is False
        assert eval_res["overall_score"] > 0
        assert "Python" in eval_res["matched_skills"]


def test_skill_retention_zero_matched_skills():
    """Invariant 2: A job with 0 matched skills is never dropped, scored with is_excluded=False."""
    matcher = MatchingService()
    profile = CandidateProfile(
        target_roles=["Backend Developer"],
        skills=["Python", "FastAPI"],
        experience_years=1,
        preferred_locations=["Remote"],
        remote_preference=True,
    )

    job = Job(
        title="Rust Developer",
        company_name="Crypto Labs",
        location="Remote",
        remote_type="REMOTE",
        employment_type="FULL_TIME",
        required_skills=["Rust", "Solana", "Anchor"],
        experience_min=1,
        experience_max=2,
        experience_confidence="HIGH",
        description_confidence="HIGH",
    )

    eval_res = matcher.evaluate_job(job, profile)
    assert eval_res["is_excluded"] is False
    assert len(eval_res["matched_skills"]) == 0
    assert len(eval_res["missing_skills"]) == 3
    assert eval_res["recommendation"] in ["SKIP", "LOW_PRIORITY"]
    assert eval_res["overall_score"] >= 0.0


def test_experience_parsing_and_retention():
    """Invariant 3: '5 days a week' parsed with confidence=LOW, not as 5 years experience."""
    min_exp, max_exp, raw_text, conf = parse_experience_requirement("Work 5 days a week, 8 hours a day")
    assert min_exp is None
    assert max_exp is None
    assert conf == "LOW"

    min_exp, max_exp, raw_text, conf = parse_experience_requirement("2-4 years of experience required")
    assert min_exp == 2
    assert max_exp == 4
    assert conf == "HIGH"

    min_exp, max_exp, raw_text, conf = parse_experience_requirement("Freshers can apply. 0 years required")
    assert min_exp == 0
    assert max_exp == 0
    assert conf == "HIGH"

    min_exp, max_exp, raw_text, conf = parse_experience_requirement("Minimum 3 yrs experience")
    assert min_exp == 3
    assert max_exp is None
    assert conf == "HIGH"


@pytest.mark.asyncio
async def test_linkedin_hydration_failure_retention():
    """Invariant 4: LinkedIn detail page failure preserves job snippet with description_confidence=LOW."""
    adapter = LinkedInAdapter()
    raw = RawJob(
        source="linkedin",
        source_job_id="12345678",
        source_url="https://www.linkedin.com/jobs/view/12345678",
        title="Software Engineer",
        company_name="Startup Co",
        location="Bengaluru, India",
        description="Short snippet from search list",
        posted_time_raw="2 hours ago",
    )

    norm = await adapter.normalize(raw)
    assert norm is not None
    assert norm.title == "Software Engineer"
    assert norm.description == "Short snippet from search list"
    assert norm.description_confidence == "LOW"
    assert norm.source == "linkedin"


def test_freshness_cutoff_boundary():
    """Invariant 5: 24h strict freshness cutoff boundary in Asia/Kolkata (IST)."""
    svc = FreshnessService()
    now_ist = datetime.now(IST)

    dt_23h = now_ist - timedelta(hours=23)
    assert svc.is_fresh(dt_23h, confidence="HIGH", freshness_hours=24, reference_now=now_ist) is True

    dt_25h = now_ist - timedelta(hours=25)
    assert svc.is_fresh(dt_25h, confidence="HIGH", freshness_hours=24, reference_now=now_ist) is False

    dt_24h = now_ist - timedelta(hours=24)
    assert svc.is_fresh(dt_24h, confidence="HIGH", freshness_hours=24, reference_now=now_ist) is True

    dt_few, conf_few = svc.parse_relative_time("few hours ago", reference_now=now_ist)
    assert dt_few is not None
    assert conf_few == "HIGH"
    assert svc.is_fresh(dt_few, confidence=conf_few, freshness_hours=24, reference_now=now_ist) is True


def test_multi_source_dedup_merges_other_sources():
    """Invariant 6: Multi-source dedup preserves secondary source records in raw_data['other_sources']."""
    now = datetime.now(timezone.utc)
    primary = NormalizedJob(
        source="linkedin",
        source_job_id="li_101",
        source_url="https://linkedin.com/jobs/view/101",
        application_url="https://acme.com/jobs/apply/101",
        title="Full Stack Developer",
        normalized_title="Full Stack Developer",
        role_category="FULL_STACK",
        company_name="GlobalTech",
        normalized_company="GlobalTech",
        location="Bengaluru",
        normalized_location="Bengaluru",
        remote_type="ONSITE",
        employment_type="FULL_TIME",
        job_hash="hash101",
        description="Detailed job description from LinkedIn with many skills and requirements.",
        posted_at=now - timedelta(hours=3),
        posted_at_confidence="HIGH",
        raw_data={},
    )

    secondary = NormalizedJob(
        source="naukri",
        source_job_id="nk_202",
        source_url="https://naukri.com/job/202",
        application_url="https://naukri.com/job/202",
        title="Full Stack Developer",
        normalized_title="Full Stack Developer",
        role_category="FULL_STACK",
        company_name="GlobalTech",
        normalized_company="GlobalTech",
        location="Bengaluru",
        normalized_location="Bengaluru",
        remote_type="ONSITE",
        employment_type="FULL_TIME",
        job_hash="hash202",
        description="Shorter naukri description",
        posted_at=now - timedelta(hours=5),
        posted_at_confidence="HIGH",
        raw_data={},
    )

    canonical, duplicate = select_canonical_job(primary, secondary)
    assert canonical.source == "linkedin"
    assert "other_sources" in canonical.raw_data
    other = canonical.raw_data["other_sources"]
    assert len(other) == 1
    assert other[0]["source"] == "naukri"
    assert other[0]["source_url"] == "https://naukri.com/job/202"
    assert other[0]["source_job_id"] == "nk_202"


def test_low_ai_score_retained():
    """Invariant 7: Low AI score (e.g. 20%) is retained and recommendation is SKIP without dropping."""
    matcher = MatchingService()
    profile = CandidateProfile(
        target_roles=["Frontend Engineer"],
        skills=["React", "CSS"],
        experience_years=0,
        preferred_locations=["Bengaluru"],
        remote_preference=False,
    )

    job = Job(
        title="Database Administrator",
        company_name="DataCorp",
        location="Chennai",
        remote_type="ONSITE",
        employment_type="FULL_TIME",
        required_skills=["Oracle", "PL/SQL", "DBA"],
        experience_min=5,
        experience_max=8,
        experience_confidence="HIGH",
        description_confidence="HIGH",
    )

    eval_res = matcher.evaluate_job(job, profile)
    assert eval_res["is_excluded"] is False
    assert eval_res["recommendation"] == "SKIP"
    assert eval_res["overall_score"] <= 35.0


def test_unpaid_vs_salary_unknown_distinction():
    """Invariant 8: Unknown salary is NOT classified as unpaid."""
    assert is_unpaid_salary_text("Not disclosed") is False
    assert is_unpaid_salary_text("Competitive") is False
    assert is_unpaid_salary_text(None) is False
    assert is_unpaid_salary_text("") is False
    assert is_unpaid_salary_text("Best in industry") is False

    assert is_unpaid_salary_text("Unpaid internship") is True
    assert is_unpaid_salary_text("No stipend") is True
    assert is_unpaid_salary_text("Volunteer position") is True
    assert is_unpaid_salary_text("Expenses only") is True


def test_schema_serialization_recall_fields():
    """Invariant 9: JobListItem schema serializes recall-first fields cleanly."""
    item = JobListItem(
        id="123e4567-e89b-12d3-a456-426614174000",
        title="Software Engineer",
        company="Startup Co",
        location="Remote",
        remote_type="REMOTE",
        employment_type="FULL_TIME",
        salary="Not disclosed",
        salary_min=None,
        salary_max=None,
        experience="Experience unspecified",
        experience_min=None,
        experience_max=None,
        experience_confidence="LOW",
        description_confidence="LOW",
        source="linkedin",
        application_url="https://linkedin.com/jobs/view/123",
        other_sources=[{"source": "internshala", "url": "https://internshala.com/job/123"}],
    )

    data = item.model_dump()
    assert data["experience_confidence"] == "LOW"
    assert data["description_confidence"] == "LOW"
    assert data["salary_min"] is None
    assert len(data["other_sources"]) == 1
    assert data["other_sources"][0]["source"] == "internshala"


def test_experience_tier_fresher_and_range_eligibility():
    """Invariant 10: Early-career ranges (0-2y) are eligible for freshers and score high."""
    matcher = MatchingService()
    profile = CandidateProfile(
        target_roles=["Software Engineer"],
        skills=["Python"],
        experience_years=0,
        preferred_locations=["Remote"],
        remote_preference=True,
        internship_allowed=True,
    )

    # 0-2y entry level job
    fresher_range_job = Job(
        title="Associate Software Engineer",
        company_name="Tech Corp",
        location="Remote",
        remote_type="REMOTE",
        employment_type="FULL_TIME",
        required_skills=["Python"],
        experience_min=0,
        experience_max=2,
        experience_confidence="HIGH",
        description_confidence="HIGH",
    )
    res = matcher.evaluate_job(fresher_range_job, profile)
    assert res["is_excluded"] is False
    assert res["experience_score"] >= 90.0
    assert res["experience_eligible"] is True

    # Internship
    intern_job = Job(
        title="Python Intern",
        company_name="Tech Corp",
        location="Remote",
        remote_type="REMOTE",
        employment_type="INTERNSHIP",
        required_skills=["Python"],
        experience_min=None,
        experience_max=None,
        experience_confidence="LOW",
        description_confidence="HIGH",
    )
    intern_res = matcher.evaluate_job(intern_job, profile)
    assert intern_res["is_excluded"] is False
    assert intern_res["experience_score"] == 100.0
    assert intern_res["experience_eligible"] is True


def test_batch_status_schema_and_status_validation():
    """Invariant 11: Batch status schema serializes job IDs and validates statuses."""
    from app.schemas.job import BatchJobStatusUpdateRequest, BatchJobStatusResponse
    from app.services.job_service import VALID_STATUSES
    import uuid

    id1 = str(uuid.uuid4())
    id2 = str(uuid.uuid4())
    req = BatchJobStatusUpdateRequest(job_ids=[id1, id2], status="REJECTED")
    assert req.status == "REJECTED"
    assert len(req.job_ids) == 2
    assert "REJECTED" in VALID_STATUSES
    assert "SAVED" in VALID_STATUSES
    assert "DISCOVERED" in VALID_STATUSES

    resp = BatchJobStatusResponse(updated_count=2, status="REJECTED", job_ids=[id1, id2])
    assert resp.updated_count == 2
    assert resp.job_ids == [id1, id2]


