from datetime import datetime, timedelta, timezone
from app.services.freshness_service import FreshnessService
from app.services.dedup_service import (
    compute_job_hash,
    compute_description_similarity,
    is_direct_company_url,
    DeduplicationService,
)


def test_freshness_clock_skew_protection():
    """Verify posting timestamp slightly in future is floored to 0.0 age."""
    now = datetime.now(timezone.utc)
    future_time = now + timedelta(minutes=15)
    age = FreshnessService.calculate_age_hours(future_time, reference_now=now)
    assert age == 0.0
    assert FreshnessService.is_fresh(future_time, confidence="HIGH", reference_now=now)


def test_recency_string_parser_and_rescue():
    """Verify relative string parser rescues high confidence timestamps within 24h."""
    now = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)

    # 1. Just now -> now
    dt1, conf1 = FreshnessService.parse_recency_string("Just now", reference_now=now)
    assert conf1 == "HIGH"
    assert dt1 == now

    # 2. 2 hours ago -> now - 2h
    dt2, conf2 = FreshnessService.parse_recency_string("2 hours ago", reference_now=now)
    assert conf2 == "HIGH"
    assert dt2 == now - timedelta(hours=2)

    # 3. Reject stale time units (e.g. 2 months ago)
    dt3, conf3 = FreshnessService.parse_recency_string("2 months ago", reference_now=now)
    assert dt3 is None
    assert conf3 == "LOW"


def test_dedup_hash_generation():
    """Verify metadata hash generation is deterministic."""
    hash1 = compute_job_hash(
        company="Acme Corp",
        title="Software Engineer",
        location="Bengaluru",
        employment_type="FULL_TIME",
        source_job_id="12345",
    )
    hash2 = compute_job_hash(
        company=" acme corp  ",
        title="software engineer",
        location="bengaluru",
        employment_type="full_time",
        source_job_id="12345",
    )
    assert hash1 == hash2


def test_is_direct_company_url():
    assert is_direct_company_url("https://razorpay.com/careers/software-engineer") is True
    assert is_direct_company_url("https://www.linkedin.com/jobs/view/123456") is False
    assert is_direct_company_url("https://www.naukri.com/job-listings-123456") is False
