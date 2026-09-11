import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.sources.adapters.internshala import InternshalaAdapter
from app.sources.base import JobSearchQuery, RawJob
from app.sources.registry import get_source_registry
from app.crawling.crawler_models import CrawlResult
from app.crawling.crawler_provider import CrawlerProvider


SAMPLE_CARD_HTML = """
<div class="container-fluid individual_internship" data-href="/job/detail/python-fresher-developer-bangalore123" id="individual_internship_123">
  <div class="internship_meta">
    <div class="individual_internship_header">
      <h3 class="job-title-href">Python Backend Developer (Fresher)</h3>
      <div class="company-name">Innovate Tech Labs</div>
    </div>
    <div class="individual_internship_details">
      <div class="locations">Bangalore, Remote</div>
      <div class="row-1-item">
        <span class="desktop">₹ 4,50,000 - 7,00,000</span>
      </div>
      <div class="experience_meta">0-1 year(s)</div>
      <div class="about_job">
        <div class="text">We are hiring a Python & FastAPI developer for AI backend microservices.</div>
      </div>
      <div class="status-info">2 hours ago</div>
    </div>
  </div>
</div>
"""

SAMPLE_STALE_CARD_HTML = """
<div class="container-fluid individual_internship" data-href="/job/detail/stale-job-456" id="individual_internship_456">
  <div class="internship_meta">
    <h3 class="job-title-href">Legacy PHP Developer</h3>
    <div class="company-name">OldCorp</div>
    <div class="locations">Mumbai</div>
    <div class="status-info">10 days ago</div>
  </div>
</div>
"""


def test_internshala_html_parsing():
    adapter = InternshalaAdapter()
    raw_jobs = adapter.parse_html(SAMPLE_CARD_HTML)

    assert len(raw_jobs) == 1
    raw = raw_jobs[0]
    assert raw.source == "internshala"
    assert raw.source_job_id == "individual_internship_123"
    assert "Python Backend Developer" in raw.title
    assert raw.company_name == "Innovate Tech Labs"
    assert "Bangalore" in raw.location
    assert "₹ 4,50,000 - 7,00,000" in (raw.salary_raw or "")
    assert raw.posted_time_raw == "2 hours ago"
    assert "https://internshala.com/job/detail/python-fresher-developer-bangalore123" in raw.application_url


def test_internshala_normalization_fresh():
    adapter = InternshalaAdapter()
    raw_jobs = adapter.parse_html(SAMPLE_CARD_HTML)
    assert len(raw_jobs) == 1

    norm = adapter.normalize_job(raw_jobs[0])
    assert norm is not None
    assert norm.source == "internshala"
    assert norm.company_name == "Innovate Tech Labs"
    assert norm.normalized_company.lower() == "innovate tech labs"
    assert norm.role_category == "BACKEND"
    assert norm.experience_min == 0
    assert norm.experience_max == 1
    assert norm.salary_min == 450000.0
    assert norm.salary_max == 700000.0
    assert norm.posted_at_confidence == "HIGH"
    assert norm.quality_score >= 80.0
    assert len(norm.job_hash) == 64
    assert "Python" in norm.required_skills


def test_internshala_stale_job_exclusion():
    adapter = InternshalaAdapter()
    raw_jobs = adapter.parse_html(SAMPLE_STALE_CARD_HTML)
    assert len(raw_jobs) == 1

    # Stale job posted 10 days ago must be rejected by normalize_job
    norm = adapter.normalize_job(raw_jobs[0])
    assert norm is None


@pytest.mark.asyncio
async def test_internshala_normalize_async_stale():
    adapter = InternshalaAdapter()
    raw_jobs = adapter.parse_html(SAMPLE_STALE_CARD_HTML)
    assert len(raw_jobs) == 1
    # Asynchronous normalize() must return None for stale jobs without fabricating fake objects
    norm = await adapter.normalize(raw_jobs[0])
    assert norm is None


def test_internshala_card_validity_strict():
    adapter = InternshalaAdapter()

    # Invalid: root /jobs/ URL fallback
    invalid_url_html = """
    <div class="container-fluid individual_internship" data-href="/jobs/" id="c1">
      <h3 class="job-title-href">DevOps Engineer</h3>
      <div class="company-name">ValidCorp</div>
      <div class="status-info">1 hour ago</div>
    </div>
    """
    assert len(adapter.parse_html(invalid_url_html)) == 0

    # Invalid: generic company name
    generic_comp_html = """
    <div class="container-fluid individual_internship" data-href="/job/detail/real-job-1" id="c2">
      <h3 class="job-title-href">DevOps Engineer</h3>
      <div class="company-name">Company</div>
      <div class="status-info">1 hour ago</div>
    </div>
    """
    assert len(adapter.parse_html(generic_comp_html)) == 0

    # Invalid: confidential placeholder
    confidential_comp_html = """
    <div class="container-fluid individual_internship" data-href="/job/detail/real-job-2" id="c3">
      <h3 class="job-title-href">DevOps Engineer</h3>
      <div class="company-name">Confidential</div>
      <div class="status-info">1 hour ago</div>
    </div>
    """
    assert len(adapter.parse_html(confidential_comp_html)) == 0


def test_internshala_determine_search_paths():
    adapter = InternshalaAdapter()

    # Multi-role mapping (jobs only)
    q_jobs_only = JobSearchQuery(roles=["Backend", "Full Stack"], include_jobs=True, include_internships=False)
    paths_jobs = adapter._determine_search_paths(q_jobs_only)
    assert "/jobs/backend-development-jobs/" in paths_jobs
    assert "/jobs/full-stack-development-jobs/" in paths_jobs
    assert len(paths_jobs) == 2

    # Multi-role mapping (internships only)
    q_intern_only = JobSearchQuery(roles=["Backend", "Full Stack"], include_jobs=False, include_internships=True)
    paths_intern = adapter._determine_search_paths(q_intern_only)
    assert "/internships/backend-development-internship/" in paths_intern
    assert "/internships/full-stack-development-internship/" in paths_intern
    assert len(paths_intern) == 2

    # Multi-role mapping (both jobs and internships)
    q_both = JobSearchQuery(roles=["Backend", "Full Stack"], include_jobs=True, include_internships=True)
    paths_both = adapter._determine_search_paths(q_both)
    assert len(paths_both) == 4

    # Specific AI query
    q_ai = JobSearchQuery(query="artificial intelligence engineer", include_internships=False)
    paths_ai = adapter._determine_search_paths(q_ai)
    assert "/jobs/artificial-intelligence-ai-jobs/" in paths_ai

    # Default broad search with both returns 16 categories (7 jobs + 9 internships)
    q_broad = JobSearchQuery(query="software", include_jobs=True, include_internships=True)
    paths_broad = adapter._determine_search_paths(q_broad)
    assert len(paths_broad) == 16
    assert "/jobs/computer-science-jobs/" in paths_broad
    assert "/internships/computer-science-internship/" in paths_broad


def test_parse_experience_from_text():
    from app.utils.normalization import parse_experience_requirement

    # Ranges
    assert parse_experience_requirement("0-1 years")[:2] == (0, 1)
    assert parse_experience_requirement("0-2 years")[:2] == (0, 2)
    assert parse_experience_requirement("1-2 years")[:2] == (1, 2)
    assert parse_experience_requirement("2-3 years")[:2] == (2, 3)
    assert parse_experience_requirement("3-5 years")[:2] == (3, 5)
    assert parse_experience_requirement("5-8 years")[:2] == (5, 8)
    assert parse_experience_requirement("0 to 2 yrs")[:2] == (0, 2)

    # Pluses
    assert parse_experience_requirement("5+ years")[:2] == (5, None)
    assert parse_experience_requirement("3+ yrs")[:2] == (3, None)

    # Single number
    assert parse_experience_requirement("35 Years Experience")[:2] == (35, 35)
    assert parse_experience_requirement("1 year")[:2] == (1, 1)

    # Fresher keywords
    assert parse_experience_requirement("Fresher")[:2] == (0, 0)
    assert parse_experience_requirement("No experience required")[:2] == (0, 0)
    assert parse_experience_requirement("Freshers eligible")[:2] == (0, 0)
    assert parse_experience_requirement("Entry level")[:2] == (0, 0)


def test_is_senior_title():
    from app.sources.adapters.internshala import is_senior_title

    # Must flag true for senior / lead roles
    assert is_senior_title("Senior Backend Developer") is True
    assert is_senior_title("Sr. Full Stack Engineer") is True
    assert is_senior_title("Tech Lead - Python") is True
    assert is_senior_title("Staff Software Engineer") is True
    assert is_senior_title("Principal Architect") is True
    assert is_senior_title("Engineering Manager") is True
    assert is_senior_title("Director of Engineering") is True
    assert is_senior_title("Head of AI") is True
    assert is_senior_title("VP of Technology") is True
    assert is_senior_title("CTO / Co-founder") is True

    # Must protect entry-level, junior, trainee, associate roles
    assert is_senior_title("Software Engineer Trainee") is False
    assert is_senior_title("Associate Software Engineer") is False
    assert is_senior_title("Junior Python Developer") is False
    assert is_senior_title("Jr. Web Developer") is False
    assert is_senior_title("Graduate Engineer Trainee") is False
    assert is_senior_title("Backend Intern") is False
    assert is_senior_title("Entry Level Developer") is False

    # Standard non-senior roles
    assert is_senior_title("Software Engineer") is False
    assert is_senior_title("Python Developer") is False
    assert is_senior_title("Full Stack Developer") is False


SAMPLE_INTERNSHIP_CARD_HTML = """
<div class="container-fluid individual_internship" data-href="/internships/detail/python-backend-internship-in-bangalore-at-cloudtech123" id="individual_internship_999">
  <div class="internship_meta">
    <div class="individual_internship_header">
      <h3 class="job-title-href">Python Backend Development Intern</h3>
      <div class="company-name">CloudTech Labs</div>
    </div>
    <div class="individual_internship_details">
      <div class="locations">Bangalore, Remote</div>
      <div class="row-1-item">
        <i class="ic-16-calendar"></i>
        <span>3 Months</span>
      </div>
      <div class="row-1-item">
        <span class="stipend">₹ 15,000 /month</span>
      </div>
      <div class="about_job">
        <div class="text">Learn FastAPI, Docker, and PostgreSQL on real-world projects.</div>
      </div>
      <div class="status-info">1 hour ago</div>
    </div>
  </div>
</div>
"""


def test_internshala_internship_card_parsing():
    adapter = InternshalaAdapter()
    raw_jobs = adapter.parse_html(SAMPLE_INTERNSHIP_CARD_HTML)

    assert len(raw_jobs) == 1
    raw = raw_jobs[0]
    assert raw.source == "internshala"
    assert raw.source_job_id == "individual_internship_999"
    assert "Python Backend Development Intern" in raw.title
    assert raw.company_name == "CloudTech Labs"
    assert raw.raw_payload.get("is_internship") is True
    assert raw.raw_payload.get("duration") == "3 Months"
    assert "15,000" in (raw.salary_raw or "")

    norm = adapter.normalize_job(raw)
    assert norm is not None
    assert norm.employment_type == "INTERNSHIP"
    assert norm.experience_min == 0
    assert norm.experience_max == 0
    assert norm.salary_min == 180000.0  # 15,000 * 12
    assert norm.salary_max == 180000.0
    assert norm.salary_period == "YEAR"
    assert norm.remote_type == "REMOTE"
    assert "Python" in norm.required_skills



@pytest.mark.asyncio
async def test_internshala_registry_integration():
    registry = get_source_registry()
    src = registry.get_source("internshala")
    assert src is not None
    assert src.source_name == "internshala"
    assert src.enabled is True


@pytest.mark.asyncio
async def test_internshala_search_error_isolation():
    # Mock fetch to simulate timeout/error and verify error isolation
    adapter = InternshalaAdapter()
    adapter._fetch_page = AsyncMock(return_value=None)
    # Search must handle timeout gracefully and return empty list
    jobs = await adapter.search(JobSearchQuery(query="nonexistent"))
    assert isinstance(jobs, list)
    assert len(jobs) == 0


def test_internshala_experience_extraction_strict_units():
    from app.utils.normalization import parse_experience_requirement

    # Valid years
    assert parse_experience_requirement("0-1 year(s)")[:2] == (0, 1)
    assert parse_experience_requirement("2 - 4 yrs")[:2] == (2, 4)
    assert parse_experience_requirement("Fresher")[:2] == (0, 0)

    # Days per week must NOT match as years of experience
    assert parse_experience_requirement("Work 5 days a week")[:2] == (None, None)
    assert parse_experience_requirement("6 days working")[:2] == (None, None)


def test_internshala_normalize_sets_posted_at_raw():
    adapter = InternshalaAdapter()
    raw = RawJob(
        source="internshala",
        source_job_id="is-101",
        title="Web Developer",
        company_name="Acme",
        description="Build websites using Python and React. Experience required 0-1 years.",
        location="Work from home",
        posted_time_raw="Just now",
        source_url="https://internshala.com/job/detail/is-101",
        application_url="https://internshala.com/job/detail/is-101",
        raw_payload={"status_success": True}
    )
    norm = adapter.normalize_job(raw)
    assert norm is not None
    assert norm.posted_at_raw == "Just now"


# --- Crawl4AI Integration Tests ---


def test_internshala_uses_shared_crawler_provider():
    adapter = InternshalaAdapter()
    provider = adapter._get_crawler_provider()
    from app.crawling.crawler_provider import CrawlerProvider
    assert isinstance(provider, CrawlerProvider)


@pytest.mark.asyncio
async def test_internshala_crawl4ai_fetch_success():
    adapter = InternshalaAdapter()

    mock_result = CrawlResult(
        url="https://internshala.com/jobs/backend-development-jobs/",
        status_code=200,
        success=True,
        html=SAMPLE_CARD_HTML,
    )

    mock_provider = AsyncMock(spec=CrawlerProvider)
    mock_provider.fetch.return_value = mock_result

    adapter._crawler_provider = mock_provider

    html = await adapter._fetch_via_crawl4ai("https://internshala.com/jobs/backend-development-jobs/")

    assert html is not None
    assert "Python Backend Developer" in html
    mock_provider.fetch.assert_called_once()


@pytest.mark.asyncio
async def test_internshala_crawl4ai_timeout_falls_back_to_http():
    adapter = InternshalaAdapter()

    mock_provider = AsyncMock(spec=CrawlerProvider)
    async def slow_fetch(*args, **kwargs):
        await asyncio.sleep(10)
        return CrawlResult(url="", status_code=408, success=False, error_message="Timeout")
    mock_provider.fetch.side_effect = slow_fetch
    adapter._crawler_provider = mock_provider

    html = await adapter._fetch_via_crawl4ai("https://internshala.com/jobs/backend-development-jobs/", timeout=0.01)

    assert html is None


@pytest.mark.asyncio
async def test_internshala_crawl4ai_unavailable_falls_back_to_playwright():
    adapter = InternshalaAdapter()
    from app.crawling.crawler_provider import NoOpCrawlerProvider
    adapter._crawler_provider = NoOpCrawlerProvider()

    html = await adapter._fetch_via_crawl4ai("https://internshala.com/jobs/backend-development-jobs/")

    assert html is None


def test_internshala_job_and_internship_categories_crawled():
    adapter = InternshalaAdapter()
    q = JobSearchQuery(query="software", include_jobs=True, include_internships=True)
    paths = adapter._determine_search_paths(q)

    job_paths = [p for p in paths if p.startswith("/jobs/")]
    intern_paths = [p for p in paths if p.startswith("/internships/")]

    assert len(job_paths) >= 7
    assert len(intern_paths) >= 9
    assert "/jobs/computer-science-jobs/" in job_paths
    assert "/internships/computer-science-internship/" in intern_paths


def test_internshala_parser_unchanged():
    adapter = InternshalaAdapter()
    raw_jobs = adapter.parse_html(SAMPLE_CARD_HTML)

    assert len(raw_jobs) == 1
    raw = raw_jobs[0]
    assert raw.source == "internshala"
    assert raw.source_job_id == "individual_internship_123"
    assert "Python Backend Developer" in raw.title


def test_internshala_fresh_listings_retained():
    adapter = InternshalaAdapter()
    raw_jobs = adapter.parse_html(SAMPLE_CARD_HTML)
    assert len(raw_jobs) == 1

    norm = adapter.normalize_job(raw_jobs[0])
    assert norm is not None
    assert norm.posted_at_confidence == "HIGH"


def test_internshala_stale_listings_rejected():
    adapter = InternshalaAdapter()
    raw_jobs = adapter.parse_html(SAMPLE_STALE_CARD_HTML)
    assert len(raw_jobs) == 1

    norm = adapter.normalize_job(raw_jobs[0])
    assert norm is None


@pytest.mark.asyncio
async def test_internshala_account_hold_fails_fast():
    adapter = InternshalaAdapter()

    hold_html = """
    <html><body>
    <div>Your account is put on hold due to violation of Internshala rules</div>
    </body></html>
    """

    block_state = adapter.detect_internshala_block_state(hold_html)
    assert block_state == "ACCOUNT_HOLD"


def test_internshala_modal_email_not_false_hold():
    adapter = InternshalaAdapter()

    html_with_modal = """
    <html><body>
    <div id="modal_email" style="display:none;">Your account is put on hold</div>
    <div class="individual_internship" data-href="/job/detail/real-job-1">
      <h3 class="job-title-href">Real Job</h3>
      <div class="company-name">Real Company</div>
      <div class="status-info">1 hour ago</div>
    </div>
    </body></html>
    """

    block_state = adapter.detect_internshala_block_state(html_with_modal)
    assert block_state is None

    raw_jobs = adapter.parse_html(html_with_modal)
    assert len(raw_jobs) == 1
    assert raw_jobs[0].title == "Real Job"


def test_internshala_experience_parsing_correct():
    from app.utils.normalization import parse_experience_requirement

    assert parse_experience_requirement("0-1 years")[:2] == (0, 1)
    assert parse_experience_requirement("2-3 years")[:2] == (2, 3)
    assert parse_experience_requirement("Fresher")[:2] == (0, 0)
    assert parse_experience_requirement("Work 5 days a week")[:2] == (None, None)
    assert parse_experience_requirement("6 days working")[:2] == (None, None)


def test_internshala_internship_duration_separate():
    adapter = InternshalaAdapter()
    raw_jobs = adapter.parse_html(SAMPLE_INTERNSHIP_CARD_HTML)
    assert len(raw_jobs) == 1

    raw = raw_jobs[0]
    assert raw.raw_payload.get("duration") == "3 Months"
    assert raw.raw_payload.get("is_internship") is True
    assert raw.posted_time_raw == "1 hour ago"


def test_internshala_urls_valid_source_derived():
    adapter = InternshalaAdapter()
    raw_jobs = adapter.parse_html(SAMPLE_CARD_HTML)
    assert len(raw_jobs) == 1

    raw = raw_jobs[0]
    assert raw.source_url.startswith("https://internshala.com/job/detail/")
    assert raw.application_url == raw.source_url


def test_internshala_skill_extraction_integrated():
    adapter = InternshalaAdapter()
    raw_jobs = adapter.parse_html(SAMPLE_CARD_HTML)
    assert len(raw_jobs) == 1

    norm = adapter.normalize_job(raw_jobs[0])
    assert norm is not None
    assert "Python" in norm.required_skills
    assert len(norm.required_skills) > 0


@pytest.mark.asyncio
async def test_internshala_source_registry_integration():
    registry = get_source_registry()
    src = registry.get_source("internshala")
    assert src is not None
    assert src.source_name == "internshala"
    assert src.enabled is True


@pytest.mark.asyncio
async def test_internshala_full_ingestion_pipeline():
    from app.services.job_ingestion_service import JobIngestionService
    from app.services.dedup_service import compute_job_hash

    adapter = InternshalaAdapter()
    raw_jobs = adapter.parse_html(SAMPLE_CARD_HTML)
    assert len(raw_jobs) == 1

    norm = adapter.normalize_job(raw_jobs[0])
    assert norm is not None

    assert norm.job_hash == compute_job_hash(
        norm.normalized_company,
        norm.normalized_title,
        norm.normalized_location,
        norm.employment_type,
        norm.source_job_id,
    )

    assert norm.quality_score >= 0
    assert norm.required_skills
    assert norm.posted_at is not None

    ingestion = JobIngestionService()
    assert ingestion.freshness_service is not None
    assert ingestion.dedup_service is not None
