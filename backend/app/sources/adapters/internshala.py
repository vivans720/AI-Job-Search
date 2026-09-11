import asyncio
import hashlib
import os
import random
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import httpx
import structlog

from app.config import settings as default_settings
from app.services.dedup_service import compute_job_hash
from app.services.freshness_service import get_freshness_service
from app.sources.base import JobSearchQuery, JobSource, NormalizedJob, RawJob
from app.sources.errors import RateLimitBlockError, TransientNetworkError, classify_error
from app.sources.rate_limiter import get_source_rate_limiter
from app.utils.browser_context import resolve_user_data_dir, persistent_browser_session
from app.utils.browser_stealth import (
    DEFAULT_STEALTH_USER_AGENT,
    apply_stealth_context,
    configure_resource_filters,
)
from app.utils.normalization import (
    CANONICAL_SKILLS,
    categorize_role,
    extract_skills_from_text,
    normalize_location,
    normalize_skills,
    normalize_title,
    parse_experience_requirement,
    parse_salary_text,
)
from app.utils.validation import validate_normalized_job
from app.crawling.crawler_registry import get_crawler_provider
from app.crawling.crawler_models import CrawlRequest

logger = structlog.get_logger("job_agent.internshala_adapter")

BASE_URL = "https://internshala.com"

ROLE_EXPANSION = {
    "ai": ["ai", "machine learning", "ml", "genai", "llm", "deep learning", "nlp", "artificial intelligence"],
    "ml": ["machine learning", "ml", "data science"],
    "python": ["python", "django", "fastapi", "flask"],
    "full stack": ["full stack", "full-stack", "mern", "web development", "software engineer"],
    "backend": ["backend", "api developer", "platform engineer", "sde", "node", "express"],
    "frontend": ["frontend", "react", "next.js", "javascript", "typescript", "ui developer"],
}

# Skill-to-category mapping for tech skills
SKILL_TO_JOB_CATEGORIES = {
    "python": ["/jobs/python-django-jobs/"],
    "django": ["/jobs/python-django-jobs/"],
    "javascript": ["/jobs/front-end-development-jobs/", "/jobs/full-stack-development-jobs/"],
    "js": ["/jobs/front-end-development-jobs/", "/jobs/full-stack-development-jobs/"],
    "typescript": ["/jobs/front-end-development-jobs/", "/jobs/full-stack-development-jobs/"],
    "ts": ["/jobs/front-end-development-jobs/", "/jobs/full-stack-development-jobs/"],
    "react": ["/jobs/front-end-development-jobs/", "/jobs/full-stack-development-jobs/"],
    "react.js": ["/jobs/front-end-development-jobs/", "/jobs/full-stack-development-jobs/"],
    "reactjs": ["/jobs/front-end-development-jobs/", "/jobs/full-stack-development-jobs/"],
    "node.js": ["/jobs/backend-development-jobs/", "/jobs/full-stack-development-jobs/"],
    "nodejs": ["/jobs/backend-development-jobs/", "/jobs/full-stack-development-jobs/"],
    "node": ["/jobs/backend-development-jobs/", "/jobs/full-stack-development-jobs/"],
}

SKILL_TO_INTERNSHIP_CATEGORIES = {
    "python": ["/internships/python-django-internship/"],
    "django": ["/internships/python-django-internship/"],
    "javascript": ["/internships/front-end-development-internship/", "/internships/full-stack-development-internship/"],
    "js": ["/internships/front-end-development-internship/", "/internships/full-stack-development-internship/"],
    "typescript": ["/internships/front-end-development-internship/", "/internships/full-stack-development-internship/"],
    "ts": ["/internships/front-end-development-internship/", "/internships/full-stack-development-internship/"],
    "react": ["/internships/front-end-development-internship/", "/internships/full-stack-development-internship/"],
    "react.js": ["/internships/front-end-development-internship/", "/internships/full-stack-development-internship/"],
    "reactjs": ["/internships/front-end-development-internship/", "/internships/full-stack-development-internship/"],
    "node.js": ["/internships/backend-development-internship/", "/internships/full-stack-development-internship/"],
    "nodejs": ["/internships/backend-development-internship/", "/internships/full-stack-development-internship/"],
    "node": ["/internships/backend-development-internship/", "/internships/full-stack-development-internship/"],
}

# Category mapping for high-relevance tech jobs
JOB_CATEGORY_MAP = {
    "ai": "/jobs/artificial-intelligence-ai-jobs/",
    "artificial intelligence": "/jobs/artificial-intelligence-ai-jobs/",
    "ml": "/jobs/machine-learning-jobs/",
    "machine learning": "/jobs/machine-learning-jobs/",
    "python": "/jobs/python-django-jobs/",
    "django": "/jobs/python-django-jobs/",
    "full stack": "/jobs/full-stack-development-jobs/",
    "fullstack": "/jobs/full-stack-development-jobs/",
    "backend": "/jobs/backend-development-jobs/",
    "frontend": "/jobs/front-end-development-jobs/",
    "front end": "/jobs/front-end-development-jobs/",
    "software": "/jobs/computer-science-jobs/",
    "computer science": "/jobs/computer-science-jobs/",
    "cs": "/jobs/computer-science-jobs/",
}

# Category mapping for high-relevance tech internships
INTERNSHIP_CATEGORY_MAP = {
    "software": "/internships/software-development-internship/",
    "cs": "/internships/computer-science-internship/",
    "computer science": "/internships/computer-science-internship/",
    "python": "/internships/python-django-internship/",
    "django": "/internships/python-django-internship/",
    "backend": "/internships/backend-development-internship/",
    "full stack": "/internships/full-stack-development-internship/",
    "fullstack": "/internships/full-stack-development-internship/",
    "ai": "/internships/artificial-intelligence-ai-internship/",
    "genai": "/internships/artificial-intelligence-ai-internship/",
    "ml": "/internships/machine-learning-internship/",
    "machine learning": "/internships/machine-learning-internship/",
    "frontend": "/internships/front-end-development-internship/",
    "front end": "/internships/front-end-development-internship/",
    "data science": "/internships/data-science-internship/",
}

CATEGORY_URL_MAP = JOB_CATEGORY_MAP

DEFAULT_JOB_PATHS = [
    "/jobs/computer-science-jobs/",
    "/jobs/backend-development-jobs/",
    "/jobs/full-stack-development-jobs/",
    "/jobs/python-django-jobs/",
    "/jobs/artificial-intelligence-ai-jobs/",
    "/jobs/machine-learning-jobs/",
    "/jobs/front-end-development-jobs/",
]

DEFAULT_INTERNSHIP_PATHS = [
    "/internships/software-development-internship/",
    "/internships/computer-science-internship/",
    "/internships/backend-development-internship/",
    "/internships/full-stack-development-internship/",
    "/internships/python-django-internship/",
    "/internships/artificial-intelligence-ai-internship/",
    "/internships/machine-learning-internship/",
    "/internships/front-end-development-internship/",
    "/internships/data-science-internship/",
]

DEFAULT_TECH_PATHS = DEFAULT_JOB_PATHS

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/128.0.0.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Centralized CSS selectors for Internshala HTML cards
INTERNSHALA_SELECTORS = {
    "card": "div.individual_internship",
    "title": [".job-title-href", ".profile h3 a", "h3.heading_4_5 a", ".profile", "h3"],
    "company": [".company-name", ".company_name", ".link_display_like_text"],
    "location": [".locations", "#location_names", ".location_link"],
    "salary": [".desktop", ".stipend", ".salary"],
    "status": [".status-info", ".status-container", ".posted-info", ".detail-row-2"],
    "description": [".job-description", ".description_container", ".about_job", ".text"],
    "calendar_icon": ".ic-16-calendar",
    "briefcase_icon": ".ic-16-briefcase",
    "row_item": ".row-1-item",
}


def is_senior_title(title: str) -> bool:
    """Detects whether a title indicates a senior or leadership position."""
    if not title:
        return False
    t = title.lower()

    has_junior = bool(re.search(r"\b(junior|jr|jr\.|trainee|intern|internship|fresher|entry|graduate)\b", t))
    has_senior = bool(
        re.search(
            r"\b(senior|sr|sr\.|lead|staff|principal|architect|manager|director|head|cto|vp|vice president)\b",
            t,
        )
    )

    if has_junior and not has_senior:
        return False
    if has_senior and not has_junior:
        return True
    if has_senior and has_junior:
        return False

    return False


class InternshalaAdapter(JobSource):
    source_name: str = "internshala"
    enabled: bool = True

    def __init__(self, settings: Any = None, timeout: float = 12.0):
        super().__init__()
        self.settings = settings or default_settings
        self.timeout = timeout
        self.enabled = getattr(self.settings, "SOURCE_INTERNSHALA_ENABLED", True)
        self.freshness_service = get_freshness_service()
        self.last_yield_metrics: dict[str, Any] = {}
        self.last_category_metrics: dict[str, dict[str, Any]] = {}
        self._crawler_provider: Any | None = None
        self._freshness_hours: int = 24  # Updated dynamically by search()

        # Adapter-level fast-fail state for anti-bot / account-hold walls
        self._blocked_state: str | None = None
        self.status: str = "ok"
        self.last_error: str | None = None

    async def health_check(self) -> bool:
        if self.status == "blocked":
            return False
        try:
            async with httpx.AsyncClient(headers=HEADERS, timeout=5.0) as client:
                res = await client.head(f"{BASE_URL}/jobs/", follow_redirects=True)
                return res.status_code in (200, 301, 302)
        except Exception as e:
            logger.warning("internshala_health_check_failed", error=str(e))
            return False

    def _get_crawler_provider(self) -> Any | None:
        if self._crawler_provider is not None:
            return self._crawler_provider
        try:
            self._crawler_provider = get_crawler_provider()
            return self._crawler_provider
        except Exception:
            return None

    async def _fetch_via_crawl4ai(self, target_url: str, timeout: float = 20.0) -> str | None:
        provider = self._get_crawler_provider()
        if provider is None or type(provider).__name__ == "NoOpCrawlerProvider":
            return None
        try:
            result = await asyncio.wait_for(
                provider.fetch(CrawlRequest(
                    url=target_url,
                    timeout=timeout,
                    wait_for="div.individual_internship, div.internship_meta, .job-title-href",
                    cache_mode="BYPASS",
                    metadata={"source": "internshala"},
                )),
                timeout=timeout + 5.0,
            )
            if result and result.success and result.html:
                logger.info("internshala_crawl4ai_fetch_completed", url=target_url, html_len=len(result.html))
                return result.html
            logger.warning("internshala_crawl4ai_fetch_failed", url=target_url, error=result.error_message if result else "no result")
            return None
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("internshala_crawl4ai_fetch_exception", url=target_url, error=str(e))
            return None

    def _determine_search_paths(self, query: JobSearchQuery | list | str | None = None) -> list[str]:
        roles: list[str] = []
        skills: list[str] = []
        q: str = ""
        include_jobs: bool = True
        include_internships: bool = True

        if isinstance(query, list):
            skills = [str(r).lower().strip() for r in query]
        elif isinstance(query, str):
            q = query.lower().strip()
        elif isinstance(query, JobSearchQuery):
            q = (query.query or "").lower().strip()
            roles = [r.lower().strip() for r in (query.roles or [])]
            skills = [s.lower().strip() for s in (query.skills or [])]
            include_jobs = getattr(query, "include_jobs", True)
            include_internships = getattr(query, "include_internships", True)

        job_paths: list[str] = []
        internship_paths: list[str] = []

        # 1. First priority: Skills mapping
        if skills:
            for s in skills:
                if include_jobs and s in SKILL_TO_JOB_CATEGORIES:
                    for p in SKILL_TO_JOB_CATEGORIES[s]:
                        if p not in job_paths:
                            job_paths.append(p)
                if include_internships and s in SKILL_TO_INTERNSHIP_CATEGORIES:
                    for p in SKILL_TO_INTERNSHIP_CATEGORIES[s]:
                        if p not in internship_paths:
                            internship_paths.append(p)
            # Retain core broad categories to catch description-only skill jobs
            if include_jobs:
                for core_p in ("/jobs/computer-science-jobs/", "/jobs/full-stack-development-jobs/"):
                    if core_p not in job_paths:
                        job_paths.append(core_p)
            if include_internships:
                for core_p in ("/internships/software-development-internship/", "/internships/computer-science-internship/"):
                    if core_p not in internship_paths:
                        internship_paths.append(core_p)

        combined = f"{q} {' '.join(roles)}".strip()
        is_generic = not combined or combined in (
            "software",
            "tech",
            "jobs",
            "internships",
            "it",
            "fresher",
            "engineering",
        )

        if not job_paths and not internship_paths and combined and not is_generic:
            if include_jobs:
                for key, path in JOB_CATEGORY_MAP.items():
                    if key in combined and path not in job_paths:
                        job_paths.append(path)
                for category, synonyms in ROLE_EXPANSION.items():
                    if any(syn in combined for syn in synonyms):
                        cat_path = JOB_CATEGORY_MAP.get(category)
                        if cat_path and cat_path not in job_paths:
                            job_paths.append(cat_path)

            if include_internships:
                for key, path in INTERNSHIP_CATEGORY_MAP.items():
                    if key in combined and path not in internship_paths:
                        internship_paths.append(path)
                for category, synonyms in ROLE_EXPANSION.items():
                    if any(syn in combined for syn in synonyms):
                        cat_path = INTERNSHIP_CATEGORY_MAP.get(category)
                        if cat_path and cat_path not in internship_paths:
                            internship_paths.append(cat_path)

        if include_jobs and not job_paths:
            job_paths = list(DEFAULT_JOB_PATHS)
        if include_internships and not internship_paths:
            internship_paths = list(DEFAULT_INTERNSHIP_PATHS)

        all_paths: list[str] = []
        if include_jobs:
            all_paths.extend(job_paths)
        if include_internships:
            all_paths.extend(internship_paths)

        return all_paths

    async def _fetch_url(self, target_url: str, max_attempts: int = 3) -> str | None:
        """Automated text/HTTP fallback gate using resilient HTTP client with rate limiting and metrics."""
        from app.utils.http_client import resilient_fetch

        limiter = get_source_rate_limiter(self.source_name)
        await limiter.acquire()
        self._metrics.requests_count += 1

        try:
            result = await resilient_fetch(
                target_url,
                headers=HEADERS,
                timeout=self.timeout,
                max_retries=max_attempts,
                caller_tag="internshala_adapter",
            )
            self._metrics.retries_count += getattr(result, "retry_count", 0)
            if result.status_code in (403, 429) or result.is_blocked:
                self.status = "blocked"
                self.last_error = f"HTTP {result.status_code} - blocked by Internshala perimeter"
                self.last_error_category = "rate_limit_block"
                self._metrics.status = "blocked"
                self._metrics.last_error = self.last_error
                self._metrics.last_error_category = self.last_error_category
            elif result.is_success:
                self.status = "ok"
                self._metrics.status = "ok"
            return result.text if result.is_success else None
        except Exception as exc:
            classified = classify_error(exc, self.source_name)
            self.last_error = classified.message
            self.last_error_category = classified.category.value
            self.status = "degraded" if classified.retryable else "failed"
            self._metrics.status = self.status
            self._metrics.last_error = self.last_error
            self._metrics.last_error_category = self.last_error_category
            logger.warning("internshala_fetch_exception", error=str(exc), category=classified.category.value)
            return None

    def detect_internshala_block_state(self, html: str) -> str | None:
        """Detects likely Internshala block/verify pages from HTML.

        Pure helper: no network/browser, safe to unit test.
        """
        if not html:
            return None

        content_lower = html.lower()

        # If page contains valid job/internship listing cards, it is NOT blocked
        has_cards = any(
            marker in content_lower
            for marker in (
                "individual_internship",
                "internship_meta",
                "internship_list_container",
                "job-card-wrapper",
            )
        )
        if has_cards:
            return None

        # Defend against active challenge/captcha pages
        for token in (
            "cf-browser-verification",
            "turnstile",
            "verify you are human",
            "are you human",
            "robot check",
            "unusual traffic",
            "access denied",
        ):
            if token in content_lower:
                return "VERIFY_OR_CAPTCHA"

        # Account hold / violation checks (only when no listing cards present, and not inside modal templates)
        clean_html = re.sub(r'<div[^>]*id=["\']modal_email["\'][^>]*>.*?</div>', '', content_lower, flags=re.DOTALL)

        if (
            "account is put on hold" in clean_html
            or ("account has been" in clean_html and "hold" in clean_html)
            or "account hold" in clean_html
            or "put on hold" in clean_html
        ):
            return "ACCOUNT_HOLD"

        if "violation of internshala" in clean_html and "rules" in clean_html:
            return "RULE_VIOLATION"

        if "captcha" in clean_html or "enable javascript" in clean_html:
            return "VERIFY_OR_CAPTCHA"

        return None

    async def _fetch_via_browser(self, target_url: str, timeout: float | None = None) -> str | None:
        """Fetches the URL via a persisted Playwright browser session."""
        effective_timeout = timeout if timeout is not None else self.timeout
        try:
            async with persistent_browser_session(
                user_data_dir=getattr(self.settings, "BROWSER_USER_DATA_DIR", None),
                headless=getattr(self.settings, "BROWSER_HEADLESS", True),
                enable_stealth=True,
                block_heavy_resources=True,
            ) as context:
                page = context.pages[0] if context.pages else await context.new_page()

                logger.info(
                    "internshala_browser_navigating",
                    url=target_url,
                )

                try:
                    await page.goto(target_url, wait_until="networkidle", timeout=int(effective_timeout * 1000))
                except Exception:
                    await page.goto(target_url, wait_until="domcontentloaded", timeout=int(effective_timeout * 1000))

                page_content = await page.content()

                block_state = self.detect_internshala_block_state(page_content)
                if block_state in {"ACCOUNT_HOLD", "RULE_VIOLATION", "VERIFY_OR_CAPTCHA"}:
                    logger.error(
                        "internshala_block_detected",
                        url=target_url,
                        block_state=block_state,
                    )
                    return block_state

                return page_content
        except Exception as e:
            logger.warning("internshala_playwright_failed", error=str(e), url=target_url)
            return None

    async def _fetch_page(self, target_url: str) -> str | None:
        """Retrieves listing HTML using HTTP-first, Crawl4AI rendered, browser fallback.

        If a block/verify wall is detected in either channel, we return None
        and set adapter-level blocked state so the caller can fail fast.
        """
        # 1) HTTP-first
        html = await self._fetch_url(target_url)
        if html:
            block_state = self.detect_internshala_block_state(html)
            if block_state in {"ACCOUNT_HOLD", "RULE_VIOLATION", "VERIFY_OR_CAPTCHA"}:
                self._blocked_state = block_state
                self.status = "blocked"
                self.last_error = f"Internshala perimeter hold: {block_state}"
                return None

            # Only trust HTML that looks like a listings page.
            if self._is_likely_card_html(html) and len(html) > 500:
                return html

        # 2) Crawl4AI rendered (primary rendered path)
        logger.info("internshala_crawl4ai_fetch_started", url=target_url)
        html = await self._fetch_via_crawl4ai(target_url)
        if html:
            block_state = self.detect_internshala_block_state(html)
            if block_state in {"ACCOUNT_HOLD", "RULE_VIOLATION", "VERIFY_OR_CAPTCHA"}:
                self._blocked_state = block_state
                self.status = "blocked"
                self.last_error = f"Internshala perimeter hold: {block_state}"
                return None
            if self._is_likely_card_html(html) and len(html) > 500:
                return html

        # 3) Browser fallback (legacy Playwright)
        logger.info("internshala_crawl4ai_fallback_activated", url=target_url, reason="crawl4ai_unavailable_or_no_cards")
        html = await self._fetch_via_browser(target_url)
        if html in {"ACCOUNT_HOLD", "RULE_VIOLATION", "VERIFY_OR_CAPTCHA"}:
            self._blocked_state = html
            self.status = "blocked"
            self.last_error = f"Internshala perimeter hold: {html}"
            return None
        if html and len(html) > 500:
            return html

        return None

    async def search(self, query: JobSearchQuery, max_pages_per_category: int = 2) -> list[RawJob]:
        """
        Multi-category and paginated search across Internshala tech listings.
        """
        if not self.enabled:
            logger.info("Internshala Adapter is disabled via configuration settings.")
            return []

        paths = self._determine_search_paths(query)
        self._freshness_hours = query.freshness_hours or 24
        logger.info("internshala_search_started", paths=paths, max_pages=max_pages_per_category, freshness_hours=self._freshness_hours)

        # Reset adapter-level block state for this run
        self._blocked_state = None

        all_raw_jobs: list[RawJob] = []
        seen_job_ids: set[str] = set()
        category_metrics: dict[str, dict[str, int]] = {}
        jobs_metrics: dict[str, dict[str, int]] = {}
        internships_metrics: dict[str, dict[str, int]] = {}
        consecutive_failures = 0

        limit = getattr(query, "limit", 50) if isinstance(query, JobSearchQuery) else 50
        max_jobs_quota = max(limit, 100)
        max_internships_quota = max(limit, 100)
        jobs_count = 0
        start_time = asyncio.get_event_loop().time()
        try:
            for path in paths:
                is_intern = path.startswith("/internships")
                if not is_intern and jobs_count >= max_jobs_quota:
                    continue
                if is_intern and internships_count >= max_internships_quota:
                    continue

                cat_slug = (
                    path.strip("/")
                    .replace("internships/", "")
                    .replace("jobs/", "")
                    .replace("-internship", "")
                    .replace("-jobs", "")
                )
                cat_discovered = 0
                cat_fresh = 0

                for page in range(1, max_pages_per_category + 1):
                    if page == 1:
                        target_url = urljoin(BASE_URL, path)
                    else:
                        target_url = urljoin(BASE_URL, f"{path.rstrip('/')}/page-{page}/")

                    logger.info("internshala_fetch_page", category=cat_slug, is_intern=is_intern, page=page, url=target_url)
                    html = await self._fetch_page(target_url)
                    if not html:
                        # Fail fast on anti-bot / account-hold walls
                        if self._blocked_state in {"ACCOUNT_HOLD", "RULE_VIOLATION", "VERIFY_OR_CAPTCHA"}:
                            logger.error(
                                "internshala_block_fail_fast_abort",
                                category=cat_slug,
                                is_intern=is_intern,
                                page=page,
                                block_state=self._blocked_state,
                            )
                            return []

                        if page == 1:
                            consecutive_failures += 1
                            if consecutive_failures >= 2:
                                logger.warning("internshala_consecutive_failures_abort", category=cat_slug)
                                break
                            break
                        break

                    consecutive_failures = 0

                    cards = self.parse_html(html)
                    if not cards:
                        break

                    page_fresh = 0
                    for r in cards:
                        # Fetch-time fast freshness filter
                        p_at, conf = None, "LOW"
                        if r.posted_time_raw:
                            p_at, conf = self.freshness_service.parse_recency_string(r.posted_time_raw)

                        ref_now = r.scraped_at or datetime.now(timezone.utc)
                        is_fresh = False
                        if p_at:
                            is_fresh = self.freshness_service.is_fresh(p_at, conf, freshness_hours=self._freshness_hours, reference_now=ref_now)
                        elif r.posted_time_raw and any(kw in r.posted_time_raw.lower() for kw in ("today", "just now", "few hours", "1 day")):
                            is_fresh = True

                        # Discard stale cards immediately: prevents downstream expensive LLM skill extraction
                        if not is_fresh:
                            logger.debug("internshala_fetch_stale_skipped", title=r.title, posted_raw=r.posted_time_raw, cutoff=self._freshness_hours)
                            continue

                        page_fresh += 1
                        dedup_key = r.source_job_id or r.source_url
                        if dedup_key not in seen_job_ids:
                            seen_job_ids.add(dedup_key)
                            all_raw_jobs.append(r)
                            cat_discovered += 1
                            cat_fresh += 1
                            if is_intern:
                                internships_count += 1
                            else:
                                jobs_count += 1

                    if page > 2 and page_fresh == 0:
                        logger.info("internshala_pagination_early_stop", category=cat_slug, page=page, reason="No fresh cards after page 2")
                        break

                    await asyncio.sleep(0.5)

                metric_entry = {
                    "discovered": cat_discovered,
                    "fresh": cat_fresh,
                }
                category_metrics[cat_slug] = metric_entry
                if is_intern:
                    internships_metrics[cat_slug] = metric_entry
                else:
                    jobs_metrics[cat_slug] = metric_entry

                if consecutive_failures >= 2:
                    break
        finally:
            elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000.0
            self._metrics.duration_ms += elapsed_ms
            self._metrics.raw_discovered = len(all_raw_jobs)

        self.last_category_metrics = {
            "all": category_metrics,
            "jobs": jobs_metrics,
            "internships": internships_metrics,
        }
        logger.info(
            "internshala_search_completed",
            total_unique_discovered=len(all_raw_jobs),
            jobs_discovered=sum(m["discovered"] for m in jobs_metrics.values()),
            internships_discovered=sum(m["discovered"] for m in internships_metrics.values()),
        )
        return all_raw_jobs

    def _parse_card_node(self, card) -> RawJob | None:
        """Parses individual card HTML node into RawJob model."""
        def _select_first(element, selectors: list[str] | str):
            if isinstance(selectors, str):
                return element.select_one(selectors)
            for sel in selectors:
                match = element.select_one(sel)
                if match:
                    return match
            return None

        # 1. Title & URL
        title_el = _select_first(card, INTERNSHALA_SELECTORS["title"])
        if not title_el:
            return None
        title = title_el.get_text(strip=True)
        if not title:
            return None

        rel_url = (
            card.get("data-href")
            or (title_el.get("href") if title_el else None)
            or card.get("data-canonical")
            or ""
        )
        if not rel_url or rel_url.rstrip("/") in ("/jobs", "/internships", ""):
            return None
        app_url = urljoin(BASE_URL, rel_url)

        is_internship = "/internship/detail/" in app_url or "/internship" in rel_url

        # 2. Company
        comp_el = _select_first(card, INTERNSHALA_SELECTORS["company"])
        company = comp_el.get_text(strip=True) if comp_el else ""
        if not company or company.lower() in ("company", "confidential", "hiring company"):
            return None

        # 3. Location & Remote
        loc_el = _select_first(card, INTERNSHALA_SELECTORS["location"])
        location = loc_el.get_text(strip=True) if loc_el else "India"
        remote_type = "REMOTE" if ("work from home" in location.lower() or "remote" in location.lower()) else "ONSITE"

        # 4. Salary / Stipend
        salary_el = _select_first(card, INTERNSHALA_SELECTORS["salary"])
        salary_raw = salary_el.get_text(strip=True) if salary_el else None

        # 5. Experience & Duration
        duration_raw = None
        if is_internship:
            employment_type = "INTERNSHIP"
            exp_raw = "Internship (Fresher)"
            cal_el = card.select_one(INTERNSHALA_SELECTORS["calendar_icon"])
            if cal_el and cal_el.parent:
                duration_raw = cal_el.parent.get_text(strip=True)
        else:
            employment_type = "FULL_TIME"
            exp_raw = None
            bc_el = card.select_one(INTERNSHALA_SELECTORS["briefcase_icon"])
            if bc_el and bc_el.parent:
                exp_raw = bc_el.parent.get_text(strip=True)
            else:
                for item in card.select(INTERNSHALA_SELECTORS["row_item"]):
                    txt = item.get_text(strip=True)
                    if "year" in txt.lower() or "experience" in txt.lower() or "fresher" in txt.lower():
                        exp_raw = txt
                        break
            if not exp_raw:
                exp_raw = "0-1 years"

        # 6. Posted Time (separate posting date from duration/start date)
        status_el = _select_first(card, INTERNSHALA_SELECTORS["status"])
        status_text = status_el.get_text(strip=True) if status_el else ""
        status_lower = status_text.lower()
        if any(token in status_lower for token in ["ago", "today", "yesterday", "just now", "posted", "active", "few"]):
            posted_time_raw = status_text
        else:
            posted_time_raw = "Just now"

        # 7. Description
        desc_el = _select_first(card, INTERNSHALA_SELECTORS["description"])
        desc = (
            desc_el.get_text(strip=True)
            if desc_el
            else f"{'Internship' if is_internship else 'Fresher engineering opportunity'} at {company}."
        )

        source_id = card.get("id") or (rel_url.split("-")[-1] if rel_url else str(uuid.uuid4()))

        raw_payload = {
            "internshala_id": source_id,
            "raw_title": title,
            "raw_company": company,
            "raw_location": location,
            "raw_salary": salary_raw,
            "raw_experience": exp_raw,
            "raw_duration": duration_raw,
            "duration": duration_raw,
            "employment_type": employment_type,
            "is_internship": is_internship,
            "is_senior": is_senior_title(title),
            "raw_posted_text": posted_time_raw,
            "source_url": app_url,
            "scraped_at_iso": datetime.now(timezone.utc).isoformat(),
            "dom_card_id": card.get("id"),
        }

        return RawJob(
            source=self.source_name,
            source_job_id=str(source_id),
            title=title,
            company_name=company,
            description=desc,
            location=location,
            remote_type=remote_type,
            employment_type=employment_type,
            experience_raw=exp_raw,
            salary_raw=salary_raw,
            posted_time_raw=posted_time_raw,
            source_url=app_url,
            application_url=app_url,
            raw_payload=raw_payload,
        )

    def parse_html(self, html: str) -> list[RawJob]:
        """
        Pure parser converting Internshala HTML cards into RawJob models
        with full parser observability and field yield tracking.
        """
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(INTERNSHALA_SELECTORS["card"])
        total_cards = len(cards)
        results: list[RawJob] = []

        title_count = 0
        comp_count = 0
        loc_count = 0
        salary_count = 0
        exp_count = 0
        age_count = 0
        url_count = 0

        for card in cards:
            job = self._parse_card_node(card)
            if job:
                results.append(job)
                title_count += 1
                comp_count += 1
                url_count += 1
                if job.location:
                    loc_count += 1
                if job.salary_raw:
                    salary_count += 1
                if job.experience_raw:
                    exp_count += 1
                if job.posted_time_raw:
                    age_count += 1

        if total_cards > 0:
            yield_metrics = {
                "total_cards": total_cards,
                "title_yield": round(title_count / total_cards, 2),
                "company_yield": round(comp_count / total_cards, 2),
                "location_yield": round(loc_count / total_cards, 2),
                "salary_yield": round(salary_count / total_cards, 2),
                "experience_yield": round(exp_count / total_cards, 2),
                "age_yield": round(age_count / total_cards, 2),
                "url_yield": round(url_count / total_cards, 2),
            }
            self.last_yield_metrics = yield_metrics
            logger.info("internshala_parser_yield", **yield_metrics)

            if yield_metrics["title_yield"] < 0.85 or yield_metrics["company_yield"] < 0.85:
                logger.error(
                    "internshala_parser_degraded",
                    warning="Extraction yield below 85% threshold. DOM markup may have shifted.",
                    metrics=yield_metrics,
                )

        return results

    def normalize_job(self, raw: RawJob) -> NormalizedJob | None:
        """
        Normalizes and enforces strict 24-hour freshness on Internshala listings.
        Rescues active timestamps ('Just now', 'Today', 'Active today') into operational timelines.
        """
        if not raw.posted_time_raw:
            return None

        # Rescue vague active counters and relative times
        posted_at, confidence = self.freshness_service.parse_recency_string(raw.posted_time_raw)

        if not posted_at or not self.freshness_service.is_fresh(posted_at, confidence, freshness_hours=self._freshness_hours):
            return None

        # Experience
        if raw.employment_type == "INTERNSHIP":
            exp_min, exp_max, exp_text, exp_conf = 0, 0, "Internship (0 years)", "HIGH"
        else:
            exp_min, exp_max, exp_text, exp_conf = parse_experience_requirement(raw.experience_raw or raw.description)

        # Title & Category
        norm_title, category = normalize_title(raw.title)

        # Location
        norm_loc = normalize_location(raw.location)
        remote_type = "REMOTE" if raw.remote_type == "REMOTE" or "remote" in norm_loc.lower() else "ONSITE"

        # Salary parsing
        sal_dict = parse_salary_text(raw.salary_raw)
        min_sal = sal_dict.get("salary_min")
        max_sal = sal_dict.get("salary_max")

        # Description handling
        desc = (raw.description or "").strip()
        if not desc:
            desc = f"{raw.title} at {raw.company_name}."
        description_confidence = "HIGH" if len(desc) >= 200 else "LOW"

        # Skills extraction
        raw_skills = raw.raw_payload.get("skills", []) if raw.raw_payload else []
        required_skills, preferred_skills = extract_skills_from_text(
            description=desc,
            title=raw.title,
            explicit_skills=raw_skills,
        )

        norm_company = raw.company_name.strip()
        job_hash = compute_job_hash(
            norm_company,
            norm_title,
            norm_loc,
            raw.employment_type or "INTERNSHIP",
            raw.source_job_id,
        )

        quality_score = 75.0

        if raw.salary_raw and "not disclosed" not in raw.salary_raw.lower():
            quality_score += 15.0

        # Prefer detailed descriptions (helps downstream validation & skill extraction)
        desc_len = len(desc)
        if desc_len >= 350:
            quality_score += 10.0
        elif desc_len >= 200:
            quality_score += 5.0

        if confidence == "HIGH":
            quality_score += 10.0

        # Reward skill coverage rather than raw text length alone
        total_skills = len(required_skills) + len(preferred_skills)
        if total_skills >= 3:
            quality_score += 10.0
        elif total_skills >= 1:
            quality_score += 5.0

        # If extraction is uncertain, cap quality a bit
        if (raw.raw_payload or {}).get("skill_extraction_confidence") is not None:
            try:
                ext_conf = float((raw.raw_payload or {}).get("skill_extraction_confidence"))
                if ext_conf < 0.6:
                    quality_score -= 10.0
            except Exception:
                pass

        raw_payload = dict(raw.raw_payload or {})
        raw_payload.setdefault("skill_extraction_method", "deterministic")
        raw_payload.setdefault("skill_extraction_confidence", 0.95 if (required_skills or preferred_skills) else 0.5)
        raw_payload["experience_text"] = exp_text
        raw_payload["experience_confidence"] = exp_conf
        raw_payload["description_confidence"] = description_confidence

        return NormalizedJob(
            source=self.source_name,
            source_job_id=raw.source_job_id,
            title=raw.title,
            normalized_title=norm_title,
            company_name=raw.company_name,
            normalized_company=norm_company,
            description=desc,
            role_category=category,
            required_skills=required_skills,
            preferred_skills=preferred_skills,
            experience_min=exp_min,
            experience_max=exp_max,
            experience_text=exp_text,
            experience_confidence=exp_conf,
            description_confidence=description_confidence,
            location=raw.location,
            normalized_location=norm_loc,
            remote_type=remote_type,
            employment_type=raw.employment_type or "FULL_TIME",
            salary_min=min_sal,
            salary_max=max_sal,
            salary_currency="INR",
            posted_at=posted_at,
            posted_at_raw=raw.posted_time_raw,
            posted_at_confidence=confidence,
            source_url=raw.source_url,
            application_url=raw.application_url or raw.source_url,
            job_hash=job_hash,
            quality_score=min(100.0, quality_score),
            raw_data=raw_payload,
        )

    def _is_likely_card_html(self, html: str) -> bool:
        """Heuristic: does HTML look like an Internshala listing page with cards?"""
        if not html:
            return False

        # Core card container
        if "div.individual_internship" in html:
            return True

        # Secondary signals (selector drift tolerant)
        for marker in (
            "job-title-href",
            "company-name",
            "locations",
            "job-description",
            "status-info",
        ):
            if marker in html:
                return True

        return False

    async def get_job(self, url: str) -> RawJob | None:
        """Fetches a specific Internshala listing by URL."""
        try:
            html = await self._fetch_page(url)
            if not html:
                return None
            parsed = self.parse_html(html)
            return parsed[0] if parsed else None
        except Exception as e:
            logger.warning("internshala_get_job_failed", url=url, error=str(e))
            return None

    async def normalize(self, raw: RawJob) -> NormalizedJob | None:
        """Asynchronously normalizes RawJob into NormalizedJob conforming to JobSource ABC."""
        norm = self.normalize_job(raw)
        if norm is None:
            return None

        raw_skills = raw.raw_payload.get("skills", []) if raw.raw_payload else []
        from app.services.skill_extraction_service import get_skill_extraction_service
        extraction = await get_skill_extraction_service().extract_skills(
            description=raw.description or "",
            title=raw.title,
            explicit_skills=raw_skills,
        )

        norm.required_skills = extraction.required_skills
        norm.preferred_skills = extraction.preferred_skills

        raw_data = dict(norm.raw_data or {})
        raw_data["skill_extraction_method"] = extraction.method
        raw_data["skill_extraction_confidence"] = extraction.confidence
        raw_data["skill_extraction_provenance"] = {
            "method": extraction.method,
            "confidence": extraction.confidence,
            "required_count": len(extraction.required_skills),
            "preferred_count": len(extraction.preferred_skills),
        }
        norm.raw_data = raw_data
        return norm
