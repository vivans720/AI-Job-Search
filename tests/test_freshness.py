from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import pytest

from app.services.freshness_service import FreshnessService, IST


def test_relative_time_parsing():
    svc = FreshnessService()
    now_ist = datetime.now(IST)

    # 2 hours ago
    dt, conf = svc.parse_relative_time("2 hours ago", reference_now=now_ist)
    assert dt is not None
    assert conf == "HIGH"
    age = svc.calculate_age_hours(dt, reference_now=now_ist)
    assert 1.9 <= age <= 2.1

    # 30 mins ago
    dt, conf = svc.parse_relative_time("30 minutes ago", reference_now=now_ist)
    assert dt is not None
    assert conf == "HIGH"
    age = svc.calculate_age_hours(dt, reference_now=now_ist)
    assert 0.4 <= age <= 0.6

    # Recency terms are rescued into HIGH confidence operational timestamps
    dt, conf = svc.parse_relative_time("Recently", reference_now=now_ist)
    assert dt is not None
    assert conf == "HIGH"
    age = svc.calculate_age_hours(dt, reference_now=now_ist)
    assert 0.4 <= age <= 0.6

    dt, conf = svc.parse_relative_time("Just now", reference_now=now_ist)
    assert dt is not None
    assert conf == "HIGH"
    age = svc.calculate_age_hours(dt, reference_now=now_ist)
    assert age == 0.0

    # Stale multi-day string returns LOW confidence
    dt, conf = svc.parse_relative_time("5 days ago", reference_now=now_ist)
    assert dt is not None
    assert conf == "LOW"

    # Relative expressions
    dt, conf = svc.parse_relative_time("few hours ago", reference_now=now_ist)
    assert dt is not None
    assert conf == "HIGH"
    age = svc.calculate_age_hours(dt, reference_now=now_ist)
    assert 2.9 <= age <= 3.1

    dt, conf = svc.parse_relative_time("1d ago", reference_now=now_ist)
    assert dt is not None
    assert conf == "HIGH"
    age = svc.calculate_age_hours(dt, reference_now=now_ist)
    assert 11.9 <= age <= 12.1

    # Duration strings must NOT be parsed as relative timestamps
    dt, conf = svc.parse_relative_time("1 month", reference_now=now_ist)
    assert dt is None
    assert conf == "LOW"

    dt, conf = svc.parse_relative_time("6 months", reference_now=now_ist)
    assert dt is None
    assert conf == "LOW"


def test_boundary_freshness():
    """Verify exact 23h59m vs 24h00m vs 24h01m freshness cutoff."""
    svc = FreshnessService(freshness_hours=24)
    now_ist = datetime.now(IST)

    # 23 hours 59 minutes ago -> FRESH
    t_fresh = now_ist - timedelta(hours=23, minutes=59)
    assert svc.is_fresh(t_fresh, "HIGH", reference_now=now_ist) is True
    assert svc.classify_freshness(t_fresh, "HIGH", reference_now=now_ist) == "FRESH"

    # Exactly 24 hours ago -> FRESH
    t_boundary = now_ist - timedelta(hours=24, seconds=0)
    assert svc.is_fresh(t_boundary, "HIGH", reference_now=now_ist) is True

    # 24 hours 1 minute ago -> STALE
    t_stale = now_ist - timedelta(hours=24, minutes=1)
    assert svc.is_fresh(t_stale, "HIGH", reference_now=now_ist) is False
    assert svc.classify_freshness(t_stale, "HIGH", reference_now=now_ist) == "STALE"


def test_low_confidence_exclusion():
    svc = FreshnessService(freshness_hours=24)
    now_ist = datetime.now(IST)

    # Even if timestamp is fresh, confidence LOW must be excluded from primary feed
    t_recent = now_ist - timedelta(hours=2)
    assert svc.is_fresh(t_recent, confidence="LOW", reference_now=now_ist) is False
    assert svc.classify_freshness(t_recent, confidence="LOW", reference_now=now_ist) == "UNCERTAIN"


def test_timezone_conversion():
    svc = FreshnessService()
    now_utc = datetime.now(timezone.utc)
    ist_dt = svc.to_ist(now_utc)
    assert ist_dt.tzinfo == IST

    back_utc = svc.to_utc(ist_dt)
    assert back_utc.tzinfo == timezone.utc
    assert abs((now_utc - back_utc).total_seconds()) < 1.0
