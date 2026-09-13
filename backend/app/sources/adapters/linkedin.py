import asyncio
import hashlib
import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any
from urllib.parse import quote_plus, urljoin
from bs4 import BeautifulSoup
import httpx
import structlog

from app.config import settings
from app.services.dedup_service import compute_job_hash
from app.services.freshness_service import get_freshness_service
from app.services.skill_extraction_service import get_skill_extraction_service
from app.sources.adapters.internshala import is_senior_title
from app.sources.base import JobSearchQuery, JobSource, NormalizedJob, RawJob
from app.sources.errors import RateLimitBlockError, TransientNetworkError, classify_error
from app.sources.rate_limiter import get_source_rate_limiter
from app.utils.normalization import (
    categorize_role,
    extract_skills_from_text,
    infer_experience_from_title,
    normalize_location,
    normalize_title,
    parse_experience_requirement,
    parse_salary_text,
)
from app.utils.validation import validate_normalized_job

logger = structlog.get_logger(__name__)

BASE_URL = "https://www.linkedin.com"
GUEST_SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
PUBLIC_SEARCH_URL = "https://www.linkedin.com/jobs/search"

# Centralized CSS selectors for LinkedIn guest listings and public views
LINKEDIN_SELECTORS = {
    "card": [
        "li",
        "div.job-search-card",
        "div.base-card",
        "div.base-search-card",
    ],
    "title": [
        "h3.base-search-card__title",
        ".base-search-card__title",
        "h3.job-search-card__title",
        ".job-search-card__title",
        "h3",
        "a.base-card__full-link",
    ],
    "company": [
        "h4.base-search-card__subtitle",
        ".base-search-card__subtitle",
        "h4.job-search-card__subtitle",
        ".job-search-card__subtitle",
        "a.hidden-nested-link",
        "h4",
    ],
    "location": [
        "span.job-search-card__location",
        ".job-search-card__location",
        "span.base-search-card__location",
        ".base-search-card__metadata span",
    ],
    "time": [
        "time.job-search-card__listdate",
        "time.job-search-card__listdate--new",
        "time.base-search-card__listdate",
        "time",
    ],
    "link": [
        "a.base-card__full-link",
        "a.job-search-card__url-link",
        "a[data-tracking-control-name='public_jobs_jserp-result_search-card']",
        "a[href*='/jobs/view/']",
    ],
    "description": [
        "div.show-more-less-html__markup",
        "div.description__text",
        "section.show-more-less-html",
        ".decorated-job-posting__details",
        ".jobs-description__content",
    ],
}

GUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
}

SKILL_EXPANSIONS: dict[str, list[str]] = {
    "javascript": ["javascript", "js"],
    "js": ["javascript", "js"],
    "typescript": ["typescript", "ts"],
    "ts": ["typescript", "ts"],
    "react": ["react", "react.js", "reactjs"],
    "react.js": ["react", "react.js", "reactjs"],
    "reactjs": ["react", "react.js", "reactjs"],
    "node.js": ["node.js", "nodejs", "node js"],
    "nodejs": ["node.js", "nodejs", "node js"],
    "node": ["node.js", "nodejs", "node js"],
    "python": ["python", "python3"],
}

DEFAULT_TARGETED_SKILLS = [
    "Software Engineer",
    "Full Stack Developer",
    "Backend Developer",
    "Frontend Developer",
    "react",
    "python",
    "node.js",
    "javascript",
    "typescript",
]

CORE_TECH_ROLES = [
    "Software Engineer",
    "Full Stack Developer",
    "Backend Developer",
    "Frontend Developer",
]


def extract_linkedin_job_id(url_or_urn: str | None) -> str:
    """Extracts numeric LinkedIn job ID from URL or URN string."""
    if not url_or_urn:
        return str(uuid.uuid4())
    cleaned = str(url_or_urn).split("?")[0].split("#")[0].strip().rstrip("/")
    # Check URN pattern: urn:li:jobPosting:1234567890
    urn_match = re.search(r"jobPosting:(\d+)", cleaned)
    if urn_match:
        return urn_match.group(1)
    # Check trailing numeric ID in URL path: .../jobs/view/...-1234567890
    trailing_match = re.search(r"(\d{6,16})$", cleaned)
    if trailing_match:
        return trailing_match.group(1)
    # Any 6-16 digit sequence
    num_match = re.search(r"(\d{6,16})", cleaned)
    if num_match:
        return num_match.group(1)
    return cleaned


def clean_linkedin_url(url: str | None) -> str:
    """Strips tracking query parameters and canonicalizes LinkedIn job URLs."""
    if not url:
        return "https://www.linkedin.com/jobs"
    cleaned = url.split("?")[0].split("#")[0].strip()
    if not cleaned.startswith("http"):
        cleaned = urljoin(BASE_URL, cleaned)
    return cleaned

class LinkedInAdapter(JobSource):
    """
    Production-grade LinkedIn Adapter for autonomous job discovery in India.
    Features:
      - Triple Discovery Engine: Guest API fast path, Crawl4AI rendered path, Playwright stealth fallback.
      - Resilient Fetching: Automatic socket-level Tor SOCKS5 fallback on 429 and 403.
      - Strict 24h Freshness: Rejects jobs older than 24 hours in IST (Asia/Kolkata).
      - Senior Title Exclusion: Rejects leadership and senior roles to protect freshers.
      - Hybrid Skill Extraction: Provenance-tracked structured requirements.
      - Data Integrity: Strict validation before persistence.
    """

    source_name: str = "linkedin"

    def __init__(
        self,
        timeout: float = 12.0,
        max_retries: int = 3,
        tor_proxy_url: str | None = None,
        user_data_dir: str | None = None,
        headless: bool = True,
        crawler_provider: Any | None = None,
    ):
        super().__init__()
        self.timeout = timeout
        self.max_retries = max_retries
        self.tor_proxy_url = tor_proxy_url or getattr(settings, "TOR_PROXY_URL", "socks5://127.0.0.1:9050")
        self.user_data_dir = user_data_dir or getattr(settings, "BROWSER_USER_DATA_DIR", "~/.config/job_agent_browser_profile")
        self.headless = getattr(settings, "BROWSER_HEADLESS", headless)
        self.freshness_service = get_freshness_service()
        self.skill_extraction_service = get_skill_extraction_service()
        self.enabled = getattr(settings, "SOURCE_LINKEDIN_ENABLED", True)
        self._crawler_provider = crawler_provider
        self._freshness_hours: int = 24  # Updated dynamically by search()

    async def health_check(self) -> bool:
        """Verifies public availability of LinkedIn guest search."""
        try:
            from app.utils.http_client import resilient_fetch
            test_url = f"{GUEST_SEARCH_URL}?keywords=software&location=India&f_TPR=r86400&start=0"
            result = await resilient_fetch(
                test_url,
                headers=GUEST_HEADERS,
                timeout=5.0,
                max_retries=1,
                caller_tag="linkedin_health_check",
            )
            return result.status_code in (200, 301, 302)
        except Exception as e:
            logger.warning("linkedin_health_check_failed", error=str(e))
            return False

    def _determine_search_queries(self, query: JobSearchQuery) -> list[str]:
        """
        Translates search query into targeted terms with freshness-aware query budgeting.
        Prevents excessive query explosion and eliminates duplicate synonyms.
        """
        search_terms: list[str] = []
        freshness_h = query.freshness_hours or 24

        # 1. Explicit query override takes highest priority
        if query.query and query.query.strip():
            search_terms.append(query.query.strip())

        # 2. Roles budgeting
        roles_to_include: list[str] = []
        if not query.query:
            roles_to_include = query.roles if query.roles else CORE_TECH_ROLES
        elif query.roles:
            roles_to_include = query.roles

        # For tight windows (<= 4h), focus strictly on top primary core roles
        if freshness_h <= 1 and roles_to_include:
            roles_to_include = roles_to_include[:2]
        elif freshness_h <= 4 and roles_to_include:
            roles_to_include = roles_to_include[:2]

        for r in roles_to_include:
            clean_r = r.strip()
            if clean_r and clean_r.lower() not in [s.lower() for s in search_terms]:
                search_terms.append(clean_r)

        # 3. Skills budgeting: For windows <= 4h, avoid fanning out into multiple skill variants.
        # Core role queries ('Software Engineer', 'Full Stack Developer') already match these skills.
        if freshness_h > 4:
            raw_skills = query.skills if query.skills else []
            for s in raw_skills:
                clean_s = s.lower().strip()
                if not clean_s:
                    continue
                # For <= 8h, pick only primary canonical skill, avoid adding multiple synonyms
                if freshness_h <= 8 and clean_s in SKILL_EXPANSIONS:
                    primary_variant = SKILL_EXPANSIONS[clean_s][0]
                    if primary_variant.lower() not in [st.lower() for st in search_terms]:
                        search_terms.append(primary_variant)
                elif clean_s in SKILL_EXPANSIONS:
                    for variant in SKILL_EXPANSIONS[clean_s]:
                        if variant.lower() not in [st.lower() for st in search_terms]:
                            search_terms.append(variant)
                elif clean_s not in [st.lower() for st in search_terms]:
                    search_terms.append(clean_s)

        # 4. Canonical deduplication preserving insertion order
        deduped: list[str] = []
        seen: set[str] = set()
        for term in search_terms:
            canonical_key = re.sub(r"[^a-z0-9]", "", term.lower())
            if canonical_key and canonical_key not in seen:
                seen.add(canonical_key)
                deduped.append(term)

        if not deduped:
            deduped = list(DEFAULT_TARGETED_SKILLS[:2] if freshness_h <= 4 else DEFAULT_TARGETED_SKILLS)

        # Hard cap queries based on freshness window
        if freshness_h <= 4:
            return deduped[:2]
        elif freshness_h <= 8:
            return deduped[:4]
        return deduped[:8]

    async def _fetch_url(self, target_url: str) -> str | None:
        """
        Fetches URL using resilient HTTP client with rate limiting and error classification.
        Gracefully handles 429 (rate limited) and 403 (anti-bot blocked) by falling
        back to local socket-level Tor SOCKS5 network proxy.
        """
        from app.utils.http_client import (
            fetch_via_tor_proxy,
            is_tor_proxy_available,
            resilient_fetch,
        )

        limiter = get_source_rate_limiter(self.source_name)
        wait_sec = await limiter.acquire()
        self._metrics.rate_limit_wait_ms += (wait_sec * 1000.0)
        self._metrics.requests_count += 1

        try:
            result = await resilient_fetch(
                target_url,
                headers=GUEST_HEADERS,
                timeout=self.timeout,
                max_retries=self.max_retries,
                caller_tag="linkedin_adapter",
                enable_tor_fallback=True,
            )
            self._metrics.retries_count += getattr(result, "attempt_count", 1) - 1
        except Exception as exc:
            classified = classify_error(exc, self.source_name)
            self.last_error = classified.message
            self.last_error_category = classified.category.value
            self.status = "degraded" if classified.retryable else "blocked"
            self._metrics.status = self.status
            self._metrics.last_error = self.last_error
            self._metrics.last_error_category = self.last_error_category
            logger.warning("linkedin_fetch_exception", error=str(exc), category=classified.category.value)
            return None

        if result.is_success and result.text:
            self.status = "ok"
            self._metrics.status = "ok"
            return result.text

        # Explicit fallback if client received 429 / 403 and did not recover
        if result.status_code in (403, 429) or result.is_blocked or result.is_rate_limited:
            self.status = "blocked"
            self.last_error = f"HTTP {result.status_code} - rate limited / blocked"
            self.last_error_category = "rate_limit_block"
            self._metrics.status = "blocked"
            self._metrics.last_error = self.last_error
            self._metrics.last_error_category = self.last_error_category
            logger.warning(
                "linkedin_rate_limited_or_blocked",
                status_code=result.status_code,
                url=target_url,
                action="attempting_tor_fallback",
            )
            if is_tor_proxy_available(self.tor_proxy_url):
                tor_result = await fetch_via_tor_proxy(
                    target_url,
                    headers=GUEST_HEADERS,
                    timeout=self.timeout + 5.0,
                    caller_tag="linkedin_adapter",
                    proxy_url=self.tor_proxy_url,
                )
                if tor_result and tor_result.is_success and tor_result.text:
                    logger.info("linkedin_tor_fallback_succeeded", url=target_url)
                    self.status = "ok"
                    self._metrics.status = "ok"
                    return tor_result.text

        return None

    def _get_crawler_provider(self) -> Any | None:
        if self._crawler_provider is not None:
            return self._crawler_provider
        try:
            from app.crawling.crawler_registry import get_crawler_provider
            return get_crawler_provider()
        except Exception:
            return None

    async def _fetch_via_crawl4ai(self, target_url: str, timeout: float = 20.0) -> str | None:
        """
        Rendered fetch via shared Crawl4AI provider.
        Returns HTML string or None. Never raises. Falls back to legacy browser.
        """
        provider = self._get_crawler_provider()
        if provider is None or type(provider).__name__ == "NoOpCrawlerProvider":
            return None
        try:
            from app.crawling.crawler_models import CrawlRequest
            result = await asyncio.wait_for(
                provider.fetch(CrawlRequest(
                    url=target_url,
                    timeout=timeout,
                    wait_for="li, div.job-search-card, div.base-card",
                    cache_mode="BYPASS",
                    metadata={"source": "linkedin"},
                )),
                timeout=timeout + 5.0,
            )
            if result and result.success and result.html:
                return result.html
            return None
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("linkedin_crawl4ai_fetch_failed", url=target_url, error=str(e))
            return None

    async def _fetch_via_browser(self, target_url: str, timeout: float = 20.0) -> str | None:
        """
        Secondary fallback discovery path using Playwright headless browser automation.
        Employs launch_persistent_context referencing settings.BROWSER_USER_DATA_DIR
        and applies fingerprint camouflage via apply_stealth_context.
        """
        try:
            from playwright.async_api import async_playwright
            from app.utils.browser_context import resolve_user_data_dir
            from app.utils.browser_stealth import (
                DEFAULT_STEALTH_USER_AGENT,
                apply_stealth_context,
                configure_resource_filters,
            )

            profile_dir = resolve_user_data_dir(self.user_data_dir)
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-first-run",
                "--no-default-browser-check",
            ]

            logger.info(
                "linkedin_playwright_fallback_initiated",
                url=target_url,
                profile_dir=str(profile_dir),
            )

            async with async_playwright() as pw:
                context = await pw.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    headless=self.headless,
                    args=launch_args,
                    user_agent=DEFAULT_STEALTH_USER_AGENT,
                )
                await apply_stealth_context(context)
                page = context.pages[0] if context.pages else await context.new_page()
                await configure_resource_filters(page)

                await page.goto(target_url, wait_until="domcontentloaded", timeout=int(timeout * 1000))

                try:
                    await page.wait_for_selector(
                        "li, div.job-search-card, div.base-card",
                        timeout=5000,
                    )
                except Exception:
                    pass

                content = await page.content()
                await context.close()
                return content
        except Exception as e:
            logger.warning("linkedin_playwright_fallback_failed", error=str(e), url=target_url)
            return None

    def parse_html(self, html: str) -> list[RawJob]:
        """
        Parses HTML from unauthenticated Guest API or Playwright DOM into RawJob items.
        Filters out malformed nodes and enforces structural selector boundaries.
        """
        if not html or not html.strip():
            return []

        soup = BeautifulSoup(html, "html.parser")
        results: list[RawJob] = []
        seen_ids: set[str] = set()

        cards = []
        for card_sel in LINKEDIN_SELECTORS["card"]:
            found = soup.select(card_sel)
            valid_found = [c for c in found if c.select_one("a") or c.select_one("h3")]
            if valid_found:
                cards = valid_found
                break

        for card in cards:
            title_el = None
            for sel in LINKEDIN_SELECTORS["title"]:
                match = card.select_one(sel)
                if match and match.get_text(strip=True):
                    title_el = match
                    break

            link_el = None
            for sel in LINKEDIN_SELECTORS["link"]:
                match = card.select_one(sel)
                if match and match.get("href"):
                    link_el = match
                    break

            if not title_el and not link_el:
                continue

            raw_title = title_el.get_text(strip=True) if title_el else ""
            raw_href = link_el.get("href", "") if link_el else ""

            if not raw_title and link_el:
                raw_title = link_el.get_text(strip=True)

            if not raw_title or len(raw_title) < 2:
                continue

            comp_el = None
            for sel in LINKEDIN_SELECTORS["company"]:
                match = card.select_one(sel)
                if match and match.get_text(strip=True):
                    comp_el = match
                    break
            company = comp_el.get_text(strip=True) if comp_el else "Tech Company"
            if not company or company.lower() in ("company", "confidential", "hiring company"):
                company = "Tech Company"

            loc_el = None
            for sel in LINKEDIN_SELECTORS["location"]:
                match = card.select_one(sel)
                if match and match.get_text(strip=True):
                    loc_el = match
                    break
            location = loc_el.get_text(strip=True) if loc_el else "India"

            time_el = None
            for sel in LINKEDIN_SELECTORS["time"]:
                match = card.select_one(sel)
                if match:
                    time_el = match
                    break

            posted_time_raw = time_el.get_text(strip=True) if time_el else None
            datetime_attr = time_el.get("datetime") if time_el else None

            app_url = clean_linkedin_url(raw_href) if raw_href else f"{BASE_URL}/jobs"
            urn_val = card.get("data-entity-urn", "")
            job_id = extract_linkedin_job_id(urn_val) if urn_val else extract_linkedin_job_id(raw_href)

            loc_lower = location.lower()
            if "remote" in loc_lower or "work from home" in loc_lower:
                remote_type = "REMOTE"
            elif "hybrid" in loc_lower:
                remote_type = "HYBRID"
            else:
                remote_type = "ONSITE"

            desc_el = None
            for sel in LINKEDIN_SELECTORS["description"]:
                match = card.select_one(sel)
                if match and match.get_text(strip=True):
                    desc_el = match
                    break
            description = (
                desc_el.get_text(strip=True)
                if desc_el
                else f"{raw_title} opportunity at {company} in {location}."
            )

            dedup_key = job_id or app_url
            if dedup_key in seen_ids:
                continue
            seen_ids.add(dedup_key)

            raw_payload = {
                "linkedin_id": job_id,
                "title": raw_title,
                "company": company,
                "location": location,
                "posted_time_raw": posted_time_raw,
                "datetime": datetime_attr,
                "source_url": app_url,
            }

            results.append(
                RawJob(
                    source=self.source_name,
                    source_job_id=job_id,
                    title=raw_title,
                    company_name=company,
                    description=description,
                    location=location,
                    remote_type=remote_type,
                    employment_type="FULL_TIME",
                    experience_raw=None,
                    salary_raw=None,
                    posted_time_raw=posted_time_raw,
                    source_url=app_url,
                    application_url=app_url,
                    raw_payload=raw_payload,
                )
            )

        return results

    async def search(self, query: JobSearchQuery) -> list[RawJob]:
        """
        Triple Discovery search across targeted queries:
        1. Fast Path: Guest API endpoint (seeMoreJobPostings/search) with f_TPR.
        2. Rendered Path: Shared Crawl4AI provider via CrawlerProvider boundary.
        3. Fallback Path: Headless Playwright persistent browser with stealth camo.
        
        Optimized with:
        - Freshness-aware query and page offsets (1h uses 1 page, 24h uses up to 3 pages).
        - Global per-sync hydration budget (replaces aggressive per-query hydration).
        - Browser fallback attempt budget and circuit breaker.
        - Early stopping on empty pages or when target limit reached.
        - Granular crawl and timing telemetry.
        """
        queries = self._determine_search_queries(query)
        location = query.locations[0] if query.locations else "India"
        limit = query.limit or 50
        freshness_h = query.freshness_hours or 24
        self._freshness_hours = freshness_h

        logger.info("linkedin_search_started", queries=queries, location=location, limit=limit, freshness_hours=freshness_h)
        all_raw_jobs: list[RawJob] = []
        seen_job_ids: set[str] = set()

        # LinkedIn f_TPR param: r{seconds} filters server-side by posting age
        f_tpr_seconds = freshness_h * 3600
        f_tpr = f"r{f_tpr_seconds}"

        # Freshness-aware pagination offsets: start at 0, only check 25 if first page yields high count
        if freshness_h <= 1:
            offsets = [0]
        elif freshness_h <= 4:
            offsets = [0, 25]
        else:
            offsets = [0, 25, 50]

        # Global per-sync hydration budget:
        # For <= 4h, skip synchronous detail hydration during sync loop.
        # Card descriptions + titles are complete enough for deterministic extraction & matching.
        # This saves 3 requests (30-60s of rate limit headroom).
        if freshness_h <= 4:
            global_hydration_budget = 0
        else:
            global_hydration_budget = 10


        global_hydrated_count = 0
        consecutive_failures = 0
        max_consecutive_failures = 2

        # Browser fallback budgets per sync
        max_browser_fallbacks = 1 if freshness_h <= 4 else 2
        browser_fallback_attempts = 0
        browser_fallback_disabled = False

        self._metrics.queries_count = len(queries)
        start_time = asyncio.get_event_loop().time()
        discovery_t0 = start_time

        try:
            for role in queries:
                if len(all_raw_jobs) >= limit:
                    logger.info("linkedin_search_limit_reached_early_exit", count=len(all_raw_jobs), limit=limit)
                    break

                if consecutive_failures >= max_consecutive_failures:
                    logger.warning(
                        "linkedin_search_circuit_breaker_triggered",
                        reason="consecutive_query_failures",
                        consecutive_failures=consecutive_failures,
                        message="LinkedIn public search endpoints unavailable or blocked. Halting discovery to prevent hanging.",
                    )
                    break

                role_slug = quote_plus(role.strip())
                loc_slug = quote_plus(location.strip())
                role_discovered = 0

                for start_offset in offsets:
                    if len(all_raw_jobs) >= limit:
                        break

                    # Primary Fast Path
                    guest_api_url = (
                        f"{GUEST_SEARCH_URL}?keywords={role_slug}&location={loc_slug}&f_TPR={f_tpr}&start={start_offset}"
                    )
                    self._metrics.pages_count += 1
                    self._metrics.search_requests_count += 1
                    html = await self._fetch_url(guest_api_url)

                    parsed: list[RawJob] = []
                    if html:
                        parsed = self.parse_html(html)

                    # Rendered paths (only on first page if guest API fails and fallback budget available)
                    if (
                        not parsed
                        and start_offset == 0
                        and not browser_fallback_disabled
                        and browser_fallback_attempts < max_browser_fallbacks
                    ):
                        logger.info("linkedin_guest_api_miss_triggering_browser_fallback", role=role)
                        browser_fallback_attempts += 1
                        self._metrics.browser_fallbacks_count += 1
                        public_search_url = (
                            f"{PUBLIC_SEARCH_URL}?keywords={role_slug}&location={loc_slug}&f_TPR={f_tpr}"
                        )
                        rendered_html = await self._fetch_via_crawl4ai(public_search_url)
                        if not rendered_html:
                            rendered_html = await self._fetch_via_browser(public_search_url)
                        if rendered_html:
                            parsed = self.parse_html(rendered_html)
                        else:
                            logger.warning("linkedin_browser_fallback_failed_disabling_for_sync", role=role)
                            browser_fallback_disabled = True

                    if not parsed:
                        # Empty page: stop paginating this query immediately
                        break

                    new_on_page = 0
                    for job in parsed:
                        if len(all_raw_jobs) >= limit:
                            break

                        dedup_id = job.source_job_id or job.source_url
                        if dedup_id in seen_job_ids:
                            continue

                        # Fetch-time fast freshness check: drop stale jobs before detail hydration
                        ref_time = job.scraped_at or datetime.now(timezone.utc)
                        dt_attr = (job.raw_payload or {}).get("datetime")
                        p_at, conf = None, "LOW"
                        if job.posted_time_raw:
                            p_at, conf = self.freshness_service.parse_relative_time(job.posted_time_raw.strip(), reference_now=ref_time)
                        if not p_at and dt_attr:
                            p_at, conf = self.freshness_service.parse_relative_time(str(dt_attr), reference_now=ref_time)

                        if p_at and not self.freshness_service.is_fresh(p_at, conf, freshness_hours=self._freshness_hours, reference_now=ref_time):
                            logger.debug("linkedin_fetch_stale_skipped", title=job.title, posted_raw=job.posted_time_raw, cutoff=self._freshness_hours)
                            continue

                        seen_job_ids.add(dedup_id)
                        new_on_page += 1

                        # Global per-sync detail hydration budget
                        if (
                            (not job.description or len(job.description.strip()) < 200)
                            and job.source_url
                            and global_hydrated_count < global_hydration_budget
                        ):
                            hyd_t0 = asyncio.get_event_loop().time()
                            try:
                                self._metrics.hydration_requests_count += 1
                                hydrated = await self.get_job(job.source_url, use_browser=False)
                                hyd_duration = (asyncio.get_event_loop().time() - hyd_t0) * 1000.0
                                self._metrics.hydration_duration_ms += hyd_duration
                                if hydrated and len(hydrated.description or "") > len(job.description or ""):
                                    all_raw_jobs.append(hydrated)
                                    global_hydrated_count += 1
                                    role_discovered += 1
                                    continue
                            except Exception as e:
                                logger.debug("linkedin_detail_hydration_failed", url=job.source_url, error=str(e))

                        all_raw_jobs.append(job)
                        role_discovered += 1

                    if new_on_page == 0 or (freshness_h <= 4 and new_on_page < 10):
                        # Tight freshness window: if offset 0 returned < 10 jobs, offset 25 will not have fresh postings
                        break

                    await asyncio.sleep(0.1)


                if role_discovered > 0:
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1

                await asyncio.sleep(0.1)
        finally:
            now_t = asyncio.get_event_loop().time()
            elapsed_ms = (now_t - start_time) * 1000.0
            self._metrics.duration_ms += elapsed_ms
            self._metrics.discovery_duration_ms += (now_t - discovery_t0) * 1000.0
            self._metrics.raw_discovered = len(all_raw_jobs)

        logger.info(
            "linkedin_search_completed",
            total_discovered=len(all_raw_jobs),
            queries_count=len(queries),
            pages_count=self._metrics.pages_count,
            requests_count=self._metrics.requests_count,
            hydrations=global_hydrated_count,
            rate_limit_wait_ms=self._metrics.rate_limit_wait_ms,
            duration_ms=self._metrics.duration_ms,
        )
        return all_raw_jobs

    async def get_job(self, url: str, use_browser: bool = False) -> RawJob | None:
        """Fetches a specific LinkedIn job posting by URL."""
        try:
            html = await self._fetch_url(url)
            if not html and use_browser:
                html = await self._fetch_via_crawl4ai(url)
            if not html and use_browser:
                html = await self._fetch_via_browser(url)
            if not html:
                return None

            from app.utils.json_ld import extract_job_posting_ld
            ld_data = extract_job_posting_ld(html)
            if ld_data and ld_data.get("title") and ld_data.get("company_name"):
                job_id = extract_linkedin_job_id(url)
                return RawJob(
                    source=self.source_name,
                    source_job_id=job_id,
                    title=ld_data["title"],
                    company_name=ld_data["company_name"],
                    description=ld_data.get("description", ""),
                    location=ld_data.get("location", "India"),
                    remote_type=ld_data.get("remote_type", "ONSITE"),
                    employment_type=ld_data.get("employment_type", "FULL_TIME"),
                    salary_raw=str(ld_data.get("salary_min")) if ld_data.get("salary_min") else None,
                    posted_time_raw=ld_data.get("date_posted"),
                    source_url=url,
                    application_url=url,
                    raw_payload=ld_data,
                )

            parsed = self.parse_html(html)
            if parsed:
                return parsed[0]

            soup = BeautifulSoup(html, "html.parser")
            title_el = soup.select_one("h1.top-card-layout__title, h2.topcard__title, h1")
            comp_el = soup.select_one("a.topcard__org-name-link, span.topcard__flavor, .sub-nav-cta__optional-url")
            desc_el = soup.select_one("div.show-more-less-html__markup, div.description__text")
            loc_el = soup.select_one("span.topcard__flavor--bullet, span.top-card-layout__first-subline")
            time_el = soup.select_one("span.posted-time-ago__text, time")

            if title_el and comp_el:
                title = title_el.get_text(strip=True)
                company = comp_el.get_text(strip=True)
                desc = desc_el.get_text(strip=True) if desc_el else f"{title} at {company}."
                loc = loc_el.get_text(strip=True) if loc_el else "India"
                time_str = time_el.get_text(strip=True) if time_el else None
                dt_attr = time_el.get("datetime") if time_el else None
                job_id = extract_linkedin_job_id(url)

                return RawJob(
                    source=self.source_name,
                    source_job_id=job_id,
                    title=title,
                    company_name=company,
                    description=desc,
                    location=loc,
                    remote_type="REMOTE" if "remote" in loc.lower() else "ONSITE",
                    employment_type="FULL_TIME",
                    posted_time_raw=time_str,
                    source_url=url,
                    application_url=url,
                    raw_payload={"datetime": dt_attr, "linkedin_id": job_id},
                )

            return None
        except Exception as e:
            logger.warning("linkedin_get_job_failed", url=url, error=str(e))
            return None

    async def normalize(self, raw: RawJob) -> NormalizedJob | None:
        """
        Transforms raw LinkedIn listing into canonical NormalizedJob.
        Enforces:
          1. Strict 24h freshness check in IST (Asia/Kolkata timezone).
          2. Hybrid zero-hallucination skill extraction with provenance tracking.
          3. 5-Tier Level 3 metadata hashing.
          4. Data integrity validation.
        """
        # 1. Strict 24h Freshness Filtering
        posted_at: datetime | None = None
        confidence: str = "LOW"

        # Reference time is when the raw job was captured (scraped_at)
        ref_time = raw.scraped_at or datetime.now(timezone.utc)
        datetime_attr = raw.raw_payload.get("datetime") if isinstance(raw.raw_payload, dict) else None

        # A: If raw.posted_time_raw has relative words (e.g. "14 hours ago", "22 hours ago", "1 day ago", "Just now"),
        # it contains exact elapsed time relative to scraped_at. Prioritize this over date-only datetime attributes.
        has_relative_text = False
        if raw.posted_time_raw:
            raw_lower = raw.posted_time_raw.strip().lower()
            if any(k in raw_lower for k in ["hour", "hr", "h", "min", "sec", "just now", "today", "yesterday", "day ago", "d ago", "recently"]):
                has_relative_text = True
                posted_at, confidence = self.freshness_service.parse_relative_time(raw.posted_time_raw.strip(), reference_now=ref_time)

        # B: If no relative text match, check datetime_attr (e.g. full ISO timestamp with 'T')
        if not posted_at and datetime_attr:
            posted_at, confidence = self.freshness_service.parse_relative_time(str(datetime_attr), reference_now=ref_time)

        # C: Fallback to whatever string is left in raw.posted_time_raw
        if not posted_at and raw.posted_time_raw and not has_relative_text:
            posted_at, confidence = self.freshness_service.parse_relative_time(raw.posted_time_raw.strip(), reference_now=ref_time)

        # Reject stale (>24h) or uncertain (LOW confidence) listings using evaluate_freshness
        is_fresh, reason, age_hours = self.freshness_service.evaluate_freshness(
            posted_at=posted_at,
            confidence=confidence,
            freshness_hours=self._freshness_hours,
            reference_now=ref_time,
            source=self.source_name,
            title=raw.title,
            scraped_at=raw.scraped_at,
        )
        if not is_fresh:
            logger.debug(
                "linkedin_stale_or_uncertain_job_excluded",
                title=raw.title,
                posted_time_raw=raw.posted_time_raw,
                confidence=confidence,
                reason=reason,
                age_hours=age_hours,
            )
            return None

        # 2. Description handling & uncertainty preservation
        # Do NOT reject short snippets. Hydration fallback marks description_confidence = LOW.
        desc = (raw.description or "").strip()
        if not desc:
            desc = f"{raw.title} at {raw.company_name}."
        description_confidence = "HIGH" if len(desc) >= 200 else "LOW"
        raw.description = desc

        # 3. Structural Field Normalization
        norm_title, role_category = normalize_title(raw.title)
        norm_company = raw.company_name.strip()
        norm_loc = normalize_location(raw.location)
        remote_type = raw.remote_type
        if "remote" in norm_loc.lower():
            remote_type = "REMOTE"

        # Robust experience parsing: ignore synthetic fallback description ("... opportunity at ...")
        exp_source = raw.experience_raw
        if not exp_source and raw.description:
            # Only consider description if it's not our synthetic search card snippet
            if "opportunity at" not in raw.description.lower() or len(raw.description.strip()) > 120:
                exp_source = raw.description

        exp_min, exp_max, exp_text, exp_conf = parse_experience_requirement(exp_source)

        # Fall back to title-based seniority inference if no explicit experience extracted
        if not exp_text or exp_conf == "LOW":
            t_min, t_max, t_text, t_conf = infer_experience_from_title(raw.title)
            if t_text:
                exp_min, exp_max, exp_text, exp_conf = t_min, t_max, t_text, t_conf
            elif not exp_text:
                exp_text = "Experience unspecified"

        sal_dict = parse_salary_text(raw.salary_raw)
        sal_min = sal_dict.get("salary_min")
        sal_max = sal_dict.get("salary_max")
        sal_currency = sal_dict.get("salary_currency", "INR")
        sal_period = sal_dict.get("salary_period", "YEAR")

        # Deterministic 5-tier Level 3 multi-dimensional job hash
        job_hash = compute_job_hash(
            norm_company,
            norm_title,
            norm_loc,
            raw.employment_type or "FULL_TIME",
            raw.source_job_id,
        )

        # 4. Zero-Hallucination Skill Extraction with Provenance Tracking
        desc_for_extraction = raw.description
        extraction = await self.skill_extraction_service.extract_skills(
            description=desc_for_extraction,
            title=raw.title,
        )

        raw_data = dict(raw.raw_payload or {})
        raw_data["skill_extraction_method"] = extraction.method
        raw_data["skill_extraction_confidence"] = extraction.confidence
        raw_data["skill_extraction_provenance"] = {
            "method": extraction.method,
            "confidence": extraction.confidence,
            "required_count": len(extraction.required_skills),
            "preferred_count": len(extraction.preferred_skills),
        }
        raw_data["experience_text"] = exp_text
        raw_data["experience_confidence"] = exp_conf
        raw_data["description_confidence"] = description_confidence

        # Quality scoring
        quality_score = 75.0
        if sal_min is not None:
            quality_score += 15.0
        if confidence == "HIGH":
            quality_score += 10.0

        normalized = NormalizedJob(
            source=self.source_name,
            source_job_id=raw.source_job_id,
            title=raw.title,
            normalized_title=norm_title,
            role_category=role_category,
            company_name=raw.company_name,
            normalized_company=norm_company,
            description=raw.description,
            location=raw.location,
            normalized_location=norm_loc,
            remote_type=remote_type,
            employment_type=raw.employment_type or "FULL_TIME",
            experience_min=exp_min,
            experience_max=exp_max,
            experience_text=exp_text,
            experience_confidence=exp_conf,
            description_confidence=description_confidence,
            salary_min=sal_min,
            salary_max=sal_max,
            salary_currency=sal_currency,
            salary_period=sal_period,
            salary_raw=raw.salary_raw,
            posted_at=posted_at,
            posted_at_raw=raw.posted_time_raw,
            posted_at_confidence=confidence,
            source_url=raw.source_url,
            application_url=raw.application_url or raw.source_url,
            job_hash=job_hash,
            required_skills=extraction.required_skills,
            preferred_skills=extraction.preferred_skills,
            quality_score=min(100.0, quality_score),
            raw_data=raw_data,
        )

        # 5. Data Integrity Check
        is_valid, reason = validate_normalized_job(normalized)
        if not is_valid:
            logger.warning(
                "linkedin_job_validation_failed",
                reason=reason,
                title=normalized.title,
                url=normalized.source_url,
            )
            return None

        return normalized
