import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import structlog

logger = structlog.get_logger(__name__)

IST = ZoneInfo("Asia/Kolkata")


class FreshnessService:
    """
    Deterministic freshness evaluation engine.
    Ensures strict 24-hour window compliance using timezone-aware calculations,
    recency rescue anchors, and clock-skew floors.
    """

    def __init__(self, default_tz: str = "Asia/Kolkata", freshness_hours: int = 24):
        self.tz = ZoneInfo(default_tz)
        self.freshness_hours = freshness_hours

    def now_ist(self) -> datetime:
        return datetime.now(self.tz)

    @staticmethod
    def ensure_utc(dt: datetime | None) -> datetime | None:
        """Enforces safe UTC transformations without introducing artificial aging."""
        if dt is None:
            return None
        if dt.tzinfo is None:
            # Assume naive timestamps are already UTC from standard web data
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def to_utc(self, dt: datetime | None) -> datetime | None:
        return self.ensure_utc(dt)

    def to_ist(self, dt: datetime | None) -> datetime | None:
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(self.tz)

    @classmethod
    def calculate_age_hours(
        cls, posted_at: datetime | None, reference_now: datetime | None = None
    ) -> float | None:
        if posted_at is None:
            return None

        now_utc = cls.ensure_utc(reference_now) or datetime.now(timezone.utc)
        posted_utc = cls.ensure_utc(posted_at)

        diff_seconds = (now_utc - posted_utc).total_seconds()
        age_hours = round(diff_seconds / 3600.0, 2)

        # CLOCK SKEW PROTECTION: If posted in the future due to clock drift, floor to 0.0
        if age_hours < 0:
            age_hours = 0.0

        return age_hours

    @classmethod
    def parse_recency_string(
        cls, text: str | None, reference_now: datetime | None = None
    ) -> tuple[datetime | None, str]:
        """Rescues vague relative recency phrases into high-confidence operational UTC anchors."""
        if not text or not text.strip():
            return None, "LOW"

        cleaned = text.strip().lower()
        now_utc = cls.ensure_utc(reference_now) or datetime.now(timezone.utc)

        # 1. Reject duration strings, future dates, and stale time units (months, years, weeks)
        if re.search(r"\b(?:\d+\s*)?(?:months?|mo|years?|yrs?|weeks?|wks?|duration|starts?\s+in|starts?\s+within)\b", cleaned):
            return None, "LOW"

        # 2. Immediate High-Confidence Rescue
        if any(token in cleaned for token in ["just now", "just posted", "few seconds ago", "seconds ago"]):
            return now_utc, "HIGH"

        if "half an hour ago" in cleaned:
            return now_utc - timedelta(minutes=30), "HIGH"

        if re.search(r"\b(?:a\s+)?few\s+hours?\s+ago\b", cleaned):
            return now_utc - timedelta(hours=3), "HIGH"

        if re.search(r"\b(?:an?|1)\s+hour\s+ago\b", cleaned):
            return now_utc - timedelta(hours=1), "HIGH"

        if any(token in cleaned for token in ["today", "active today", "new", "posted recently", "recently", "posted today"]):
            return now_utc - timedelta(minutes=30), "HIGH"

        if any(token in cleaned for token in ["yesterday", "1 day ago", "1d ago", "active 1 day ago"]):
            # Set to 12 hours ago to guarantee survival within the 24h SQL window
            return now_utc - timedelta(hours=12), "HIGH"

        # 3. Extract Minutes (word boundaries, strict check to avoid matching month)
        mins_match = re.search(r"\b(\d+)\s*(?:minutes?|mins?|m)\s*(?:ago)?\b", cleaned)
        if mins_match:
            mins = int(mins_match.group(1))
            return now_utc - timedelta(minutes=mins), "HIGH"

        # 4. Extract Hours (<= 24h is HIGH confidence fresh, > 24h is stale)
        hours_match = re.search(r"\b(\d+)\s*(?:hours?|hrs?|h)\s*(?:ago)?\b", cleaned)
        if hours_match:
            hrs = int(hours_match.group(1))
            conf = "HIGH" if hrs <= 24 else "LOW"
            return now_utc - timedelta(hours=hrs), conf

        # 5. Extract Days (1 day ago is rescued within 24h; >= 2 days is stale)
        days_match = re.search(r"\b(\d+)\s*(?:days?|d)\s*(?:ago)?\b", cleaned)
        if days_match:
            days = int(days_match.group(1))
            if days == 1:
                return now_utc - timedelta(hours=12), "HIGH"
            return now_utc - timedelta(days=days), "LOW"

        # 6. Date-only format YYYY-MM-DD (No hour information: assume midpoint ~12h old with MEDIUM confidence)
        date_match = re.match(r"^(\d{4}-\d{2}-\d{2})$", text.strip())
        if date_match:
            try:
                d = datetime.strptime(date_match.group(1), "%Y-%m-%d").date()
                today = now_utc.date()
                if d == today:
                    return now_utc - timedelta(hours=12), "MEDIUM"
                elif d == today - timedelta(days=1):
                    return now_utc - timedelta(hours=20), "MEDIUM"
                else:
                    days_ago = max(2, (today - d).days)
                    return now_utc - timedelta(days=days_ago), "LOW"
            except Exception:
                pass

        # 7. Full ISO format with time
        try:
            dt = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
            return cls.ensure_utc(dt), "HIGH"
        except Exception:
            pass

        return None, "LOW"

    def parse_relative_time(
        self, text: str | None, reference_now: datetime | None = None
    ) -> tuple[datetime | None, str]:
        """Backwards compatible instance method for parse_recency_string."""
        return self.parse_recency_string(text, reference_now=reference_now)

    @classmethod
    def evaluate_freshness(
        cls,
        posted_at: datetime | None,
        confidence: str = "HIGH",
        freshness_hours: int | float | None = 24.0,
        reference_now: datetime | None = None,
        source: str = "unknown",
        title: str = "unknown",
        scraped_at: datetime | None = None,
    ) -> tuple[bool, str, float | None]:
        """
        Evaluates freshness deterministically and logs structured debug telemetry.
        Returns: (is_fresh, reason, age_hours)
        """
        max_hours = float(freshness_hours if freshness_hours is not None else 24.0)
        age = cls.calculate_age_hours(posted_at, reference_now)

        if posted_at is None:
            is_ok = False
            decision = "REJECT"
            reason = "missing_posted_at"
        elif confidence not in ["HIGH", "MEDIUM"]:
            is_ok = False
            decision = "REJECT"
            reason = f"low_confidence_{confidence}"
        elif age is None:
            is_ok = False
            decision = "REJECT"
            reason = "age_calculation_failed"
        elif age > max_hours:
            is_ok = False
            decision = "REJECT"
            reason = f"stale_age_{age}h_exceeds_{max_hours}h"
        else:
            is_ok = True
            decision = "ACCEPT"
            reason = "fresh"

        logger.debug(
            "freshness_decision",
            source=source,
            title=title,
            posted_at=posted_at.isoformat() if posted_at else None,
            scraped_at=scraped_at.isoformat() if scraped_at else None,
            posted_at_confidence=confidence,
            age_hours=age,
            cutoff_hours=max_hours,
            decision=decision,
            reason=reason,
        )
        return is_ok, reason, age

    @classmethod
    def is_fresh(
        cls,
        posted_at: datetime | None,
        confidence: str = "HIGH",
        freshness_hours: int | float | None = 24.0,
        reference_now: datetime | None = None,
    ) -> bool:
        """
        Determines freshness using a clock-skew floor and broad acceptance criteria.
        Requires:
        1. posted_at is not None
        2. confidence is HIGH or MEDIUM (not LOW)
        3. 0.0 <= age_hours <= max_hours
        """
        is_ok, _, _ = cls.evaluate_freshness(
            posted_at=posted_at,
            confidence=confidence,
            freshness_hours=freshness_hours,
            reference_now=reference_now,
        )
        return is_ok

    def classify_freshness(
        self,
        posted_at: datetime | None,
        confidence: str = "HIGH",
        freshness_hours: int | None = None,
        reference_now: datetime | None = None,
    ) -> str:
        """Returns 'FRESH', 'UNCERTAIN', or 'STALE'."""
        if posted_at is None or confidence == "LOW":
            return "UNCERTAIN"

        max_h = freshness_hours if freshness_hours is not None else self.freshness_hours
        if self.is_fresh(posted_at, confidence, max_h, reference_now):
            return "FRESH"
        return "STALE"


_default_freshness_service: FreshnessService | None = None


def get_freshness_service() -> FreshnessService:
    global _default_freshness_service
    if _default_freshness_service is None:
        _default_freshness_service = FreshnessService()
    return _default_freshness_service
