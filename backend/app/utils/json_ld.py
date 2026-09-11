import json
import re
from typing import Any, Callable
from bs4 import BeautifulSoup
import structlog

logger = structlog.get_logger(__name__)


def clean_html_text(raw_html: str | None) -> str:
    """Strips HTML tags and normalizes whitespace."""
    if not raw_html:
        return ""
    clean = re.sub(r"<[^>]+>", " ", str(raw_html))
    return " ".join(clean.split()).strip()


def extract_json_ld_blocks(html: str) -> list[dict[str, Any]]:
    """
    Finds and parses all <script type="application/ld+json"> blocks in the HTML.
    Unpacks top-level lists and Schema.org @graph collections.
    """
    if not html or "<script" not in html:
        return []

    results: list[dict[str, Any]] = []
    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})

    for script in scripts:
        content = script.string or script.get_text()
        if not content:
            continue
        try:
            data = json.loads(content.strip())
            if isinstance(data, list):
                results.extend(item for item in data if isinstance(item, dict))
            elif isinstance(data, dict):
                if "@graph" in data and isinstance(data["@graph"], list):
                    results.extend(item for item in data["@graph"] if isinstance(item, dict))
                else:
                    results.append(data)
        except (json.JSONDecodeError, TypeError) as e:
            # Try relaxing escape characters or trailing commas
            cleaned = re.sub(r",\s*([\]}])", r"\1", content.strip())
            try:
                data = json.loads(cleaned)
                if isinstance(data, list):
                    results.extend(item for item in data if isinstance(item, dict))
                elif isinstance(data, dict):
                    results.append(data)
            except Exception:
                logger.debug("json_ld_parse_failed", error=str(e))
                continue

    return results


def extract_job_posting_ld(html: str) -> dict[str, Any] | None:
    """
    Scans HTML for Schema.org JobPosting structured metadata.
    Extracts canonical job attributes (title, company, description, datePosted, salary, location).
    """
    blocks = extract_json_ld_blocks(html)
    job_node: dict[str, Any] | None = None

    for block in blocks:
        node_type = block.get("@type", "")
        if isinstance(node_type, list):
            if any(t in ("JobPosting", "https://schema.org/JobPosting", "http://schema.org/JobPosting") for t in node_type):
                job_node = block
                break
        elif node_type in ("JobPosting", "https://schema.org/JobPosting", "http://schema.org/JobPosting"):
            job_node = block
            break

    if not job_node:
        return None

    # Title
    title = str(job_node.get("title") or "").strip()

    # Company name
    company_name = ""
    hiring_org = job_node.get("hiringOrganization")
    if isinstance(hiring_org, dict):
        company_name = str(hiring_org.get("name") or "").strip()
    elif isinstance(hiring_org, str):
        company_name = hiring_org.strip()

    # Description
    raw_desc = job_node.get("description") or ""
    clean_desc = clean_html_text(raw_desc)

    # Date posted & valid through
    date_posted = job_node.get("datePosted")
    valid_through = job_node.get("validThrough")

    # Employment type
    emp_type_raw = job_node.get("employmentType")
    if isinstance(emp_type_raw, list):
        emp_type = emp_type_raw[0] if emp_type_raw else "FULL_TIME"
    else:
        emp_type = str(emp_type_raw or "FULL_TIME")

    # Location & Remote status
    location = ""
    remote_type = "ONSITE"
    if str(job_node.get("jobLocationType", "")).upper() == "TELECOMMUTE":
        remote_type = "REMOTE"

    job_loc = job_node.get("jobLocation")
    if isinstance(job_loc, dict):
        addr = job_loc.get("address")
        if isinstance(addr, dict):
            parts = [
                addr.get("addressLocality"),
                addr.get("addressRegion"),
                addr.get("addressCountry"),
            ]
            location = ", ".join(str(p).strip() for p in parts if p)
        elif isinstance(addr, str):
            location = addr.strip()
    elif isinstance(job_loc, list) and job_loc:
        first_loc = job_loc[0]
        if isinstance(first_loc, dict):
            addr = first_loc.get("address")
            if isinstance(addr, dict):
                parts = [
                    addr.get("addressLocality"),
                    addr.get("addressRegion"),
                    addr.get("addressCountry"),
                ]
                location = ", ".join(str(p).strip() for p in parts if p)
            elif isinstance(addr, str):
                location = addr.strip()

    # Salary extraction
    salary_min = None
    salary_max = None
    salary_currency = "INR"
    salary_period = "YEAR"
    salary_raw = None

    base_salary = job_node.get("baseSalary")
    if isinstance(base_salary, dict):
        salary_currency = base_salary.get("currency") or "INR"
        val = base_salary.get("value")
        if isinstance(val, dict):
            salary_min = val.get("minValue") or val.get("value")
            salary_max = val.get("maxValue") or val.get("value")
            unit = val.get("unitText", "")
            if "MONTH" in str(unit).upper():
                salary_period = "MONTH"
            elif "HOUR" in str(unit).upper():
                salary_period = "HOUR"
            salary_raw = f"{salary_currency} {salary_min} - {salary_max} / {salary_period}"
        elif isinstance(val, (int, float, str)):
            salary_min = val
            salary_raw = f"{salary_currency} {val}"

    # Skills / requirements
    skills: list[str] = []
    skills_raw = job_node.get("skills")
    if isinstance(skills_raw, list):
        skills = [str(s).strip() for s in skills_raw if s]
    elif isinstance(skills_raw, str):
        skills = [s.strip() for s in skills_raw.split(",") if s.strip()]

    return {
        "title": title,
        "company_name": company_name,
        "description": clean_desc,
        "raw_description": raw_desc,
        "date_posted": str(date_posted) if date_posted else None,
        "valid_through": str(valid_through) if valid_through else None,
        "employment_type": emp_type,
        "location": location,
        "remote_type": remote_type,
        "salary_min": float(salary_min) if salary_min is not None and str(salary_min).replace(".", "", 1).isdigit() else None,
        "salary_max": float(salary_max) if salary_max is not None and str(salary_max).replace(".", "", 1).isdigit() else None,
        "salary_currency": salary_currency,
        "salary_period": salary_period,
        "salary_raw": salary_raw,
        "skills": skills,
        "source_type": "JSON_LD",
        "raw_node": job_node,
    }


def parse_job_with_fallback(
    html: str,
    css_fallback_fn: Callable[[str], dict[str, Any]] | None = None,
) -> tuple[dict[str, Any] | None, str]:
    """
    Parses job listing data prioritizing Schema.org JSON-LD structural metadata.
    If JSON-LD metadata is absent or missing essential fields (title, company, or description),
    falls back gracefully to the provided CSS selector parsing function.

    Returns:
        tuple of (job_data_dict, source_channel: "JSON_LD" | "CSS_SELECTOR" | "NONE")
    """
    # 1. Attempt primary JSON-LD extraction
    ld_job = extract_job_posting_ld(html)
    if ld_job and ld_job.get("title") and (ld_job.get("company_name") or ld_job.get("description")):
        logger.debug("job_parsed_via_json_ld", title=ld_job["title"], company=ld_job["company_name"])
        return ld_job, "JSON_LD"

    # 2. Fall back to CSS selector parser
    if css_fallback_fn:
        try:
            css_job = css_fallback_fn(html)
            if css_job and css_job.get("title"):
                logger.debug("job_parsed_via_css_fallback", title=css_job["title"])
                return css_job, "CSS_SELECTOR"
        except Exception as e:
            logger.warning("css_fallback_parsing_failed", error=str(e))

    return None, "NONE"
