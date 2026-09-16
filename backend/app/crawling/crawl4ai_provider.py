import asyncio
import os
from pathlib import Path
import time
from typing import Any
import structlog

from app.config import settings
from app.crawling.crawler_models import CrawlRequest, CrawlResult, ExtractionRequest, ExtractionResult
from app.crawling.crawler_provider import CrawlerProvider

# Ensure Crawl4AI stores cache/db in app data directory rather than failing on root ~/.crawl4ai
if "CRAWL4_AI_BASE_DIRECTORY" not in os.environ:
    data_dir = Path(__file__).resolve().parent.parent / "data"
    os.environ["CRAWL4_AI_BASE_DIRECTORY"] = str(data_dir)

logger = structlog.get_logger(__name__)


class Crawl4AICrawlerProvider(CrawlerProvider):
    """
    Concrete implementation of CrawlerProvider backed by Crawl4AI.
    Provides managed browser contexts, stealth execution, structured CSS/schema
    extraction, concurrency bounding, and isolated failure handling.
    """

    def __init__(
        self,
        max_concurrency: int | None = None,
        timeout: float | None = None,
        headless: bool | None = None,
    ):
        self.max_concurrency = max_concurrency or getattr(settings, "CRAWL4AI_MAX_CONCURRENCY", 3)
        self.timeout = timeout or getattr(settings, "CRAWL4AI_TIMEOUT", 20.0)
        self.headless = headless if headless is not None else getattr(settings, "CRAWL4AI_HEADLESS", True)
        self._semaphore = asyncio.Semaphore(self.max_concurrency)

    async def fetch(self, request: CrawlRequest) -> CrawlResult:
        start_time = time.monotonic()
        async with self._semaphore:
            try:
                from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

                cache_mode_map = {
                    "BYPASS": CacheMode.BYPASS,
                    "ENABLED": CacheMode.ENABLED,
                    "READ_ONLY": CacheMode.READ_ONLY,
                }
                c_mode = cache_mode_map.get(request.cache_mode.upper(), CacheMode.BYPASS)

                source_hint = "default"
                if "linkedin.com" in request.url:
                    source_hint = "linkedin"
                elif "naukri.com" in request.url:
                    source_hint = "naukri"
                elif "internshala.com" in request.url:
                    source_hint = "internshala"

                # Load guest cookies if available
                from app.crawling.guest_session_manager import get_guest_session_manager
                guest_mgr = get_guest_session_manager(source_hint)
                guest_cookies = guest_mgr.load_cached_cookies()

                browser_conf = BrowserConfig(
                    headless=self.headless,
                    viewport_width=1440,
                    viewport_height=900,
                    text_mode=False,
                    light_mode=False,
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                    ),
                    headers={
                        "Accept-Language": "en-US,en;q=0.9",
                        "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
                        "Sec-Ch-Ua-Mobile": "?0",
                        "Sec-Ch-Ua-Platform": '"macOS"',
                    },
                )

                # Stealth evasion JS to remove webdriver flags & mock plugins
                stealth_js = (
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                    "window.chrome = { runtime: {} };"
                    "Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});"
                )
                effective_js = f"{stealth_js}\n{request.js_code}" if request.js_code else stealth_js

                run_conf = CrawlerRunConfig(
                    cache_mode=c_mode,
                    wait_for=request.wait_for,
                    js_code=effective_js,
                    css_selector=request.css_selector,
                    page_timeout=int(request.timeout * 1000),
                )

                async with AsyncWebCrawler(config=browser_conf) as crawler:
                    res = await asyncio.wait_for(
                        crawler.arun(url=request.url, config=run_conf),
                        timeout=request.timeout,
                    )
                    duration = time.monotonic() - start_time

                    if res.success:
                        return CrawlResult(
                            url=request.url,
                            status_code=getattr(res, "status_code", 200) or 200,
                            success=True,
                            html=res.html or "",
                            cleaned_html=res.cleaned_html or "",
                            markdown=res.markdown or "",
                            duration_sec=duration,
                            metadata=request.metadata,
                        )
                    else:
                        logger.warning("crawl4ai_fetch_failed", url=request.url, error=res.error_message)
                        return CrawlResult(
                            url=request.url,
                            status_code=getattr(res, "status_code", 500) or 500,
                            success=False,
                            error_message=res.error_message or "Unknown crawler error",
                            duration_sec=duration,
                            metadata=request.metadata,
                        )

            except asyncio.TimeoutError:
                duration = time.monotonic() - start_time
                logger.warning("crawl4ai_fetch_timeout", url=request.url, timeout=request.timeout)
                return CrawlResult(
                    url=request.url,
                    status_code=408,
                    success=False,
                    error_message=f"Timeout after {request.timeout}s",
                    duration_sec=duration,
                    metadata=request.metadata,
                )
            except Exception as e:
                duration = time.monotonic() - start_time
                logger.error("crawl4ai_fetch_exception", url=request.url, error=str(e))
                return CrawlResult(
                    url=request.url,
                    status_code=500,
                    success=False,
                    error_message=str(e),
                    duration_sec=duration,
                    metadata=request.metadata,
                )

    async def extract(self, request: ExtractionRequest) -> ExtractionResult:
        """Extract structured fields using Crawl4AI's JsonCssExtractionStrategy."""
        async with self._semaphore:
            try:
                from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
                from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
                import json

                strategy = None
                if request.schema_definition:
                    strategy = JsonCssExtractionStrategy(request.schema_definition)

                browser_conf = BrowserConfig(
                    headless=self.headless,
                    viewport_width=1280,
                    viewport_height=800,
                )

                run_conf = CrawlerRunConfig(
                    cache_mode=CacheMode.BYPASS,
                    extraction_strategy=strategy,
                    css_selector=request.css_selector,
                    page_timeout=int(request.timeout * 1000),
                )

                async with AsyncWebCrawler(config=browser_conf) as crawler:
                    if request.url:
                        res = await asyncio.wait_for(
                            crawler.arun(url=request.url, config=run_conf),
                            timeout=request.timeout + 5.0,
                        )
                    else:
                        # Direct HTML extraction
                        return ExtractionResult(
                            success=False,
                            error_message="Direct HTML extraction without URL not supported yet",
                        )

                    if res.success:
                        extracted_data: list[dict[str, Any]] = []
                        if res.extracted_content:
                            try:
                                parsed = json.loads(res.extracted_content)
                                if isinstance(parsed, list):
                                    extracted_data = parsed
                                elif isinstance(parsed, dict):
                                    extracted_data = [parsed]
                            except Exception:
                                extracted_data = [{"raw_content": res.extracted_content}]

                        return ExtractionResult(
                            success=True,
                            data=extracted_data,
                            raw_markdown=res.markdown or "",
                        )
                    else:
                        return ExtractionResult(
                            success=False,
                            error_message=res.error_message or "Extraction failed",
                        )

            except Exception as e:
                logger.error("crawl4ai_extract_exception", error=str(e))
                return ExtractionResult(
                    success=False,
                    error_message=str(e),
                )

    async def health_check(self) -> bool:
        # Lightweight deterministic probe: dependency import + config build.
        # No network crawl, no fragile raw: URL. Full browser readiness is
        # proven on first real fetch, not here.
        try:
            from crawl4ai import BrowserConfig

            BrowserConfig(headless=True)
            return True
        except Exception as e:
            logger.warning("crawl4ai_health_check_failed", error=str(e))
            return False
