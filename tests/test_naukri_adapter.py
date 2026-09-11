import pytest
from datetime import datetime, timezone, timedelta
from app.sources.adapters.naukri import (
    NaukriAdapter,
    extract_naukri_job_id,
)
from app.sources.base import JobSearchQuery, RawJob
from app.sources.registry import get_source_registry
from app.config import settings


SAMPLE_NAUKRI_JSON = {
    "jobDetails": [
        {
            "jobId": "040926001234",
            "title": "Full Stack Developer",
            "companyName": "TechCorp India",
            "jobDescription": "Looking for a Full Stack Developer skilled in Python, React, PostgreSQL, and Docker.",
            "experienceStr": "0-2 Yrs",
            "placeholders": [
                {"type": "experience", "label": "0-2 Yrs"},
                {"type": "salary", "label": "₹ 3 - 6 Lacs P.A."},
                {"type": "location", "label": "Bengaluru, Hybrid"}
            ],
            "salary": "₹ 3 - 6 Lacs P.A.",
            "location": "Bengaluru, Hybrid",
            "workMode": "Hybrid",
            "tagsAndSkills": "Python, React, PostgreSQL, Docker, FastAPI",
            "createdDate": int((datetime.now(timezone.utc) - timedelta(hours=3)).timestamp() * 1000),
            "footerPlaceholderLabel": "3 hours ago",
            "jdURL": "/job-listings-full-stack-developer-techcorp-india-bengaluru-0-to-2-years-040926001234",
            "staticUrl": "job-listings-full-stack-developer-techcorp-india-bengaluru-0-to-2-years-040926001234",
        }
    ]
}

SAMPLE_NAUKRI_HTML = """
<div class="srp-jobtuple-wrapper" data-job-id="040926005678">
  <div class="cust-job-tuple layout-wrapper lay-2 sjw__tuple">
    <div class="row1">
      <a class="title" href="https://www.naukri.com/job-listings-backend-developer-cloudsys-pune-0-to-1-years-040926005678" title="Python Backend Developer">Python Backend Developer</a>
    </div>
    <div class="row2">
      <span class="comp-dtls-wrap">
        <a class="comp-name mw-25" title="CloudSys Software">CloudSys Software</a>
      </span>
    </div>
    <div class="row3">
      <div class="job-desc text-ellipsis">Build scalable APIs with Python, FastAPI, and Redis microservices.</div>
    </div>
    <div class="row4">
      <span class="exp-wrap">
        <span class="expwdth">0-1 Yrs</span>
      </span>
      <span class="sal-wrap">
        <span class="ni-job-tuple-icon-salary">4-7 LPA</span>
      </span>
      <span class="loc-wrap">
        <span class="locWdth">Pune, Remote</span>
      </span>
    </div>
    <div class="row5">
      <ul class="tags-gt">
        <li class="dot-gt tag-li">Python</li>
        <li class="dot-gt tag-li">FastAPI</li>
        <li class="dot-gt tag-li">Redis</li>
      </ul>
    </div>
    <div class="row6">
      <span class="job-post-day">2 hours ago</span>
    </div>
  </div>
</div>
"""

SAMPLE_STALE_NAUKRI_JSON = {
    "jobDetails": [
        {
            "jobId": "010826009999",
            "title": "Legacy Java Developer",
            "companyName": "Ancient Enterprises",
            "jobDescription": "Maintaining legacy monolith.",
            "createdDate": int((datetime.now(timezone.utc) - timedelta(days=15)).timestamp() * 1000),
            "footerPlaceholderLabel": "15 days ago",
            "jdURL": "/job-listings-legacy-java-developer-010826009999",
        }
    ]
}


def test_naukri_json_parsing():
    adapter = NaukriAdapter()
    raw_jobs = adapter.parse_json(SAMPLE_NAUKRI_JSON)

    assert len(raw_jobs) == 1
    raw = raw_jobs[0]
    assert raw.source == "naukri"
    assert raw.source_job_id == "040926001234"
    assert raw.title == "Full Stack Developer"
    assert raw.company_name == "TechCorp India"
    assert "Bengaluru" in (raw.location or "")
    assert raw.remote_type == "HYBRID"
    assert "₹ 3 - 6 Lacs P.A." in (raw.salary_raw or "")
    assert "0-2 Yrs" in (raw.experience_raw or "")
    assert "040926001234" in raw.application_url


def test_naukri_html_parsing():
    adapter = NaukriAdapter()
    raw_jobs = adapter.parse_html(SAMPLE_NAUKRI_HTML)

    assert len(raw_jobs) == 1
    raw = raw_jobs[0]
    assert raw.source == "naukri"
    assert raw.source_job_id == "040926005678"
    assert "Python Backend Developer" in raw.title
    assert raw.company_name == "CloudSys Software"
    assert "Pune" in (raw.location or "")
    assert raw.remote_type == "REMOTE"
    assert "4-7 LPA" in (raw.salary_raw or "")
    assert "0-1 Yrs" in (raw.experience_raw or "")
    assert raw.posted_time_raw == "2 hours ago"


def test_naukri_job_id_extraction():
    # Direct numeric string
    assert extract_naukri_job_id("040926001234") == "040926001234"
    # Extracted from URL with hyphens
    url = "https://www.naukri.com/job-listings-python-developer-company-city-0-to-2-years-220826012440"
    assert extract_naukri_job_id(url) == "220826012440"
    # Extracted from URL with query params
    url_query = "https://www.naukri.com/job-listings-sde-1234567890?src=jobsearchDesk"
    assert extract_naukri_job_id(url_query) == "1234567890"


def test_naukri_salary_parsing():
    from app.utils.normalization import parse_salary_text

    # Lacs P.A.
    s1 = parse_salary_text("₹3 - 6 Lacs P.A.")
    assert s1["salary_min"] == 300000.0
    assert s1["salary_max"] == 600000.0

    # LPA range
    s2 = parse_salary_text("3-6 LPA")
    assert s2["salary_min"] == 300000.0
    assert s2["salary_max"] == 600000.0

    # Single LPA
    s3 = parse_salary_text("₹5 LPA")
    assert s3["salary_min"] == 500000.0
    assert s3["salary_max"] == 500000.0

    # Crore format
    s4 = parse_salary_text("1-2 Cr")
    assert s4["salary_min"] == 10000000.0
    assert s4["salary_max"] == 20000000.0

    # Not disclosed
    s5 = parse_salary_text("Not disclosed")
    assert s5["salary_min"] is None
    assert s5["salary_max"] is None


from app.utils.normalization import parse_experience_requirement


def test_naukri_experience_parsing():
    # Standard Naukri ranges
    assert parse_experience_requirement("0-1 Yrs")[:2] == (0, 1)
    assert parse_experience_requirement("0-2 Yrs")[:2] == (0, 2)
    assert parse_experience_requirement("1-3 Yrs")[:2] == (1, 3)
    assert parse_experience_requirement("3-5 Yrs")[:2] == (3, 5)

    # Broad range parsing without artificial squashing
    assert parse_experience_requirement("0-5 Yrs")[:2] == (0, 5)
    assert parse_experience_requirement("0-3 Yrs")[:2] == (0, 3)
    assert parse_experience_requirement("0-4 Yrs")[:2] == (0, 4)
    assert parse_experience_requirement("1-4 Yrs")[:2] == (1, 4)

    # Fresher keywords
    assert parse_experience_requirement("Fresher")[:2] == (0, 0)
    assert parse_experience_requirement("Entry level")[:2] == (0, 0)
    assert parse_experience_requirement("No experience")[:2] == (0, 0)

    # Plus patterns
    assert parse_experience_requirement("1+ years")[:2] == (1, None)
    assert parse_experience_requirement("5+ Yrs")[:2] == (5, None)

    # Single number
    assert parse_experience_requirement("1 Yrs")[:2] == (1, 1)
    assert parse_experience_requirement(None)[:2] == (None, None)


def test_naukri_location_and_work_mode():
    adapter = NaukriAdapter()

    # Remote inferred from location
    raw_remote = RawJob(
        source="naukri",
        source_job_id="1",
        title="AI Engineer",
        company_name="AI Labs",
        description="Remote AI role",
        location="Remote - India",
        posted_time_raw="2 hours ago",
        source_url="https://www.naukri.com/job-1",
        raw_payload={"workMode": "Remote"}
    )
    norm_remote = adapter.normalize_job(raw_remote)
    assert norm_remote is not None
    assert norm_remote.remote_type == "REMOTE"
    assert norm_remote.normalized_location in ("Remote", "Remote (India)")

    # Hybrid
    raw_hybrid = RawJob(
        source="naukri",
        source_job_id="2",
        title="Backend Engineer",
        company_name="Cloud Corp",
        description="Hybrid role",
        location="Bengaluru",
        remote_type="HYBRID",
        posted_time_raw="1 hour ago",
        source_url="https://www.naukri.com/job-2",
        raw_payload={"workMode": "Hybrid"}
    )
    norm_hybrid = adapter.normalize_job(raw_hybrid)
    assert norm_hybrid is not None
    assert norm_hybrid.remote_type == "HYBRID"
    assert norm_hybrid.normalized_location == "Bengaluru"


def test_naukri_skills_extraction():
    adapter = NaukriAdapter()
    raw = RawJob(
        source="naukri",
        source_job_id="3",
        title="Generative AI & LLM Engineer",
        company_name="DeepTech",
        description="Develop RAG pipelines with Python, PyTorch, LangChain, and Docker microservices.",
        location="Bengaluru",
        posted_time_raw="2 hours ago",
        source_url="https://www.naukri.com/job-3",
        raw_payload={"tagsAndSkills": "Python, LLM, LangChain, PyTorch, Docker"}
    )
    norm = adapter.normalize_job(raw)
    assert norm is not None
    assert "Python" in norm.required_skills
    assert "LLM" in norm.required_skills
    assert "LangChain" in norm.required_skills
    assert "PyTorch" in norm.required_skills
    assert "Docker" in norm.required_skills
    assert norm.role_category == "GEN_AI"


def test_naukri_fresh_posting_normalization():
    adapter = NaukriAdapter()
    raw_jobs = adapter.parse_json(SAMPLE_NAUKRI_JSON)
    assert len(raw_jobs) == 1

    norm = adapter.normalize_job(raw_jobs[0])
    assert norm is not None
    assert norm.source == "naukri"
    assert norm.company_name == "TechCorp India"
    assert norm.normalized_company.lower() == "techcorp india"
    assert norm.role_category == "FULL_STACK"
    assert norm.experience_min == 0
    assert norm.experience_max == 2
    assert norm.salary_min == 300000.0
    assert norm.salary_max == 600000.0
    assert norm.posted_at_confidence == "HIGH"
    assert norm.quality_score >= 80.0
    assert len(norm.job_hash) == 64
    assert "Python" in norm.required_skills
    assert "React" in norm.required_skills


def test_naukri_stale_posting_rejection():
    adapter = NaukriAdapter()
    raw_jobs = adapter.parse_json(SAMPLE_STALE_NAUKRI_JSON)
    assert len(raw_jobs) == 1

    # Stale posting posted 15 days ago must be rejected
    norm = adapter.normalize_job(raw_jobs[0])
    assert norm is None


def test_naukri_low_confidence_quarantine():
    adapter = NaukriAdapter()
    raw = RawJob(
        source="naukri",
        source_job_id="999",
        title="Junior Developer",
        company_name="VagueCorp",
        description="Coding job",
        location="Delhi NCR",
        posted_time_raw="30+ Days Ago",
        source_url="https://www.naukri.com/job-999",
        raw_payload={"footerPlaceholderLabel": "30+ Days Ago"}
    )
    # Stale 30+ days ago must be quarantined (return None) per 24-hour freshness rules
    norm = adapter.normalize_job(raw)
    assert norm is None

    # In recall-first architecture, 'Recently' is rescued into HIGH confidence fresh timestamp
    raw_recent = RawJob(
        source="naukri",
        source_job_id="1000",
        title="Junior Developer",
        company_name="FreshCorp",
        description="Coding job",
        location="Delhi NCR",
        posted_time_raw="Recently",
        source_url="https://www.naukri.com/job-1000",
        raw_payload={"footerPlaceholderLabel": "Recently"}
    )
    norm_recent = adapter.normalize_job(raw_recent)
    assert norm_recent is not None
    assert norm_recent.posted_at is not None


def test_naukri_senior_role_detection():
    from app.sources.adapters.internshala import is_senior_title

    # Senior titles flagged
    assert is_senior_title("Senior Full Stack Developer") is True
    assert is_senior_title("Sr. Backend Engineer") is True
    assert is_senior_title("Lead AI Engineer") is True
    assert is_senior_title("Principal Software Architect") is True

    # Junior/fresher protected
    assert is_senior_title("Associate Software Engineer") is False
    assert is_senior_title("Graduate Engineer Trainee") is False
    assert is_senior_title("Full Stack Developer") is False
    assert is_senior_title("Python Developer") is False


@pytest.mark.asyncio
async def test_naukri_network_error_isolation():
    from unittest.mock import patch
    # Pass an unreachable/very low timeout and mock Crawl4AI failure to test resilience
    bad_adapter = NaukriAdapter(timeout=0.001, max_retries=1)
    with patch.object(bad_adapter, "_fetch_via_crawl4ai", return_value=None):
        jobs = await bad_adapter.search(JobSearchQuery(query="software engineer", limit=5))
        assert isinstance(jobs, list)
        assert len(jobs) == 0


@pytest.mark.asyncio
async def test_naukri_crawl4ai_fallback_discovery():
    from unittest.mock import patch, AsyncMock
    adapter = NaukriAdapter()

    # Mock HTTP returning 406 (recaptcha required)
    mock_html = """
    <div class="srp-jobtuple-wrapper" data-job-id="browser12345">
        <a class="title" href="/job-browser12345">Full Stack Engineer</a>
        <a class="comp-name">Acme Corp</a>
        <span class="exp-wrap"><span class="expwdth">0-2 Yrs</span></span>
        <span class="sal-wrap"><span class="ni-job-tuple-icon-srp-rupee">₹ 5-8 Lacs PA</span></span>
        <span class="loc-wrap"><span class="locWdth">Bengaluru</span></span>
        <div class="job-desc">Work with React, Python, FastAPI</div>
        <ul class="tags-gt"><li class="dot-gt">Python</li><li class="dot-gt">React</li></ul>
        <span class="job-post-day">1 hour ago</span>
    </div>
    """
    with patch.object(adapter, "_fetch_url", new_callable=AsyncMock, return_value=(406, "recaptcha required")), \
         patch.object(adapter, "_fetch_via_crawl4ai", new_callable=AsyncMock, return_value=mock_html):
        jobs = await adapter.search(JobSearchQuery(query="full stack", limit=5))
        assert len(jobs) >= 1
        assert jobs[0].source_job_id == "browser12345"
        assert jobs[0].title == "Full Stack Engineer"
        assert jobs[0].company_name == "Acme Corp"
        assert jobs[0].posted_time_raw == "1 hour ago"


@pytest.mark.asyncio
async def test_naukri_crawl4ai_provider_integration():
    from unittest.mock import patch, AsyncMock, MagicMock
    from app.crawling.crawler_models import CrawlResult
    adapter = NaukriAdapter()

    # Mock provider that returns valid HTML
    mock_provider = MagicMock()
    mock_crawl_result = CrawlResult(
        url="https://www.naukri.com/full-stack-developer-jobs",
        status_code=200,
        success=True,
        html="""
        <div class="srp-jobtuple-wrapper" data-job-id="crawl12345">
            <a class="title" href="/job-crawl12345">Python Developer</a>
            <a class="comp-name">TechCorp</a>
            <span class="exp-wrap"><span class="expwdth">0-1 Yrs</span></span>
            <span class="loc-wrap"><span class="locWdth">Bengaluru</span></span>
            <span class="job-post-day">30 mins ago</span>
        </div>
        """,
        duration_sec=2.5,
    )
    mock_provider.fetch = AsyncMock(return_value=mock_crawl_result)

    with patch.object(adapter, "_get_crawler_provider", return_value=mock_provider), \
         patch.object(adapter, "_fetch_url", new_callable=AsyncMock, return_value=(403, "blocked")):
        jobs = await adapter.search(JobSearchQuery(query="python developer", limit=5))
        assert len(jobs) >= 1
        assert jobs[0].source_job_id == "crawl12345"
        assert jobs[0].title == "Python Developer"
        assert jobs[0].company_name == "TechCorp"

        # Verify provider.fetch was called with CrawlRequest
        mock_provider.fetch.assert_awaited()
        call_args = mock_provider.fetch.call_args
        assert call_args is not None
        crawl_request = call_args[0][0] if call_args[0] else call_args.kwargs.get("request")
        if crawl_request:
            assert "naukri.com" in crawl_request.url
            assert crawl_request.wait_for is not None
            assert crawl_request.cache_mode == "BYPASS"


@pytest.mark.asyncio
async def test_naukri_crawl4ai_timeout_and_fallback():
    from unittest.mock import patch, AsyncMock
    adapter = NaukriAdapter()

    # Mock Crawl4AI provider that times out
    with patch.object(adapter, "_get_crawler_provider", return_value=None), \
         patch.object(adapter, "_fetch_url", new_callable=AsyncMock, return_value=(200, "<html></html>")):
        # Should fall back to HTTP when Crawl4AI is unavailable
        jobs = await adapter.search(JobSearchQuery(query="software engineer", limit=5))
        # Since HTTP returns empty HTML, we expect empty results
        assert isinstance(jobs, list)


@pytest.mark.asyncio
async def test_naukri_crawl4ai_error_handling():
    from unittest.mock import patch, AsyncMock
    adapter = NaukriAdapter()

    # Mock Crawl4AI provider that returns failure
    with patch.object(adapter, "_get_crawler_provider", return_value=None), \
         patch.object(adapter, "_fetch_url", new_callable=AsyncMock, return_value=(403, "blocked")):
        # Should handle Crawl4AI unavailability gracefully
        jobs = await adapter.search(JobSearchQuery(query="backend developer", limit=5))
        assert isinstance(jobs, list)


@pytest.mark.asyncio
async def test_naukri_registry_integration():
    registry = get_source_registry()
    src = registry.get_source("naukri")
    assert src is not None
    assert src.source_name == "naukri"

    # Verify enable/disable behavior based on settings
    was_enabled = settings.SOURCE_NAUKRI_ENABLED
    try:
        settings.SOURCE_NAUKRI_ENABLED = False
        src.enabled = False
        assert src not in registry.get_enabled_sources()

        settings.SOURCE_NAUKRI_ENABLED = True
        src.enabled = True
        assert src in registry.get_enabled_sources()
    finally:
        settings.SOURCE_NAUKRI_ENABLED = was_enabled
        src.enabled = was_enabled


@pytest.mark.asyncio
async def test_naukri_sync_api(async_client):
    from unittest.mock import patch, AsyncMock
    adapter = NaukriAdapter()
    sample_raw = adapter.parse_json(SAMPLE_NAUKRI_JSON)[0]
    with patch.object(NaukriAdapter, "search", new_callable=AsyncMock, return_value=[sample_raw]):
        res = await async_client.post("/api/v1/jobs/sync?source=naukri")
        assert res.status_code == 200
        data = res.json()
        assert "total_discovered" in data
        assert "fresh_jobs" in data



@pytest.mark.asyncio
async def test_naukri_end_to_end_pipeline():
    from unittest.mock import AsyncMock, patch
    from app.database import async_session_factory
    from app.services.job_ingestion_service import JobIngestionService

    adapter = NaukriAdapter()

    fresh_raw = adapter.parse_json(SAMPLE_NAUKRI_JSON)[0]
    stale_raw = adapter.parse_json(SAMPLE_STALE_NAUKRI_JSON)[0]
    senior_raw = RawJob(
        source="naukri",
        source_job_id="040926008888",
        title="Principal Software Engineer",
        company_name="Senior Corp",
        description="Senior leadership",
        location="Bengaluru",
        experience_raw="8-12 Yrs",
        posted_time_raw="1 hour ago",
        source_url="https://www.naukri.com/job-senior-040926008888",
        raw_payload={"footerPlaceholderLabel": "1 hour ago", "experienceStr": "8-12 Yrs"}
    )
    dup_raw = RawJob(
        source="naukri",
        source_job_id="040926001234-dup",
        title="Full Stack Developer",
        company_name="TechCorp India",
        description="Looking for a Full Stack Developer skilled in Python, React, PostgreSQL, and Docker.",
        location="Bengaluru, Hybrid",
        experience_raw="0-2 Yrs",
        posted_time_raw="3 hours ago",
        source_url="https://www.naukri.com/job-dup",
        raw_payload=fresh_raw.raw_payload
    )

    with patch.object(adapter, "search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = [fresh_raw, stale_raw, senior_raw, dup_raw]

        ingestion = JobIngestionService()
        async with async_session_factory() as session:
            stats = await ingestion.ingest_source(
                session,
                adapter,
                JobSearchQuery(experience_max=2, freshness_hours=24)
            )

            assert stats["total_discovered"] == 4
            assert stats["filtered_by_freshness"] >= 1
            # In recall-first architecture: experience filtering is bypassed at ingestion
            assert stats["filtered_by_experience"] == 0
            assert stats["deduplicated"] >= 1
            assert (stats["canonical_saved"] + stats["updated_existing"]) >= 1


@pytest.mark.asyncio
async def test_naukri_multipage_search():
    import json
    from unittest.mock import AsyncMock, patch
    adapter = NaukriAdapter()

    urls_called = []
    async def mock_fetch(url, headers=None):
        urls_called.append(url)
        if "pageNo=1" in url:
            return 200, json.dumps({
                "jobDetails": [{
                    "jobId": "p1-1",
                    "title": "Software Engineer",
                    "companyName": "TechCorp",
                    "jobDescription": "Python dev",
                    "footerPlaceholderLabel": "Just now",
                    "jdURL": "/job-p1-1"
                }]
            })
        elif "pageNo=2" in url:
            return 200, json.dumps({
                "jobDetails": [{
                    "jobId": "p2-1",
                    "title": "Software Engineer",
                    "companyName": "TechCorp",
                    "jobDescription": "Python dev",
                    "footerPlaceholderLabel": "2 hours ago",
                    "jdURL": "/job-p2-1"
                }]
            })
        return 200, json.dumps({"jobDetails": []})

    with patch.object(adapter, "_fetch_url", side_effect=mock_fetch), \
         patch.object(adapter, "_fetch_via_crawl4ai", new_callable=AsyncMock, return_value=None):
        jobs = await adapter.search(JobSearchQuery(roles=["Software Engineer"], limit=100))
        assert any("pageNo=1" in u for u in urls_called)
        assert any("pageNo=2" in u for u in urls_called)
        assert len(jobs) == 2

