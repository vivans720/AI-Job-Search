import asyncio
from datetime import datetime, timezone, timedelta
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

try:
    import bs4  # noqa: F401
except ImportError:
    pytest.skip("Optional dependency 'bs4' is not installed", allow_module_level=True)

from app.config import settings
from app.sources.adapters.linkedin import (
    LinkedInAdapter,
    clean_linkedin_url,
    extract_linkedin_job_id,
)
from app.sources.adapters.internshala import is_senior_title
from app.sources.base import JobSearchQuery, RawJob, NormalizedJob
from app.sources.registry import SourceRegistry, get_source_registry, reset_registry
from app.utils.http_client import HTTPResult


# ==============================================================================
# Sample Fixtures & Payloads
# ==============================================================================

MOCK_GUEST_HTML = """
<!DOCTYPE html>
<html>
<body>
  <ul class="jobs-search__results-list">
    <li>
      <div class="base-card base-search-card job-search-card" data-entity-urn="urn:li:jobPosting:4012345678">
        <a class="base-card__full-link" href="https://in.linkedin.com/jobs/view/software-engineer-at-acme-4012345678?refId=xyz&trackingId=abc">
          <span class="sr-only">Software Engineer</span>
        </a>
        <div class="base-search-card__info">
          <h3 class="base-search-card__title">Software Engineer</h3>
          <h4 class="base-search-card__subtitle">
            <a class="hidden-nested-link" href="https://in.linkedin.com/company/acme-corp">Acme Technologies</a>
          </h4>
          <div class="base-search-card__metadata">
            <span class="job-search-card__location">Bengaluru, Karnataka, India</span>
            <time class="job-search-card__listdate" datetime="2026-09-05T12:00:00Z">2 hours ago</time>
          </div>
        </div>
      </div>
    </li>
    <li>
      <div class="base-card base-search-card job-search-card" data-entity-urn="urn:li:jobPosting:4098765432">
        <a class="base-card__full-link" href="https://in.linkedin.com/jobs/view/4098765432">
          <span class="sr-only">Senior Lead Architect</span>
        </a>
        <div class="base-search-card__info">
          <h3 class="base-search-card__title">Senior Lead Architect</h3>
          <h4 class="base-search-card__subtitle">Global Enterprise</h4>
          <div class="base-search-card__metadata">
            <span class="job-search-card__location">Remote, India</span>
            <time class="job-search-card__listdate">1 hour ago</time>
          </div>
        </div>
      </div>
    </li>
  </ul>
</body>
</html>
"""

MOCK_JSON_LD_HTML = """
<!DOCTYPE html>
<html>
<head>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "JobPosting",
  "title": "Backend Python Developer",
  "hiringOrganization": {
    "@type": "Organization",
    "name": "Fintech Solutions India"
  },
  "description": "We are seeking a Backend Developer proficient in Python, FastAPI, Docker, and PostgreSQL.",
  "datePosted": "2026-09-05T14:30:00Z",
  "jobLocationType": "TELECOMMUTE",
  "jobLocation": {
    "@type": "Place",
    "address": {
      "addressLocality": "Bengaluru",
      "addressCountry": "India"
    }
  }
}
</script>
</head>
<body></body>
</html>
"""


# ==============================================================================
# 1. Selector Boundaries & String Parsers
# ==============================================================================

def test_extract_linkedin_job_id():
    """Verifies regex extraction of numeric LinkedIn IDs across URL formats and URNs."""
    # Standard view URL with title slug
    url1 = "https://in.linkedin.com/jobs/view/software-engineer-at-acme-4012345678?refId=123"
    assert extract_linkedin_job_id(url1) == "4012345678"

    # Numeric only view URL
    url2 = "https://www.linkedin.com/jobs/view/4098765432"
    assert extract_linkedin_job_id(url2) == "4098765432"

    # URN format
    urn = "urn:li:jobPosting:4055566677"
    assert extract_linkedin_job_id(urn) == "4055566677"


def test_clean_linkedin_url():
    """Ensures tracking parameters are stripped to canonical job URLs."""
    dirty_url = "https://in.linkedin.com/jobs/view/4012345678?refId=abc&trackingId=def#content"
    assert clean_linkedin_url(dirty_url) == "https://in.linkedin.com/jobs/view/4012345678"


from app.utils.normalization import parse_experience_requirement


def test_parse_linkedin_experience():
    """Verifies experience string conversion into (min, max) boundaries using unified parser."""
    assert parse_experience_requirement("Fresher")[:2] == (0, 0)
    assert parse_experience_requirement("Entry level position")[:2] == (0, 0)
    assert parse_experience_requirement("0-2 years")[:2] == (0, 2)
    assert parse_experience_requirement("1 - 3 yrs")[:2] == (1, 3)
    assert parse_experience_requirement("2+ years")[:2] == (2, None)
    assert parse_experience_requirement("")[:2] == (None, None)


# ==============================================================================
# 2. Senior Title Exclusion Filter Tests
# ==============================================================================

def test_senior_title_exclusion_gate():
    """Verifies that senior and managerial titles are rejected while juniors are admitted."""
    # Must reject senior roles
    assert is_senior_title("Senior Software Engineer") is True
    assert is_senior_title("Lead Backend Developer") is True
    assert is_senior_title("Engineering Manager") is True
    assert is_senior_title("Staff AI Engineer") is True
    assert is_senior_title("Principal Cloud Architect") is True
    assert is_senior_title("Director of Technology") is True
    assert is_senior_title("VP of Engineering") is True

    # Must preserve junior and entry-level roles
    assert is_senior_title("Junior Python Developer") is False
    assert is_senior_title("Software Engineer") is False
    assert is_senior_title("Associate Backend Engineer") is False
    assert is_senior_title("Graduate Engineer Trainee") is False
    assert is_senior_title("AI Engineer Intern") is False


# ==============================================================================
# 3. HTML & Guest Card Parsing Tests
# ==============================================================================

def test_parse_html_guest_cards():
    """Verifies selector boundary extraction of title, company, location, and URLs."""
    adapter = LinkedInAdapter()
    jobs = adapter.parse_html(MOCK_GUEST_HTML)
    assert len(jobs) == 2

    job1 = jobs[0]
    assert job1.title == "Software Engineer"
    assert job1.company_name == "Acme Technologies"
    assert "Bengaluru" in (job1.location or "")
    assert job1.source_job_id == "4012345678"
    assert job1.source_url == "https://in.linkedin.com/jobs/view/software-engineer-at-acme-4012345678"
    assert job1.posted_time_raw == "2 hours ago"
    assert job1.raw_payload.get("datetime") == "2026-09-05T12:00:00Z"


# ==============================================================================
# 4. Resilient Fetching & Tor SOCKS5 Proxy Fallback Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_resilient_fetch_tor_fallback_on_429():
    """Verifies that hitting 429 Too Many Requests triggers Tor SOCKS5 proxy fallback."""
    adapter = LinkedInAdapter(tor_proxy_url="socks5://127.0.0.1:9050")

    mock_direct_429 = HTTPResult(
        status_code=429,
        text="Rate limited",
        error="RATE_LIMITED",
    )
    mock_tor_success = HTTPResult(
        status_code=200,
        text="<html><body><li class='base-card'>Tor Success</li></body></html>",
        routed_via="tor",
    )

    with patch("app.utils.http_client.resilient_fetch", new_callable=AsyncMock) as mock_rf, \
         patch("app.utils.http_client.is_tor_proxy_available", return_value=True), \
         patch("app.utils.http_client.fetch_via_tor_proxy", new_callable=AsyncMock) as mock_tor:

        mock_rf.return_value = mock_direct_429
        mock_tor.return_value = mock_tor_success

        result = await adapter._fetch_url("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search")
        assert result is not None
        assert "Tor Success" in result
        mock_tor.assert_awaited_once()


@pytest.mark.asyncio
async def test_resilient_fetch_tor_fallback_on_403():
    """Verifies that 403 Forbidden triggers Tor SOCKS5 proxy fallback."""
    adapter = LinkedInAdapter()

    mock_direct_403 = HTTPResult(
        status_code=403,
        text="Access Denied",
        error="ANTI_BOT_BLOCKED",
    )
    mock_tor_success = HTTPResult(
        status_code=200,
        text="<html><body><li>Unblocked via Tor</li></body></html>",
        routed_via="tor",
    )

    with patch("app.utils.http_client.resilient_fetch", new_callable=AsyncMock) as mock_rf, \
         patch("app.utils.http_client.is_tor_proxy_available", return_value=True), \
         patch("app.utils.http_client.fetch_via_tor_proxy", new_callable=AsyncMock) as mock_tor:

        mock_rf.return_value = mock_direct_403
        mock_tor.return_value = mock_tor_success

        result = await adapter._fetch_url("https://www.linkedin.com/jobs/search")
        assert result is not None
        assert "Unblocked via Tor" in result
        mock_tor.assert_awaited_once()


# ==============================================================================
# 5. Playwright Fallback Discovery Engine Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_search_triggers_playwright_fallback_when_guest_api_empty():
    """Verifies that if guest API returns empty or blocked DOM, Playwright fallback engages."""
    adapter = LinkedInAdapter()

    with patch.object(adapter, "_fetch_url", new_callable=AsyncMock) as mock_fetch, \
         patch.object(adapter, "_fetch_via_crawl4ai", new_callable=AsyncMock) as mock_crawl, \
         patch.object(adapter, "_fetch_via_browser", new_callable=AsyncMock) as mock_browser:

        # Fast path returns empty string
        mock_fetch.return_value = ""
        # Rendered Crawl4AI path misses, legacy browser fallback returns valid HTML
        mock_crawl.return_value = None
        mock_browser.return_value = MOCK_GUEST_HTML

        query = JobSearchQuery(query="Software Engineer", limit=5)
        jobs = await adapter.search(query)

        assert len(jobs) > 0
        assert jobs[0].title == "Software Engineer"
        mock_browser.assert_awaited_once()


# ==============================================================================
# 6. Strict 24h Freshness & IST Window Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_normalize_accepts_fresh_relative_hours():
    """Verifies relative strings like '2 hours ago' map to HIGH confidence within 24h window."""
    adapter = LinkedInAdapter()
    raw = RawJob(
        source="linkedin",
        source_job_id="101010",
        title="Python Backend Developer",
        company_name="Tech Solutions",
        description="Developing scalable backend microservices using Python and FastAPI. This role involves designing robust REST APIs, integrating PostgreSQL databases, writing comprehensive unit tests, and collaborating with cross-functional teams in an agile environment.",
        location="Bengaluru, Karnataka",
        posted_time_raw="2 hours ago",
        source_url="https://www.linkedin.com/jobs/view/101010",
        application_url="https://www.linkedin.com/jobs/view/101010",
    )

    norm = await adapter.normalize(raw)
    assert norm is not None
    assert norm.title == "Python Backend Developer"
    assert norm.posted_at_confidence == "HIGH"
    assert norm.posted_at is not None


@pytest.mark.asyncio
async def test_normalize_rejects_stale_jobs():
    """Verifies postings older than 24 hours (e.g. '3 days ago') are rejected."""
    adapter = LinkedInAdapter()
    raw = RawJob(
        source="linkedin",
        source_job_id="202020",
        title="Associate Software Engineer",
        company_name="Tech Solutions",
        description="Entry level software engineer opportunity involving Python microservices, database design, API integrations, and cloud infrastructure management across modern distributed systems.",
        location="Pune, India",
        posted_time_raw="3 days ago",
        source_url="https://www.linkedin.com/jobs/view/202020",
        application_url="https://www.linkedin.com/jobs/view/202020",
    )

    norm = await adapter.normalize(raw)
    assert norm is None


@pytest.mark.asyncio
async def test_normalize_rescues_recency_counters_and_rejects_stale():
    """Verifies recency phrases like 'Just now' are rescued with HIGH confidence, and stale postings rejected."""
    adapter = LinkedInAdapter()
    full_desc = (
        "Building modern responsive React interfaces for high-scale enterprise applications. "
        "Candidate will collaborate with backend engineers, build performant component libraries, "
        "and maintain state management using Redux and TypeScript across web platforms."
    )
    raw = RawJob(
        source="linkedin",
        source_job_id="303030",
        title="Frontend React Developer",
        company_name="Tech Solutions",
        description=full_desc,
        location="Remote, India",
        posted_time_raw="Just now",
        source_url="https://www.linkedin.com/jobs/view/303030",
        application_url="https://www.linkedin.com/jobs/view/303030",
        raw_payload={},
    )

    norm = await adapter.normalize(raw)
    assert norm is not None
    assert norm.posted_at_confidence == "HIGH"

    raw_stale = RawJob(
        source="linkedin",
        source_job_id="303031",
        title="Frontend React Developer",
        company_name="Tech Solutions",
        description=full_desc,
        location="Remote, India",
        posted_time_raw="10 days ago",
        source_url="https://www.linkedin.com/jobs/view/303031",
        application_url="https://www.linkedin.com/jobs/view/303031",
        raw_payload={},
    )
    norm_stale = await adapter.normalize(raw_stale)
    assert norm_stale is None



@pytest.mark.asyncio
async def test_normalize_retains_short_snippets_with_low_confidence():
    """Verifies unhydrated preview snippet cards (<200 chars) are retained with LOW confidence under recall-first."""
    adapter = LinkedInAdapter()
    raw = RawJob(
        source="linkedin",
        source_job_id="303032",
        title="Python Backend Developer",
        company_name="Tech Solutions",
        description="Short preview snippet lacking full job details.",  # 50 chars
        location="Bengaluru, India",
        posted_time_raw="1 hour ago",
        source_url="https://www.linkedin.com/jobs/view/303032",
        application_url="https://www.linkedin.com/jobs/view/303032",
    )
    norm = await adapter.normalize(raw)
    assert norm is not None
    assert norm.description_confidence == "LOW"


@pytest.mark.asyncio
async def test_normalize_retains_senior_roles_for_recall_first():
    """Verifies that senior titles are retained during normalization for downstream user filtering."""
    adapter = LinkedInAdapter()
    raw = RawJob(
        source="linkedin",
        source_job_id="404040",
        title="Senior Director of Engineering",
        company_name="Enterprise Global",
        description="Leading global engineering teams across cloud services, distributed infrastructure, and microservices architecture at planetary scale.",
        location="Bengaluru, India",
        posted_time_raw="1 hour ago",
        source_url="https://www.linkedin.com/jobs/view/404040",
        application_url="https://www.linkedin.com/jobs/view/404040",
    )

    norm = await adapter.normalize(raw)
    assert norm is not None
    assert norm.title == "Senior Director of Engineering"


# ==============================================================================
# 7. Zero-Hallucination Skill Extraction & Data Integrity Validation Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_normalize_skill_extraction_and_provenance():
    """Verifies extraction of skills with provenance tracking metadata."""
    adapter = LinkedInAdapter()
    raw = RawJob(
        source="linkedin",
        source_job_id="505050",
        title="Full Stack Developer",
        company_name="Startup Inc",
        description="Requires strong hands-on proficiency with Python, FastAPI, Docker, and React. The engineer will design REST APIs, build interactive frontend interfaces, manage container deployments, and optimize SQL database transactions.",
        location="Hyderabad, India",
        posted_time_raw="4 hours ago",
        source_url="https://www.linkedin.com/jobs/view/505050",
        application_url="https://www.linkedin.com/jobs/view/505050",
    )

    norm = await adapter.normalize(raw)
    assert norm is not None
    assert "Python" in norm.required_skills or "FastAPI" in norm.required_skills
    assert "skill_extraction_provenance" in norm.raw_data
    assert norm.raw_data["skill_extraction_provenance"]["method"] in ("hybrid", "deterministic", "llm_fallback")


@pytest.mark.asyncio
async def test_normalize_data_integrity_validation_failure():
    """Verifies that jobs failing validation boundaries (e.g. invalid URL) are rejected."""
    adapter = LinkedInAdapter()
    raw = RawJob(
        source="linkedin",
        source_job_id="606060",
        title="QA",  # Too short title (< 3 chars)
        company_name="X",
        description="Too short",
        location="India",
        posted_time_raw="1 hour ago",
        source_url="ftp://invalid-scheme.com",
        application_url="ftp://invalid-scheme.com",
    )

    norm = await adapter.normalize(raw)
    assert norm is None


# ==============================================================================
# 8. Single Job JSON-LD Extraction Test
# ==============================================================================

@pytest.mark.asyncio
async def test_get_job_json_ld_parsing():
    """Verifies get_job parses Schema.org JobPosting microdata."""
    adapter = LinkedInAdapter()
    with patch.object(adapter, "_fetch_url", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = MOCK_JSON_LD_HTML
        job = await adapter.get_job("https://www.linkedin.com/jobs/view/707070")

        assert job is not None
        assert job.title == "Backend Python Developer"
        assert job.company_name == "Fintech Solutions India"
        assert "FastAPI" in job.description
        assert job.remote_type == "REMOTE"


# ==============================================================================
# 9. Source Registry & Session Isolation Rollback Tests
# ==============================================================================

def test_registry_registers_linkedin_adapter():
    """Verifies LinkedInAdapter is registered in SourceRegistry when enabled."""
    reset_registry()
    with patch.object(settings, "SOURCE_LINKEDIN_ENABLED", True):
        registry = get_source_registry()
        src = registry.get_source("linkedin")
        assert src is not None
        assert src.source_name == "linkedin"
        assert src in registry.get_enabled_sources()


@pytest.mark.asyncio
async def test_registry_sync_source_isolated_rollback():
    """Verifies session rollback is invoked upon ingestion error."""
    registry = SourceRegistry()
    mock_source = MagicMock()
    mock_source.source_name = "linkedin"

    mock_db = MagicMock()
    mock_db.rollback = AsyncMock()

    mock_ingestion = MagicMock()
    mock_ingestion.ingest_source = AsyncMock(side_effect=RuntimeError("Simulated 429 connection drop"))

    with pytest.raises(RuntimeError, match="Simulated 429"):
        await registry.sync_source_isolated(mock_source, mock_db, mock_ingestion)

    mock_db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_registry_sync_all_isolated_fault_tolerance():
    """Verifies that a failure in one source does not prevent other sources from syncing."""
    registry = SourceRegistry()

    src1 = MagicMock()
    src1.source_name = "linkedin"
    src1.enabled = True

    src2 = MagicMock()
    src2.source_name = "naukri"
    src2.enabled = True

    registry.register(src1)
    registry.register(src2)

    mock_db = MagicMock()
    mock_db.rollback = AsyncMock()

    mock_ingestion = MagicMock()
    # src1 fails, src2 succeeds
    mock_ingestion.ingest_source = AsyncMock(side_effect=[
        RuntimeError("LinkedIn rate limit block"),
        {"total_discovered": 10, "saved_jobs": 5},
    ])

    stats = await registry.sync_all_isolated(mock_db, mock_ingestion)
    assert "naukri" in stats["sources_synced"]
    assert len(stats["failed_sources"]) == 1
    assert stats["failed_sources"][0]["source"] == "linkedin"
    assert stats["saved_jobs"] == 5


@pytest.mark.asyncio
async def test_linkedin_offset_pagination():
    from unittest.mock import patch
    adapter = LinkedInAdapter()
    urls_called = []

    async def mock_fetch(url):
        urls_called.append(url)
        if "start=0" in url:
            return """
            <ul>
              <li>
                <div class="base-card" data-entity-urn="urn:li:jobPosting:1001">
                  <a class="base-card__full-link" href="https://linkedin.com/jobs/view/1001"></a>
                  <h3 class="base-search-card__title">Software Engineer</h3>
                  <h4 class="base-search-card__subtitle"><a>Company A</a></h4>
                  <span class="job-search-card__location">Bengaluru, India</span>
                  <time datetime="2026-09-06">1 hour ago</time>
                </div>
              </li>
            </ul>
            """
        elif "start=25" in url:
            return """
            <ul>
              <li>
                <div class="base-card" data-entity-urn="urn:li:jobPosting:1002">
                  <a class="base-card__full-link" href="https://linkedin.com/jobs/view/1002"></a>
                  <h3 class="base-search-card__title">Software Engineer</h3>
                  <h4 class="base-search-card__subtitle"><a>Company B</a></h4>
                  <span class="job-search-card__location">Bengaluru, India</span>
                  <time datetime="2026-09-06">2 hours ago</time>
                </div>
              </li>
            </ul>
            """
        return ""

    with patch.object(adapter, "_fetch_url", side_effect=mock_fetch):
        jobs = await adapter.search(JobSearchQuery(roles=["Software Engineer"], limit=100, freshness_hours=24))
        assert any("start=0" in u for u in urls_called)
        assert any("start=25" in u for u in urls_called)
        assert len(jobs) == 2


@pytest.mark.asyncio
async def test_freshness_aware_query_budgeting_and_deduplication():
    """Verifies that 1h freshness window constrains queries and eliminates duplicate synonyms."""
    adapter = LinkedInAdapter()
    
    # 1h query with multiple overlapping skills and roles
    q_1h = JobSearchQuery(
        roles=["Software Engineer", "Backend Developer", "Frontend Developer", "Full Stack Developer"],
        skills=["javascript", "js", "typescript", "react", "reactjs", "python"],
        freshness_hours=1,
    )
    queries_1h = adapter._determine_search_queries(q_1h)
    # Must be capped to at most 2 queries for 1h sync
    assert len(queries_1h) <= 2
    assert len(queries_1h) == len(set(queries_1h))

    # 24h query gets broader coverage but canonical deduplication
    q_24h = JobSearchQuery(
        roles=["Software Engineer"],
        skills=["javascript", "js", "typescript", "ts"],
        freshness_hours=24,
    )
    queries_24h = adapter._determine_search_queries(q_24h)
    assert len(queries_24h) > len(queries_1h)
    # Check no literal duplicates
    assert len(queries_24h) == len(set(queries_24h))


@pytest.mark.asyncio
async def test_freshness_aware_offsets_and_early_stopping():
    """Verifies that 1h freshness uses single page offset [0] and does not request offset 25/50."""
    adapter = LinkedInAdapter()
    urls_called = []

    async def mock_fetch(url):
        urls_called.append(url)
        return """
        <ul>
          <li>
            <div class="base-card" data-entity-urn="urn:li:jobPosting:9001">
              <a class="base-card__full-link" href="https://linkedin.com/jobs/view/9001"></a>
              <h3 class="base-search-card__title">Software Engineer</h3>
              <h4 class="base-search-card__subtitle"><a>Fast Corp</a></h4>
              <span class="job-search-card__location">Bengaluru, India</span>
              <time datetime="2026-09-06">30 minutes ago</time>
            </div>
          </li>
        </ul>
        """

    with patch.object(adapter, "_fetch_url", side_effect=mock_fetch):
        jobs = await adapter.search(JobSearchQuery(roles=["Software Engineer"], freshness_hours=1, limit=10))
        assert len(jobs) == 1
        # 1h freshness should only call offset 0
        assert any("start=0" in u for u in urls_called)
        assert not any("start=25" in u for u in urls_called)
        assert not any("start=50" in u for u in urls_called)


@pytest.mark.asyncio
async def test_global_hydration_budget():
    """Verifies that detail hydration respects global cap and does not hydrate every card synchronously."""
    adapter = LinkedInAdapter()
    hydration_urls = []

    mock_search_html = """
    <ul>
      <li>
        <div class="base-card" data-entity-urn="urn:li:jobPosting:8001">
          <a class="base-card__full-link" href="https://linkedin.com/jobs/view/8001"></a>
          <h3 class="base-search-card__title">Short Desc Job 1</h3>
          <h4 class="base-search-card__subtitle"><a>Company 1</a></h4>
          <span class="job-search-card__location">Bengaluru, India</span>
          <time datetime="2026-09-06">2 hours ago</time>
        </div>
      </li>
      <li>
        <div class="base-card" data-entity-urn="urn:li:jobPosting:8002">
          <a class="base-card__full-link" href="https://linkedin.com/jobs/view/8002"></a>
          <h3 class="base-search-card__title">Short Desc Job 2</h3>
          <h4 class="base-search-card__subtitle"><a>Company 2</a></h4>
          <span class="job-search-card__location">Bengaluru, India</span>
          <time datetime="2026-09-06">2 hours ago</time>
        </div>
      </li>
      <li>
        <div class="base-card" data-entity-urn="urn:li:jobPosting:8003">
          <a class="base-card__full-link" href="https://linkedin.com/jobs/view/8003"></a>
          <h3 class="base-search-card__title">Short Desc Job 3</h3>
          <h4 class="base-search-card__subtitle"><a>Company 3</a></h4>
          <span class="job-search-card__location">Bengaluru, India</span>
          <time datetime="2026-09-06">2 hours ago</time>
        </div>
      </li>
      <li>
        <div class="base-card" data-entity-urn="urn:li:jobPosting:8004">
          <a class="base-card__full-link" href="https://linkedin.com/jobs/view/8004"></a>
          <h3 class="base-search-card__title">Short Desc Job 4</h3>
          <h4 class="base-search-card__subtitle"><a>Company 4</a></h4>
          <span class="job-search-card__location">Bengaluru, India</span>
          <time datetime="2026-09-06">2 hours ago</time>
        </div>
      </li>
    </ul>
    """

    async def mock_fetch(url):
        return mock_search_html

    async def mock_get_job(url, use_browser=False):
        hydration_urls.append(url)
        return RawJob(
            source="linkedin",
            source_job_id="hydrated_id",
            title="Hydrated Title",
            company_name="Company",
            description="A" * 300,
            location="Bengaluru, India",
            source_url=url,
        )

    with patch.object(adapter, "_fetch_url", side_effect=mock_fetch):
        with patch.object(adapter, "get_job", side_effect=mock_get_job):
            # freshness_hours=8 has global hydration budget = 10, <=4h has 0
            jobs_8h = await adapter.search(JobSearchQuery(roles=["Software Engineer"], freshness_hours=8, limit=50))
            assert len(jobs_8h) == 4
            assert len(hydration_urls) <= 10

            hydration_urls.clear()
            # freshness_hours=4 skips sync hydration (budget = 0)
            jobs_4h = await adapter.search(JobSearchQuery(roles=["Software Engineer"], freshness_hours=4, limit=50))
            assert len(jobs_4h) == 4
            assert len(hydration_urls) == 0


@pytest.mark.asyncio
async def test_4h_freshness_request_budget_and_early_stopping():
    """Verifies that freshness_hours=4 uses minimal requests, caps queries at 2, and skips unnecessary pages."""
    adapter = LinkedInAdapter()
    urls_called = []

    mock_search_html = """
    <ul>
      <li>
        <div class="base-card" data-entity-urn="urn:li:jobPosting:9002">
          <a class="base-card__full-link" href="https://linkedin.com/jobs/view/9002"></a>
          <h3 class="base-search-card__title">Software Engineer</h3>
          <h4 class="base-search-card__subtitle"><a>Company 2</a></h4>
          <span class="job-search-card__location">Bengaluru, India</span>
          <time datetime="2026-09-06">2 hours ago</time>
        </div>
      </li>
    </ul>
    """

    async def mock_fetch(url):
        urls_called.append(url)
        return mock_search_html

    with patch.object(adapter, "_fetch_url", side_effect=mock_fetch):
        # Even with 5 roles and 5 skills, 4h freshness caps to 2 queries and skips offset 25 when page 0 yielded <10 jobs
        jobs = await adapter.search(JobSearchQuery(
            roles=["Software Engineer", "Backend Developer", "Frontend Developer", "DevOps"],
            skills=["python", "react", "node.js"],
            freshness_hours=4,
            limit=50,
        ))
        assert len(jobs) == 1  # 2nd query returned duplicate job id 9002 so deduplicated
        assert adapter._metrics.queries_count == 2
        # Exactly 2 search requests executed (1 page per query), 0 hydration requests
        assert len(urls_called) == 2
        assert adapter._metrics.hydration_requests_count == 0


@pytest.mark.asyncio
async def test_browser_fallback_budget_and_circuit_breaker():
    """Verifies that browser fallbacks are limited and disabled after failure."""
    adapter = LinkedInAdapter()
    crawl4ai_calls = []
    playwright_calls = []

    async def mock_fetch(url):
        return ""  # Always simulate guest API miss

    async def mock_crawl4ai(url, timeout=20.0):
        crawl4ai_calls.append(url)
        return None  # Crawl4AI failure

    async def mock_browser(url, timeout=20.0):
        playwright_calls.append(url)
        return None  # Browser failure

    with patch.object(adapter, "_fetch_url", side_effect=mock_fetch):
        with patch.object(adapter, "_fetch_via_crawl4ai", side_effect=mock_crawl4ai):
            with patch.object(adapter, "_fetch_via_browser", side_effect=mock_browser):
                jobs = await adapter.search(JobSearchQuery(roles=["Engineer 1", "Engineer 2"], freshness_hours=1))
                # For 1h freshness, browser fallback should only be attempted on the 1st query, then disabled for 2nd query
                assert len(crawl4ai_calls) == 1
                assert len(playwright_calls) == 1
                assert adapter._metrics.browser_fallbacks_count == 1
                assert len(jobs) == 0

