import asyncio
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any
from urllib.parse import urljoin, quote_plus
from bs4 import BeautifulSoup
import httpx
import structlog

from app.config import settings
from app.services.dedup_service import compute_job_hash
from app.services.freshness_service import get_freshness_service
from app.sources.adapters.internshala import is_senior_title
from app.sources.base import JobSearchQuery, JobSource, NormalizedJob, RawJob
from app.sources.errors import RateLimitBlockError, TransientNetworkError, classify_error
from app.sources.rate_limiter import get_source_rate_limiter
from app.crawling.crawler_registry import get_crawler_provider
from app.crawling.crawler_models import CrawlRequest
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

logger = structlog.get_logger(__name__)

BASE_URL = "https://www.naukri.com"

# Targeted queries mapping for tech skills and broad roles
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

SKILL_EXPANSION = {
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

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
}

API_HEADERS = {
    "authority": "www.naukri.com",
    "accept": "application/json",
    "accept-language": "en-US,en;q=0.9",
    "appid": "109",
    "systemid": "Naukri",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
}

# Centralized CSS selectors for Naukri HTML listings
NAUKRI_HTML_SELECTORS = {
    "card": ["div.srp-jobtuple-wrapper", "article.jobTuple", "div.cust-job-tuple"],
    "title": ["a.title", ".job-title", "h2 a", "h3 a"],
    "company": ["a.comp-name", ".comp-name", ".company-name", "span.comp-dtls-wrap a"],
    "location": [".locWdth", ".loc-wrap", ".location"],
    "salary": [".ni-job-tuple-icon-salary", ".sal-wrap", ".salary"],
    "experience": [".expwdth", ".exp-wrap", ".experience"],
    "description": [".job-desc", ".job-description", ".desc"],
    "posted_time": [".job-post-day", ".date", ".badge"],
    "skills": ["ul.tags-gt li", "ul.tags li", ".tag-li"],
}


def extract_naukri_job_id(url_or_id: str | None) -> str:
    """
    Extracts canonical Naukri job ID.
    Job IDs on Naukri typically appear as numeric suffixes at the end of the URL
    (e.g., 220826012440 in /job-listings-...-220826012440).
    """
    if not url_or_id:
        return str(uuid.uuid4())

    cleaned = str(url_or_id).strip()
    # Match trailing numeric ID: 6 to 16 digits
    match = re.search(r"(\d{6,16})(?:[/?#]|$)", cleaned)
    if match:
        return match.group(1)

    return cleaned


class NaukriAdapter(JobSource):
    source_name: str = "naukri"

    def __init__(self, settings: Any = None, timeout: float = 10.0, max_retries: int = 2):
        super().__init__()
        from app.config import settings as default_settings
        self.settings = settings or default_settings
        self.timeout = timeout
        self.max_retries = max_retries
        self.freshness_service = get_freshness_service()
        self.enabled = getattr(self.settings, "SOURCE_NAUKRI_ENABLED", True)
        self._crawler_provider = None
        self._freshness_hours: int = 24  # Updated dynamically by search()

    def _get_crawler_provider(self) -> Any | None:
        if self._crawler_provider is not None:
            return self._crawler_provider
        try:
            self._crawler_provider = get_crawler_provider()
            return self._crawler_provider
        except Exception:
            return None

    async def _fetch_via_crawl4ai(self, target_url: str, timeout: float = 20.0) -> str | None:
        """
        Rendered fetch via shared Crawl4AI provider.
        Returns HTML string or None. Never raises. Falls back gracefully.
        """
        provider = self._get_crawler_provider()
        if provider is None or type(provider).__name__ == "NoOpCrawlerProvider":
            return None
        try:
            limiter = get_source_rate_limiter(self.source_name)
            await limiter.acquire()
            self._metrics.requests_count += 1
            logger.info("naukri_crawl4ai_fetch_started", url=target_url, timeout=timeout)
            result = await asyncio.wait_for(
                provider.fetch(CrawlRequest(
                    url=target_url,
                    timeout=timeout,
                    wait_for="div.srp-jobtuple-wrapper, article.jobTuple, div.cust-job-tuple",
                    cache_mode="BYPASS",
                    metadata={"source": "naukri"},
                )),
                timeout=timeout + 5.0,
            )
            if result and result.success and result.html:
                logger.info(
                    "naukri_crawl4ai_fetch_completed",
                    url=target_url,
                    html_len=len(result.html),
                    duration_sec=result.duration_sec,
                )
                self.status = "ok"
                self._metrics.status = "ok"
                return result.html
            logger.warning(
                "naukri_crawl4ai_fetch_failed",
                url=target_url,
                error=result.error_message if result else "no result",
            )
            return None
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("naukri_crawl4ai_fetch_exception", url=target_url, error=str(e))
            return None

    async def health_check(self) -> bool:
        """
        Verifies public availability of Naukri by sending a HEAD/GET request
        to a reliable public endpoint (e.g. /it-jobs).
        """
        try:
            async with httpx.AsyncClient(headers=HEADERS, timeout=5.0) as client:
                res = await client.head(f"{BASE_URL}/it-jobs", follow_redirects=True)
                if res.status_code in (200, 301, 302):
                    return True
                # Fallback to GET if HEAD method is not allowed
                res_get = await client.get(f"{BASE_URL}/it-jobs", follow_redirects=True)
                return res_get.status_code in (200, 301, 302)
        except Exception as e:
            logger.warning("naukri_health_check_failed", error=str(e))
            return False

    def _determine_search_queries(self, query: JobSearchQuery) -> list[str]:
        """
        Translates a JobSearchQuery into targeted skill search terms with alias expansion.
        """
        search_terms: list[str] = []
        if query.query and query.query.strip():
            search_terms.append(query.query.strip())
        else:
            # Query broad tech roles so description-only skill jobs are captured
            roles = query.roles if query.roles else CORE_TECH_ROLES
            for r in roles:
                if r not in search_terms:
                    search_terms.append(r)

        if query.roles:
            for r in query.roles:
                if r not in search_terms:
                    search_terms.append(r)

        raw_skills = query.skills if query.skills else []
        for s in raw_skills:
            clean_s = s.lower().strip()
            if clean_s in SKILL_EXPANSION:
                for variant in SKILL_EXPANSION[clean_s]:
                    if variant not in search_terms:
                        search_terms.append(variant)
            elif clean_s and clean_s not in search_terms:
                search_terms.append(clean_s)

        return search_terms if search_terms else list(DEFAULT_TARGETED_SKILLS)

    async def _fetch_url(self, target_url: str, headers: dict[str, str] | None = None) -> tuple[int, str]:
        """
        HTTP fetch with rate limiting, exponential backoff, and anti-bot error handling.
        Returns (status_code, body).
        """
        from app.utils.http_client import resilient_fetch

        limiter = get_source_rate_limiter(self.source_name)
        await limiter.acquire()
        self._metrics.requests_count += 1

        try:
            result = await resilient_fetch(
                target_url,
                headers=headers or HEADERS,
                timeout=self.timeout,
                max_retries=self.max_retries,
                caller_tag="naukri_adapter",
            )
            self._metrics.retries_count += getattr(result, "retry_count", 0)
            if result.status_code in (403, 429) or result.is_blocked:
                self.status = "blocked"
                self.last_error = f"HTTP {result.status_code} - blocked by Naukri perimeter"
                self.last_error_category = "rate_limit_block"
                self._metrics.status = "blocked"
                self._metrics.last_error = self.last_error
                self._metrics.last_error_category = self.last_error_category
            elif result.is_success:
                self.status = "ok"
                self._metrics.status = "ok"

            return result.status_code, result.text
        except Exception as exc:
            classified = classify_error(exc, self.source_name)
            self.last_error = classified.message
            self.last_error_category = classified.category.value
            self.status = "degraded" if classified.retryable else "failed"
            self._metrics.status = self.status
            self._metrics.last_error = self.last_error
            self._metrics.last_error_category = self.last_error_category
            logger.warning("naukri_fetch_exception", error=str(exc), category=classified.category.value)
            return 0, ""

    def _extract_next_data_payload(self, html: str) -> list[RawJob]:
        """
        Extracts RawJob objects directly from the static Next.js __NEXT_DATA__ JSON script tag.
        Guarantees 100% data fidelity and is immune to CSS selector drift.
        """
        if not html or "__NEXT_DATA__" not in html:
            return []

        try:
            soup = BeautifulSoup(html, "html.parser")
            script_tag = soup.find("script", id="__NEXT_DATA__")
            if script_tag:
                raw_payload = script_tag.string or script_tag.get_text()
                if not raw_payload:
                    return []
                payload = json.loads(raw_payload)
                page_props = payload.get("props", {}).get("pageProps", {})
                job_list = (
                    page_props.get("searchPageData", {}).get("jobDetails")
                    or page_props.get("initialState", {}).get("searchPageData", {}).get("jobDetails")
                    or []
                )
                if job_list:
                    extracted = self.parse_json({"jobDetails": job_list})
                    logger.info("naukri_extracted_via_next_data", count=len(extracted))
                    return extracted
        except Exception as ex:
            logger.warning("naukri_next_data_extraction_failed", error=str(ex))
        return []

    def parse_json(self, data: dict[str, Any]) -> list[RawJob]:
        """
        Extracts RawJob objects from Naukri structured JSON payloads (such as
        jobapi search responses or embedded SSR states).
        """
        job_details = data.get("jobDetails") or []
        results: list[RawJob] = []

        for job in job_details:
            job_id = str(job.get("jobId") or "")
            title = job.get("title") or ""
            company = job.get("companyName") or ""
            desc = job.get("jobDescription") or f"{title} role at {company}."
            placeholders = job.get("placeholders") or []

            # Extract location, salary, experience from placeholders
            loc_val = None
            salary_val = job.get("salary")
            exp_val = job.get("experienceStr") or job.get("experienceText")

            for p in placeholders:
                ptype = p.get("type")
                plabel = p.get("label")
                if ptype == "location" and not loc_val:
                    loc_val = plabel
                elif ptype == "salary" and not salary_val:
                    salary_val = plabel
                elif ptype == "experience" and not exp_val:
                    exp_val = plabel

            location = loc_val or "India"
            remote_str = (job.get("workMode") or "").lower()
            if "remote" in remote_str or "work from home" in location.lower() or "remote" in location.lower():
                remote_type = "REMOTE"
            elif "hybrid" in remote_str or "hybrid" in location.lower():
                remote_type = "HYBRID"
            else:
                remote_type = "ONSITE"

            # URL
            jd_url = job.get("jdURL") or job.get("staticUrl") or ""
            if jd_url.startswith("http"):
                app_url = jd_url
            elif jd_url:
                app_url = urljoin(BASE_URL, jd_url)
            else:
                app_url = f"{BASE_URL}/job-listings-{job_id}"

            # Posted time
            footer_label = job.get("footerPlaceholderLabel")
            created_date = job.get("createdDate")
            posted_time_raw = footer_label
            if not posted_time_raw and created_date is not None:
                try:
                    # createdDate is typically epoch millis (int/float). Handle numeric strings too.
                    if isinstance(created_date, str) and created_date.strip().replace('.', '', 1).isdigit():
                        created_date = float(created_date.strip())
                    posted_time_raw = datetime.fromtimestamp(float(created_date) / 1000, tz=timezone.utc).isoformat()
                except Exception:
                    posted_time_raw = None

            raw_payload = dict(job)
            raw_payload["source_job_id"] = job_id or extract_naukri_job_id(app_url)

            # Strict validation
            if not title or not company:
                continue

            results.append(
                RawJob(
                    source=self.source_name,
                    source_job_id=str(job_id or extract_naukri_job_id(app_url)),
                    title=title,
                    company_name=company,
                    description=desc,
                    location=location,
                    remote_type=remote_type,
                    employment_type="FULL_TIME",
                    experience_raw=exp_val,
                    salary_raw=salary_val,
                    posted_time_raw=posted_time_raw,
                    source_url=app_url,
                    application_url=app_url,
                    raw_payload=raw_payload,
                )
            )

        return results

    def parse_html(self, html: str) -> list[RawJob]:
        """
        Extracts RawJob objects from Naukri HTML listings.
        Checks for high-fidelity embedded __NEXT_DATA__ script tag first,
        then falls back to DOM CSS selectors (div.srp-jobtuple-wrapper, etc.).
        """
        # 1. High-fidelity static data layer extraction
        next_data_jobs = self._extract_next_data_payload(html)
        if next_data_jobs:
            return next_data_jobs

        # 2. DOM CSS Selector fallback
        soup = BeautifulSoup(html, "html.parser")
        cards = []
        best_cards: list[Any] = []
        best_usable = 0

        def _is_usable_card(card_el: Any) -> bool:
            # Pick the first title selector match without relying on outer helpers.
            title_el = None
            for sel in NAUKRI_HTML_SELECTORS["title"]:
                match = card_el.select_one(sel)
                if match:
                    title_el = match
                    break

            if not title_el:
                return False

            raw_title = title_el.get_text(strip=True)
            href = title_el.get("href")
            return bool(raw_title and href)

        # Evaluate each selector variant and pick the best yield.
        for card_sel in NAUKRI_HTML_SELECTORS["card"]:
            found = soup.select(card_sel)
            if not found:
                continue
            usable = sum(1 for c in found[:10] if _is_usable_card(c))
            if usable > best_usable:
                best_usable = usable
                best_cards = found

        cards = best_cards

        if not cards:
            return []

        results: list[RawJob] = []

        def _select_first(card_el: Any, selectors: list[str] | str):
            if isinstance(selectors, str):
                return card_el.select_one(selectors)
            for sel in selectors:
                match = card_el.select_one(sel)
                if match:
                    return match
            return None

        for card in cards:
            # 1. Title & URL
            title_el = None
            for sel in NAUKRI_HTML_SELECTORS["title"]:
                match = card.select_one(sel)
                if match:
                    title_el = match
                    break

            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            rel_url = title_el.get("href") or ""
            if not title or not rel_url:
                continue

            app_url = urljoin(BASE_URL, rel_url)
            job_id = card.get("data-job-id") or extract_naukri_job_id(app_url)

            # 2. Company
            comp_el = _select_first(card, NAUKRI_HTML_SELECTORS["company"])
            company = comp_el.get_text(strip=True) if comp_el else ""
            if not company or company.lower() in ("company", "confidential", "hiring company"):
                continue

            # 3. Location & Remote
            loc_el = _select_first(card, NAUKRI_HTML_SELECTORS["location"])
            location = loc_el.get_text(strip=True) if loc_el else "India"
            loc_lower = location.lower()
            if "remote" in loc_lower or "work from home" in loc_lower:
                remote_type = "REMOTE"
            elif "hybrid" in loc_lower:
                remote_type = "HYBRID"
            else:
                remote_type = "ONSITE"

            # 4. Salary
            sal_el = _select_first(card, NAUKRI_HTML_SELECTORS["salary"])
            salary_raw = sal_el.get_text(strip=True) if sal_el else None

            # 5. Experience
            exp_el = _select_first(card, NAUKRI_HTML_SELECTORS["experience"])
            exp_raw = exp_el.get_text(strip=True) if exp_el else None

            # 6. Description / Snippet
            desc_el = _select_first(card, NAUKRI_HTML_SELECTORS["description"])
            desc = desc_el.get_text(strip=True) if desc_el else f"{title} opportunity at {company}."

            # 7. Posted Time
            age_el = _select_first(card, NAUKRI_HTML_SELECTORS["posted_time"])
            posted_time_raw = age_el.get_text(strip=True) if age_el else None

            # 8. Skills
            skills_list = []
            for skill_sel in NAUKRI_HTML_SELECTORS["skills"]:
                items = card.select(skill_sel)
                if items:
                    skills_list = [s.get_text(strip=True) for s in items if s.get_text(strip=True)]
                    break

            raw_payload = {
                "naukri_id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "salary": salary_raw,
                "experience": exp_raw,
                "posted_time": posted_time_raw,
                "skills": skills_list,
                "url": app_url,
            }

            results.append(
                RawJob(
                    source=self.source_name,
                    source_job_id=str(job_id),
                    title=title,
                    company_name=company,
                    description=desc,
                    location=location,
                    remote_type=remote_type,
                    employment_type="FULL_TIME",
                    experience_raw=exp_raw,
                    salary_raw=salary_raw,
                    posted_time_raw=posted_time_raw,
                    source_url=app_url,
                    application_url=app_url,
                    raw_payload=raw_payload,
                )
            )

        return results

    async def search(self, query: JobSearchQuery) -> list[RawJob]:
        """
        Executes targeted searches across Naukri role categories.
        Operates with error isolation and anti-bot graceful recovery.
        """
        queries = self._determine_search_queries(query)
        self._freshness_hours = query.freshness_hours or 24
        logger.info("naukri_search_started", queries=queries, limit=query.limit, freshness_hours=self._freshness_hours)

        all_raw_jobs: list[RawJob] = []
        seen_job_ids: set[str] = set()

        max_pages = 3
        for term in queries:
            slug = quote_plus(term.lower())
            # For early-career searches (experience_max <= 2), avoid forcing &experience=0
            # which blinds Naukri search to only postings explicitly tagged "Fresher"
            if query.experience_max is not None and query.experience_max > 2:
        # For early-career searches (experience_max <= 2), avoid forcing &experience=0
        # which blinds Naukri search to only postings explicitly tagged "Fresher"
        if query.experience_max is not None and query.experience_max > 2:
            exp_api_param = f"&experience={query.experience_max}"
            exp_web_param = f"experience={query.experience_max}&"
        else:
            exp_api_param = ""
            exp_web_param = ""

        start_time = asyncio.get_event_loop().time()
        try:
            for term in queries:
                for page_no in range(1, max_pages + 1):
                    # 1. Primary path: Naukri Mobile/Gateway API (fast JSON response)
                    api_url = (
                        f"{BASE_URL}/jobapi/v3/search?noOfResults=20&urlType=search_by_keyword"
                        f"&searchType=adv&keyword={quote_plus(term)}&pageNo={page_no}"
                        f"&k={quote_plus(term)}&seoKey={quote_plus(term.lower().replace(' ', '-'))}-jobs"
                        f"&src=jobsearchDesk&latLong="
                    )
                    if exp_api_param:
                        api_url += f"&experience={exp_api_param}"

                    logger.info("naukri_fetch_query", query=term, page=page_no, url=api_url)
                    status, text = await self._fetch_url(api_url, headers=API_HEADERS)

                    parsed: list[RawJob] = []
                    if status == 200 and text:
                        try:
                            data = json.loads(text)
                            parsed = self.parse_json(data)
                        except Exception as e:
                            self._metrics.parse_errors += 1
                            logger.warning("naukri_json_parse_failed", error=str(e), query=term, page=page_no)

                    # If API blocked or yielded 0 results on page 1, fall back to public web search page
                    if not parsed and page_no == 1:
                        page_slug = term.lower().replace(" ", "-")
                        page_url = f"{BASE_URL}/{page_slug}-jobs?{exp_web_param}jobAge=1"
                        p_status, p_text = await self._fetch_url(page_url)
                        if p_status == 200 and p_text:
                            parsed = self.parse_html(p_text)

                        # If static HTML returned unhydrated Next.js shell, hydrate via shared Crawl4AI provider
                        if not parsed:
                            logger.info("naukri_crawl4ai_fallback_activated", url=page_url, reason="static_html_unhydrated")
                            browser_html = await self._fetch_via_crawl4ai(page_url)
                            if browser_html:
                                parsed = self.parse_html(browser_html)
                    elif not parsed and page_no > 1:
                        page_slug = term.lower().replace(" ", "-")
                        page_url = f"{BASE_URL}/{page_slug}-jobs-{page_no}?{exp_web_param}jobAge=1"
                        p_status, p_text = await self._fetch_url(page_url)
                        if p_status == 200 and p_text:
                            parsed = self.parse_html(p_text)

                        if not parsed:
                            logger.info("naukri_crawl4ai_fallback_activated", url=page_url, page=page_no, reason="static_html_unhydrated")
                            browser_html = await self._fetch_via_crawl4ai(page_url)
                            if browser_html:
                                parsed = self.parse_html(browser_html)

                    if not parsed:
                        break

                    new_on_page = 0
                    page_fresh = 0
                    for r in parsed:
                        # Fetch-time fast freshness filter
                        p_at = None
                        conf = "LOW"
                        c_epoch = (r.raw_payload or {}).get("createdDate")
                        if c_epoch:
                            try:
                                c_val = float(str(c_epoch).strip()) if isinstance(c_epoch, str) else c_epoch
                                if isinstance(c_val, (int, float)) and float(c_val) > 0:
                                    p_at = datetime.fromtimestamp(float(c_val) / 1000, tz=timezone.utc)
                                    conf = "HIGH"
                            except Exception:
                                p_at = None

                        if not p_at and r.posted_time_raw:
                            p_at, conf = self.freshness_service.parse_recency_string(r.posted_time_raw)

                        ref_now = r.scraped_at or datetime.now(timezone.utc)
                        if p_at and not self.freshness_service.is_fresh(p_at, conf, freshness_hours=self._freshness_hours, reference_now=ref_now):
                            logger.debug("naukri_fetch_stale_skipped", title=r.title, posted_raw=r.posted_time_raw, cutoff=self._freshness_hours)
                            continue

                        page_fresh += 1
                        dedup_key = r.source_job_id or r.source_url
                        if dedup_key not in seen_job_ids:
                            seen_job_ids.add(dedup_key)
                            all_raw_jobs.append(r)
                            new_on_page += 1

                    if new_on_page == 0 or (page_no > 1 and page_fresh == 0):
                        break

                    # Polite delay between page requests
                    await asyncio.sleep(0.5)

                # Polite delay between query terms
                await asyncio.sleep(0.5)
        finally:
            elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000.0
            self._metrics.duration_ms += elapsed_ms
            self._metrics.raw_discovered = len(all_raw_jobs)

        logger.info("naukri_search_completed", total_discovered=len(all_raw_jobs))
        return all_raw_jobs

    def normalize_job(self, raw: RawJob) -> NormalizedJob | None:
        """
        Normalizes and enforces strict 24-hour freshness on Naukri listings.
        Preserves honest confidence ratings and excludes uncertain timestamps.
        """
        posted_at: datetime | None = None
        confidence: str = "LOW"

        # Check createdDate in raw_payload if epoch timestamp is provided
        created_epoch = raw.raw_payload.get("createdDate")
        if created_epoch:
            try:
                created_val = created_epoch
                if isinstance(created_epoch, str) and created_epoch.strip().replace('.', '', 1).isdigit():
                    created_val = float(created_epoch.strip())
                if isinstance(created_val, (int, float)) and float(created_val) > 0:
                    posted_at = datetime.fromtimestamp(float(created_val) / 1000, tz=timezone.utc)
                    confidence = "HIGH"
            except Exception:
                posted_at = None

        # Fallback to parsing posted_time_raw (relative strings like "Just now", "Recently")
        if not posted_at and raw.posted_time_raw:
            # Parse relative recency text with automatic rescue
            posted_at, confidence = self.freshness_service.parse_recency_string(raw.posted_time_raw)

        # Dynamic freshness enforcement:
        # Reject if timestamp missing or confidence not acceptable
        if not posted_at or not self.freshness_service.is_fresh(posted_at, confidence, freshness_hours=self._freshness_hours):
            return None

        # If we accepted createdDate as epoch, prefer HIGH confidence.
        if confidence != "HIGH" and (raw.raw_payload or {}).get("createdDate") is not None:
            try:
                created_epoch = (raw.raw_payload or {}).get("createdDate")
                created_val = created_epoch
                if isinstance(created_epoch, str) and created_epoch.strip().replace('.', '', 1).isdigit():
                    created_val = float(created_epoch.strip())
                if isinstance(created_val, (int, float)) and float(created_val) > 0:
                    confidence = "HIGH"
            except Exception:
                pass

            # Re-validate freshness with updated confidence.
            if not self.freshness_service.is_fresh(posted_at, confidence):
                return None

        # Experience parsing using unified recall-first parser
        exp_min, exp_max, exp_text, exp_conf = parse_experience_requirement(raw.experience_raw or raw.description)

        # Title & Category
        norm_title, category = normalize_title(raw.title)

        # Location & Remote
        norm_loc = normalize_location(raw.location)
        remote_type = raw.remote_type
        if "remote" in norm_loc.lower():
            remote_type = "REMOTE"

        # Salary parsing
        sal_dict = parse_salary_text(raw.salary_raw)
        min_sal = sal_dict.get("salary_min")
        max_sal = sal_dict.get("salary_max")

        # Description handling
        desc = (raw.description or "").strip()
        if not desc:
            desc = f"{raw.title} at {raw.company_name}."
        description_confidence = "HIGH" if len(desc) >= 200 else "LOW"

        # From raw payload tags/skills
        explicit_skills: list[str] = []
        payload_skills = raw.raw_payload.get("tagsAndSkills") or raw.raw_payload.get("skills") or ""
        if isinstance(payload_skills, str) and payload_skills.strip():
            explicit_skills.extend([s.strip() for s in payload_skills.split(",") if s.strip()])
        elif isinstance(payload_skills, list):
            explicit_skills.extend([str(s).strip() for s in payload_skills if str(s).strip()])

        required_skills, preferred_skills = extract_skills_from_text(
            description=desc,
            title=raw.title,
            explicit_skills=explicit_skills,
        )

        # Deterministic multi-dimensional job hash for deduplication
        norm_company = raw.company_name.strip()
        job_hash = compute_job_hash(
            norm_company,
            norm_title,
            norm_loc,
            raw.employment_type or "FULL_TIME",
            raw.source_job_id,
        )

        # Quality scoring
        quality_score = 75.0
        if raw.salary_raw and "not disclosed" not in raw.salary_raw.lower():
            quality_score += 15.0
        if confidence == "HIGH":
            quality_score += 10.0

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
            salary_period="YEAR",
            salary_raw=raw.salary_raw,
            posted_at=posted_at,
            posted_at_raw=raw.posted_time_raw,
            posted_at_confidence=confidence,
            source_url=raw.source_url,
            application_url=raw.application_url or raw.source_url,
            job_hash=job_hash,
            quality_score=min(100.0, quality_score),
            raw_data=raw_payload,
        )

    async def get_job(self, url: str) -> RawJob | None:
        """
        Fetches a specific Naukri listing by URL.
        """
        try:
            status, html = await self._fetch_url(url)
            parsed = self.parse_html(html) if status == 200 and html else []
            if not parsed:
                logger.info("naukri_crawl4ai_fallback_activated", url=url, reason="http_fetch_empty")
                browser_html = await self._fetch_via_crawl4ai(url)
                if browser_html:
                    parsed = self.parse_html(browser_html)
            return parsed[0] if parsed else None
        except Exception as e:
            logger.warning("naukri_get_job_failed", url=url, error=str(e))
            return None

    async def normalize(self, raw: RawJob) -> NormalizedJob | None:
        """
        Conforms to JobSource ABC.
        Returns None if job is stale, invalid, or LOW-confidence.
        """
        norm = self.normalize_job(raw)
        if norm is None:
            return None

        # Enhance skills via shared JobSkillExtractionService (deterministic first, LLM fallback if uncertain)
        explicit_skills: list[str] = []
        payload_skills = raw.raw_payload.get("tagsAndSkills") or raw.raw_payload.get("skills") or ""
        if isinstance(payload_skills, str) and payload_skills.strip():
            explicit_skills.extend([s.strip() for s in payload_skills.split(",") if s.strip()])
        elif isinstance(payload_skills, list):
            explicit_skills.extend([str(s).strip() for s in payload_skills if str(s).strip()])

        from app.services.skill_extraction_service import get_skill_extraction_service
        extraction = await get_skill_extraction_service().extract_skills(
            description=raw.description or "",
            title=raw.title,
            explicit_skills=explicit_skills,
        )

        norm.required_skills = extraction.required_skills
        norm.preferred_skills = extraction.preferred_skills

        # Attach extraction provenance metadata
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
