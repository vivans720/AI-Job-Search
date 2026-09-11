import pytest
from app.sources.base import NormalizedJob
from app.utils.validation import validate_normalized_job


def test_validate_normalized_job_success():
    job = NormalizedJob(
        source="internshala",
        source_job_id="test_123",
        title="Python Backend Developer",
        normalized_title="python backend developer",
        role_category="BACKEND",
        company_name="Acme Tech",
        normalized_company="acme tech",
        description="We are hiring a Python backend developer with FastAPI and PostgreSQL knowledge.",
        location="Bangalore",
        normalized_location="Bangalore",
        remote_type="ONSITE",
        employment_type="FULL_TIME",
        source_url="https://internshala.com/job/detail/123",
        application_url="https://internshala.com/job/detail/123",
        job_hash="abcdef1234567890",
        required_skills=["Python", "FastAPI"],
    )
    is_valid, reason = validate_normalized_job(job)
    assert is_valid is True
    assert reason is None


def test_validate_normalized_job_short_title():
    job = NormalizedJob(
        source="internshala",
        title="Py",
        normalized_title="py",
        role_category="BACKEND",
        company_name="Acme Tech",
        normalized_company="acme tech",
        description="We are hiring a Python backend developer.",
        normalized_location="Bangalore",
        remote_type="ONSITE",
        employment_type="FULL_TIME",
        source_url="https://example.com/job/1",
        application_url="https://example.com/job/1",
        job_hash="abcdef1234567890",
    )
    is_valid, reason = validate_normalized_job(job)
    assert is_valid is False
    assert reason == "title_too_short_or_empty"


def test_validate_normalized_job_invalid_urls():
    job = NormalizedJob(
        source="internshala",
        title="Python Backend Developer",
        normalized_title="python backend developer",
        role_category="BACKEND",
        company_name="Acme Tech",
        normalized_company="acme tech",
        description="We are hiring a Python backend developer with good skills.",
        normalized_location="Bangalore",
        remote_type="ONSITE",
        employment_type="FULL_TIME",
        source_url="invalid_url",
        application_url="https://example.com/job/1",
        job_hash="abcdef1234567890",
    )
    is_valid, reason = validate_normalized_job(job)
    assert is_valid is False
    assert reason == "invalid_source_url"


def test_validate_normalized_job_empty_description():
    job = NormalizedJob(
        source="internshala",
        title="Python Backend Developer",
        normalized_title="python backend developer",
        role_category="BACKEND",
        company_name="Acme Tech",
        normalized_company="acme tech",
        description="Too short",
        normalized_location="Bangalore",
        remote_type="ONSITE",
        employment_type="FULL_TIME",
        source_url="https://example.com/job/1",
        application_url="https://example.com/job/1",
        job_hash="abcdef1234567890",
    )
    is_valid, reason = validate_normalized_job(job)
    assert is_valid is False
    assert reason == "description_too_short_or_empty"
