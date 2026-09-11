import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.utils.browser_stealth import (
    get_random_viewport,
    should_abort_resource,
    apply_stealth_context,
    DEFAULT_STEALTH_USER_AGENT,
    STEALTH_INIT_SCRIPT,
)
from app.utils.browser_context import resolve_user_data_dir
from app.utils.http_client import (
    HTTPResult,
    is_tor_proxy_available,
    resilient_fetch,
)
from app.utils.json_ld import (
    clean_html_text,
    extract_json_ld_blocks,
    extract_job_posting_ld,
    parse_job_with_fallback,
)


# ==============================================================================
# 1. Browser Stealth & Anti-Fingerprinting Tests
# ==============================================================================

def test_random_viewport_bounds():
    for _ in range(50):
        vp = get_random_viewport()
        assert 1366 <= vp["width"] <= 1920
        assert 768 <= vp["height"] <= 1080


def test_resource_filter_blocking():
    # Media and font resource types must be blocked
    assert should_abort_resource("image", "https://cdn.example.com/photo.png") is True
    assert should_abort_resource("media", "https://cdn.example.com/video.mp4") is True
    assert should_abort_resource("font", "https://fonts.example.com/inter.woff2") is True

    # File extensions in URLs must be blocked even if resource_type is ambiguous
    assert should_abort_resource("other", "https://example.com/banner.jpg?size=large") is True
    assert should_abort_resource("other", "https://example.com/assets/font.ttf") is True
    assert should_abort_resource("other", "https://example.com/logo.svg") is True

    # Tracking & telemetry scripts must be aborted
    assert should_abort_resource("script", "https://www.google-analytics.com/analytics.js") is True
    assert should_abort_resource("fetch", "https://telemetry.enterprise.com/events") is True
    assert should_abort_resource("xhr", "https://static.hotjar.com/c/hotjar.js") is True

    # Essential document, JSON API, and core scripts must be permitted
    assert should_abort_resource("document", "https://www.linkedin.com/jobs/view/123456") is False
    assert should_abort_resource("xhr", "https://api.wellfound.com/graphql") is False
    assert should_abort_resource("fetch", "https://www.instahyre.com/api/v1/jobs_search") is False


@pytest.mark.asyncio
async def test_apply_stealth_context():
    mock_context = MagicMock()
    mock_context.add_init_script = AsyncMock()
    mock_context.set_viewport_size = AsyncMock()
    mock_context.set_extra_http_headers = AsyncMock()

    await apply_stealth_context(mock_context)

    mock_context.add_init_script.assert_awaited_once_with(STEALTH_INIT_SCRIPT)
    mock_context.set_viewport_size.assert_awaited_once()
    mock_context.set_extra_http_headers.assert_awaited_once()

    call_headers = mock_context.set_extra_http_headers.await_args[0][0]
    assert call_headers["User-Agent"] == DEFAULT_STEALTH_USER_AGENT
    assert "en-IN" in call_headers["Accept-Language"]


# ==============================================================================
# 2. Session Persistence Tests
# ==============================================================================

def test_resolve_user_data_dir(tmp_path):
    target = tmp_path / "custom_browser_profile"
    resolved = resolve_user_data_dir(target)
    assert resolved.exists()
    assert resolved == target.resolve()


# ==============================================================================
# 3. Local Tor SOCKS5 Fallback Integration Tests
# ==============================================================================

def test_http_result_defaults():
    res = HTTPResult(status_code=200, text="OK")
    assert res.is_success is True
    assert res.routed_via == "direct"
    # Test unpacking compatibility
    status, body = res
    assert status == 200
    assert body == "OK"


def test_is_tor_proxy_available_closed_port():
    # Pointing to an unbound loopback port should return False without raising
    is_available = is_tor_proxy_available("socks5://127.0.0.1:59999")
    assert is_available is False


@pytest.mark.asyncio
async def test_resilient_fetch_direct_success():
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "Job Listings Page"
        mock_resp.headers = {"content-type": "text/html"}
        mock_get.return_value = mock_resp

        result = await resilient_fetch("https://example.com/jobs")
        assert result.is_success is True
        assert result.routed_via == "direct"
        assert result.text == "Job Listings Page"


@pytest.mark.asyncio
async def test_resilient_fetch_tor_fallback_on_403():
    with patch("httpx.AsyncClient.get") as mock_get, \
         patch("app.utils.http_client.is_tor_proxy_available", return_value=True), \
         patch("app.utils.http_client.fetch_via_tor_proxy") as mock_tor_fetch:

        # Direct connection returns 403 Cloudflare block
        mock_direct_resp = MagicMock()
        mock_direct_resp.status_code = 403
        mock_direct_resp.text = "Blocked by Cloudflare"
        mock_direct_resp.headers = {}
        mock_get.return_value = mock_direct_resp

        # Tor proxy fallback returns 200 OK
        mock_tor_fetch.return_value = HTTPResult(
            status_code=200,
            text="Unblocked via Tor",
            headers={"content-type": "text/html"},
            routed_via="tor",
        )

        result = await resilient_fetch("https://example.com/blocked-page")
        assert result.status_code == 200
        assert result.routed_via == "tor"
        assert result.text == "Unblocked via Tor"
        mock_tor_fetch.assert_awaited_once()


# ==============================================================================
# 4. JSON-LD Structural Metadata Extraction Tests
# ==============================================================================

SAMPLE_HTML_WITH_JSON_LD = """
<!DOCTYPE html>
<html>
<head>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "JobPosting",
  "title": "Senior Backend Engineer (Python / FastAPI)",
  "hiringOrganization": {
    "@type": "Organization",
    "name": "Acme Global Tech"
  },
  "description": "<p>We are looking for a skilled <strong>FastAPI</strong> developer with PostgreSQL experience.</p>",
  "datePosted": "2026-09-05T10:00:00Z",
  "validThrough": "2026-10-05T00:00:00Z",
  "employmentType": "FULL_TIME",
  "jobLocationType": "TELECOMMUTE",
  "jobLocation": {
    "@type": "Place",
    "address": {
      "addressLocality": "Bengaluru",
      "addressRegion": "Karnataka",
      "addressCountry": "India"
    }
  },
  "baseSalary": {
    "@type": "MonetaryAmount",
    "currency": "INR",
    "value": {
      "@type": "QuantitativeValue",
      "minValue": 1800000,
      "maxValue": 2800000,
      "unitText": "YEAR"
    }
  },
  "skills": ["Python", "FastAPI", "Docker", "PostgreSQL"]
}
</script>
</head>
<body>
  <div class="fragile-css-class">Fallback content</div>
</body>
</html>
"""

def test_extract_json_ld_blocks():
    blocks = extract_json_ld_blocks(SAMPLE_HTML_WITH_JSON_LD)
    assert len(blocks) == 1
    assert blocks[0]["@type"] == "JobPosting"
    assert blocks[0]["title"] == "Senior Backend Engineer (Python / FastAPI)"


def test_extract_json_ld_graph():
    graph_html = """
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@graph": [
        {"@type": "WebSite", "name": "Company Portal"},
        {"@type": "JobPosting", "title": "AI Research Intern", "hiringOrganization": {"name": "DeepAI"}}
      ]
    }
    </script>
    """
    blocks = extract_json_ld_blocks(graph_html)
    assert len(blocks) == 2
    job = extract_job_posting_ld(graph_html)
    assert job is not None
    assert job["title"] == "AI Research Intern"
    assert job["company_name"] == "DeepAI"


def test_extract_job_posting_ld():
    data = extract_job_posting_ld(SAMPLE_HTML_WITH_JSON_LD)
    assert data is not None
    assert data["title"] == "Senior Backend Engineer (Python / FastAPI)"
    assert data["company_name"] == "Acme Global Tech"
    assert "FastAPI developer" in data["description"]
    assert "<p>" not in data["description"]  # HTML stripped
    assert data["remote_type"] == "REMOTE"
    assert "Bengaluru" in data["location"]
    assert data["salary_min"] == 1800000.0
    assert data["salary_max"] == 2800000.0
    assert data["salary_currency"] == "INR"
    assert "Python" in data["skills"]


def test_parse_job_with_fallback_uses_json_ld_first():
    fallback_called = False

    def css_fallback(html: str):
        nonlocal fallback_called
        fallback_called = True
        return {"title": "CSS Extracted Title"}

    job, source = parse_job_with_fallback(SAMPLE_HTML_WITH_JSON_LD, css_fallback)
    assert source == "JSON_LD"
    assert job is not None
    assert job["title"] == "Senior Backend Engineer (Python / FastAPI)"
    assert fallback_called is False  # CSS parser was not needed


def test_parse_job_with_fallback_uses_css_when_no_json_ld():
    html_without_ld = "<html><body><div class='job-title'>Frontend Engineer</div></body></html>"

    def css_fallback(html: str):
        return {"title": "Frontend Engineer", "company_name": "Startup Inc"}

    job, source = parse_job_with_fallback(html_without_ld, css_fallback)
    assert source == "CSS_SELECTOR"
    assert job is not None
    assert job["title"] == "Frontend Engineer"
    assert job["company_name"] == "Startup Inc"
