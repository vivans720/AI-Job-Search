import asyncio
import sys
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

# Mock crawl4ai module in sys.modules if not installed in test environment
if "crawl4ai" not in sys.modules:
    mock_c4a = MagicMock()
    mock_c4a.CacheMode = MagicMock()
    mock_c4a.CacheMode.BYPASS = "BYPASS"
    mock_c4a.CacheMode.ENABLED = "ENABLED"
    mock_c4a.CacheMode.READ_ONLY = "READ_ONLY"
    mock_c4a.BrowserConfig = MagicMock()
    mock_c4a.CrawlerRunConfig = MagicMock()
    mock_c4a.AsyncWebCrawler = MagicMock()
    mock_c4a.extraction_strategy = MagicMock()
    mock_c4a.extraction_strategy.JsonCssExtractionStrategy = MagicMock()
    sys.modules["crawl4ai"] = mock_c4a
    sys.modules["crawl4ai.extraction_strategy"] = mock_c4a.extraction_strategy

from app.crawling.crawler_models import CrawlRequest, CrawlResult, ExtractionRequest, ExtractionResult
from app.crawling.crawler_provider import CrawlerProvider
from app.crawling.crawl4ai_provider import Crawl4AICrawlerProvider
from app.crawling.crawler_registry import get_crawler_provider, reset_crawler_provider


def test_crawler_models():
    req = CrawlRequest(url="https://example.com/jobs/1", timeout=15.0)
    assert req.url == "https://example.com/jobs/1"
    assert req.timeout == 15.0
    assert req.cache_mode == "BYPASS"

    res = CrawlResult(url=req.url, status_code=200, success=True, markdown="# Software Engineer")
    assert res.success is True
    assert "# Software Engineer" in res.markdown


def test_crawler_registry():
    reset_crawler_provider()
    provider = get_crawler_provider()
    assert isinstance(provider, CrawlerProvider)
    assert isinstance(provider, Crawl4AICrawlerProvider)


@pytest.mark.asyncio
async def test_crawl4ai_provider_fetch_mocked():
    provider = Crawl4AICrawlerProvider()

    mock_crawl_result = MagicMock()
    mock_crawl_result.success = True
    mock_crawl_result.status_code = 200
    mock_crawl_result.html = "<html><body><h1>Backend Developer</h1></body></html>"
    mock_crawl_result.cleaned_html = "<h1>Backend Developer</h1>"
    mock_crawl_result.markdown = "# Backend Developer"
    mock_crawl_result.error_message = None

    mock_crawler = AsyncMock()
    mock_crawler.arun.return_value = mock_crawl_result
    mock_crawler.__aenter__.return_value = mock_crawler
    mock_crawler.__aexit__.return_value = None

    with patch("crawl4ai.AsyncWebCrawler", return_value=mock_crawler):
        req = CrawlRequest(url="https://example.com/jobs/dev-1")
        result = await provider.fetch(req)

        assert result.success is True
        assert result.status_code == 200
        assert "Backend Developer" in result.markdown
        assert "Backend Developer" in result.html


@pytest.mark.asyncio
async def test_crawl4ai_provider_timeout_handling():
    provider = Crawl4AICrawlerProvider(timeout=0.1)

    mock_crawler = AsyncMock()
    async def slow_arun(*args, **kwargs):
        await asyncio.sleep(0.5)
        return MagicMock()

    mock_crawler.arun.side_effect = slow_arun
    mock_crawler.__aenter__.return_value = mock_crawler
    mock_crawler.__aexit__.return_value = None

    with patch("crawl4ai.AsyncWebCrawler", return_value=mock_crawler):
        req = CrawlRequest(url="https://example.com/slow", timeout=0.1)
        result = await provider.fetch(req)

        assert result.success is False
        assert result.status_code == 408
        assert "Timeout" in (result.error_message or "")


@pytest.mark.asyncio
async def test_crawl4ai_structured_extraction():
    provider = Crawl4AICrawlerProvider()

    mock_extract_result = MagicMock()
    mock_extract_result.success = True
    mock_extract_result.extracted_content = '[{"title": "Full Stack Intern", "company": "Tech Corp"}]'
    mock_extract_result.markdown = "Full Stack Intern at Tech Corp"

    mock_crawler = AsyncMock()
    mock_crawler.arun.return_value = mock_extract_result
    mock_crawler.__aenter__.return_value = mock_crawler
    mock_crawler.__aexit__.return_value = None

    with patch("crawl4ai.AsyncWebCrawler", return_value=mock_crawler):
        req = ExtractionRequest(
            url="https://example.com/jobs",
            schema_definition={"name": "Jobs", "baseSelector": "div.card"},
        )
        result = await provider.extract(req)

        assert result.success is True
        assert len(result.data) == 1
        assert result.data[0]["title"] == "Full Stack Intern"
        assert result.data[0]["company"] == "Tech Corp"


@pytest.mark.asyncio
async def test_crawl4ai_health_check():
    provider = Crawl4AICrawlerProvider()

    mock_res = MagicMock()
    mock_res.success = True

    mock_crawler = AsyncMock()
    mock_crawler.arun.return_value = mock_res
    mock_crawler.__aenter__.return_value = mock_crawler
    mock_crawler.__aexit__.return_value = None

    with patch("crawl4ai.AsyncWebCrawler", return_value=mock_crawler):
        healthy = await provider.health_check()
        assert healthy is True
