from datetime import datetime, timezone
import pytest

from app.services.dedup_service import (
    DeduplicationService,
    compute_job_hash,
    is_direct_company_url,
    select_canonical_job,
)
from app.sources.base import NormalizedJob


def make_test_job(
    source="internshala",
    source_job_id=None,
    title="Backend Developer",
    company="Swiggy",
    location="Bengaluru",
    source_url="https://internshala.com/job/101",
    application_url=None,
    description="Python FastAPI backend developer position.",
) -> NormalizedJob:
    actual_app_url = application_url or source_url
    norm_hash = compute_job_hash(company, title, location)
    return NormalizedJob(
        source=source,
        source_job_id=source_job_id,
        title=title,
        normalized_title=title,
        role_category="BACKEND",
        company_name=company,
        normalized_company=company,
        description=description,
        location=location,
        normalized_location=location,
        remote_type="ONSITE",
        employment_type="FULL_TIME",
        experience_min=0,
        experience_max=1,
        source_url=source_url,
        application_url=actual_app_url,
        job_hash=norm_hash,
        required_skills=["Python", "FastAPI"],
    )


def test_level_1_exact_url_dedup():
    svc = DeduplicationService()
    job1 = make_test_job(source_url="https://example.com/job/42", application_url="https://example.com/job/42")
    job2 = make_test_job(source="naukri", source_url="https://example.com/job/42", application_url="https://example.com/job/42")

    is_dup, reason = svc.are_duplicates(job1, job2)
    assert is_dup is True
    assert "LEVEL_1" in reason


def test_level_2_source_job_id_dedup():
    svc = DeduplicationService()
    job1 = make_test_job(source="internshala", source_job_id="same-id-99", source_url="https://internshala.com/j1")
    job2 = make_test_job(source="internshala", source_job_id="same-id-99", source_url="https://internshala.com/j2")

    is_dup, reason = svc.are_duplicates(job1, job2)
    assert is_dup is True
    assert "LEVEL_2" in reason


def test_level_3_normalized_metadata_dedup():
    svc = DeduplicationService()
    job1 = make_test_job(company="Razorpay", title="SDE 1", location="Bengaluru", source_url="https://s1.com/1")
    job2 = make_test_job(company="razorpay", title="SDE 1", location="bengaluru", source_url="https://s2.com/2")

    is_dup, reason = svc.are_duplicates(job1, job2)
    assert is_dup is True
    assert "LEVEL_3" in reason


def test_level_4_fuzzy_description_dedup():
    svc = DeduplicationService(description_threshold=0.8)
    desc1 = "Looking for a proactive Full Stack Developer Intern with strong fundamentals in React, Node.js, and TypeScript."
    desc2 = "Looking for a proactive Full Stack Developer Intern with strong fundamentals in React, Node.js, and TypeScript to join our team."
    job1 = make_test_job(company="Razorpay", title="Full Stack Intern", location="Bengaluru", description=desc1, source_url="https://s1.com/1")
    job2 = make_test_job(company="Razorpay", title="Full Stack Developer", location="Delhi", description=desc2, source_url="https://s2.com/2")

    is_dup, reason = svc.are_duplicates(job1, job2)
    assert is_dup is True
    assert "LEVEL_4" in reason


def test_level_5_embedding_dedup():
    svc = DeduplicationService(embedding_threshold=0.9)
    job1 = make_test_job(
        company="Google",
        title="Software Engineer",
        location="Bangalore",
        description="Core infrastructure and distributed file systems engineering.",
        source_url="https://s1.com/1",
    )
    job2 = make_test_job(
        company="Google",
        title="Application Engineer",
        location="Hyderabad",
        description="Internal corporate productivity tooling and developer dashboards.",
        source_url="https://s2.com/2",
    )

    embed1 = [0.1] * 384
    embed2 = [0.1001] * 384  # Cosine similarity > 0.99
    is_dup, reason = svc.are_duplicates(job1, job2, embed1, embed2)
    assert is_dup is True
    assert "LEVEL_5" in reason


def test_canonical_job_selection_direct_company_url():
    job_aggregator = make_test_job(
        source="naukri",
        application_url="https://naukri.com/apply/123",
        description="Short description",
    )
    job_careers = make_test_job(
        source="company_careers",
        application_url="https://razorpay.com/careers/apply/123",
        description="Comprehensive detailed description with all requirements.",
    )

    canonical, duplicate = select_canonical_job(job_aggregator, job_careers)
    assert canonical.application_url == "https://razorpay.com/careers/apply/123"
    assert duplicate.application_url == "https://naukri.com/apply/123"
