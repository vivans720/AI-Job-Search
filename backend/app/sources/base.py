from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field


class JobSearchQuery(BaseModel):
    query: str | None = None
    roles: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    experience_max: int | None = 2
    freshness_hours: int = 24
    include_remote: bool = True
    include_jobs: bool = True
    include_internships: bool = True
    limit: int = 50


class RawJob(BaseModel):
    source: str
    source_job_id: str | None = None
    title: str
    company_name: str
    description: str
    location: str | None = None
    remote_type: str = "ONSITE"
    employment_type: str = "FULL_TIME"
    experience_raw: str | None = None
    salary_raw: str | None = None
    posted_time_raw: str | None = None
    source_url: str
    application_url: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NormalizedJob(BaseModel):
    source: str
    source_job_id: str | None = None
    title: str
    normalized_title: str
    role_category: str
    company_name: str
    normalized_company: str
    description: str
    location: str | None = None
    normalized_location: str
    remote_type: str
    employment_type: str
    experience_min: int | None = None
    experience_max: int | None = None
    experience_text: str | None = None
    experience_confidence: str = "LOW"  # HIGH, MEDIUM, LOW
    description_confidence: str = "HIGH"  # HIGH, LOW
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str = "INR"
    salary_period: str = "YEAR"
    salary_raw: str | None = None
    posted_at: datetime | None = None
    posted_at_raw: str | None = None
    posted_at_confidence: str = "LOW"  # HIGH, MEDIUM, LOW
    first_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_url: str
    application_url: str
    job_hash: str
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    quality_score: float = 0.0
    raw_data: dict[str, Any] = Field(default_factory=dict)


class SourceCrawlMetrics(BaseModel):
    source: str
    requests_count: int = 0
    retries_count: int = 0
    raw_discovered: int = 0
    parse_errors: int = 0
    duration_ms: float = 0.0
    status: str = "ok"  # ok, degraded, blocked, failed
    last_error_category: str | None = None
    last_error: str | None = None
    # Granular latency & crawl telemetry
    queries_count: int = 0
    pages_count: int = 0
    search_requests_count: int = 0
    hydration_requests_count: int = 0
    browser_fallbacks_count: int = 0
    rate_limit_wait_ms: float = 0.0
    discovery_duration_ms: float = 0.0
    hydration_duration_ms: float = 0.0


class JobSource(ABC):
    source_name: str
    enabled: bool = True
    status: str = "ok"
    last_error: str | None = None
    last_error_category: str | None = None

    def __init__(self):
        self._metrics = SourceCrawlMetrics(source=getattr(self, "source_name", "unknown"))

    def get_metrics(self) -> SourceCrawlMetrics:
        return self._metrics.model_copy()

    def reset_metrics(self) -> None:
        self._metrics = SourceCrawlMetrics(source=getattr(self, "source_name", "unknown"))

    @abstractmethod
    async def search(self, query: JobSearchQuery) -> list[RawJob]:
        """Fetch raw listings from the source platform."""
        pass

    @abstractmethod
    async def get_job(self, url: str) -> RawJob | None:
        """Fetch a single raw listing by URL."""
        pass

    @abstractmethod
    async def normalize(self, raw: RawJob) -> NormalizedJob | None:
        """Transform platform-specific raw payload into canonical NormalizedJob. Returns None if stale or invalid."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Verifies connectivity/availability of the source."""
        pass

