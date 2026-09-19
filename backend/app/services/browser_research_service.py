import asyncio
import re
from datetime import datetime, timezone
from typing import Any
import httpx
from bs4 import BeautifulSoup
import structlog

logger = structlog.get_logger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


class BrowserResearchService:
    """
    Deep job inspection service for Hermes Agent.
    Navigates to job application/posting URLs to extract comprehensive specifications,
    application requirements, interview rounds, tech stacks, and portal status.
    """

    @staticmethod
    async def inspect_page(
        url: str,
        timeout_seconds: int = 25,
    ) -> dict[str, Any]:
        """
        Fetches and extracts deep insights from a job URL.
        Attempts headless browser execution via Playwright first;
        falls back to HTTP request if Playwright browser is unavailable.
        """
        if not url or not url.startswith(("http://", "https://")):
            return {
                "status": "error",
                "error": f"Invalid URL: {url}",
                "url": url,
            }

        result = await BrowserResearchService._fetch_playwright(url, timeout_seconds)
        if result.get("status") == "ok":
            return result

        logger.info("browser_playwright_failed_falling_back_http", url=url, error=result.get("error"))
        return await BrowserResearchService._fetch_httpx(url, timeout_seconds)

    @staticmethod
    async def _fetch_playwright(url: str, timeout: int) -> dict[str, Any]:
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
                )
                context = await browser.new_context(
                    user_agent=USER_AGENT,
                    viewport={"width": 1280, "height": 800},
                )
                page = await context.new_page()
                response = await page.goto(
                    url,
                    timeout=timeout * 1000,
                    wait_until="domcontentloaded",
                )
                final_url = page.url
                status_code = response.status if response else 200
                html = await page.content()
                title = await page.title()
                await browser.close()

                return BrowserResearchService._parse_content(
                    url=url,
                    final_url=final_url,
                    status_code=status_code,
                    title=title,
                    html=html,
                    engine="playwright",
                )
        except Exception as e:
            return {"status": "error", "error": str(e), "engine": "playwright"}

    @staticmethod
    async def _fetch_httpx(url: str, timeout: int) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                timeout=float(timeout),
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
            ) as client:
                res = await client.get(url)
                soup = BeautifulSoup(res.text, "html.parser")
                title = soup.title.string.strip() if soup.title and soup.title.string else ""
                return BrowserResearchService._parse_content(
                    url=url,
                    final_url=str(res.url),
                    status_code=res.status_code,
                    title=title,
                    html=res.text,
                    engine="httpx",
                )
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "url": url,
                "engine": "httpx",
            }

    @staticmethod
    def _parse_content(
        url: str,
        final_url: str,
        status_code: int,
        title: str,
        html: str,
        engine: str,
    ) -> dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")

        # Remove irrelevant noise tags
        for tag in soup(["script", "style", "noscript", "svg", "header", "footer", "nav"]):
            tag.decompose()

        # Extract structured text
        text_lines = [
            line.strip()
            for line in soup.get_text(separator="\n").splitlines()
            if line.strip()
        ]
        full_text = "\n".join(text_lines)

        # Truncate content for LLM agent context limit
        truncated_text = full_text[:10000]

        # Detect application keywords / forms
        has_apply_form = bool(soup.find("form"))
        is_closed = bool(
            re.search(
                r"(job is closed|no longer accepting applications|position has been filled|this job expired)",
                full_text,
                re.IGNORECASE,
            )
        )

        return {
            "status": "ok",
            "url": url,
            "final_url": final_url,
            "http_status": status_code,
            "page_title": title,
            "is_closed": is_closed,
            "has_apply_form": has_apply_form,
            "extracted_text": truncated_text,
            "char_count": len(truncated_text),
            "researched_at": datetime.now(timezone.utc).isoformat(),
            "engine": engine,
        }
