import json
import re
from pathlib import Path
from typing import Any
import structlog

from app.config import settings
from app.services.freshness_service import get_freshness_service
from app.sources.base import JobSearchQuery, JobSource, NormalizedJob, RawJob
from app.utils.normalization import (
    normalize_location,
    normalize_skills,
    normalize_title,
    parse_experience_requirement,
    parse_salary_text,
)

logger = structlog.get_logger(__name__)


def parse_experience_range(raw_exp: str | None) -> tuple[int, int]:
    if not raw_exp:
        return 0, 0
    min_y, max_y, _, _ = parse_experience_requirement(raw_exp)
    if min_y is None and max_y is None:
        return 0, 0
    return min_y or 0, max_y if max_y is not None else (min_y or 0)


def calculate_quality_score(
    company_name: str,
    salary_raw: str | None,
    application_url: str | None,
    posted_confidence: str,
    skills_count: int,
) -> float:
    score = 40.0  # Base
    if company_name and len(company_name.strip()) > 2:
        score += 20.0
    if salary_raw and "not disclosed" not in salary_raw.lower():
        score += 15.0
    if application_url and ("apply" in application_url.lower() or "careers" in application_url.lower()):
        score += 15.0
    if posted_confidence == "HIGH":
        score += 10.0
    elif posted_confidence == "MEDIUM":
        score += 5.0
    if skills_count >= 3:
        score += 5.0
    return min(100.0, score)


class SampleJobAdapter(JobSource):
    source_name: str = "sample"
    enabled: bool = True

    def __init__(self, data_path: Path | None = None):
        if data_path is None:
            # Look in data/sample_jobs/sample_jobs.json relative to project root
            root_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
            self.data_path = root_dir / "data" / "sample_jobs" / "sample_jobs.json"
        else:
            self.data_path = data_path
        self.freshness_service = get_freshness_service()

    def _load_data(self) -> list[dict[str, Any]]:
        if not self.data_path.exists():
            logger.warning("sample_jobs_file_not_found", path=str(self.data_path))
            return []
        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("sample_jobs_load_failed", error=str(e))
            return []

    async def search(self, query: JobSearchQuery) -> list[RawJob]:
        raw_list = self._load_data()
        results: list[RawJob] = []

        q_lower = query.query.lower() if query.query else None
        roles_lower = [r.lower() for r in query.roles] if query.roles else []
        locs_lower = [loc.lower() for loc in query.locations] if query.locations else []

        for item in raw_list:
            title = item.get("title", "")
            desc = item.get("description", "")
            comp = item.get("company_name", "")
            loc = item.get("location", "")
            remote = item.get("remote_type", "ONSITE")

            # Filter query
            if q_lower:
                combined = f"{title} {desc} {comp} {loc}".lower()
                if q_lower not in combined:
                    continue

            # Filter roles
            if roles_lower:
                if not any(r in title.lower() for r in roles_lower):
                    continue

            # Filter locations
            if locs_lower:
                loc_match = any(loc_q in loc.lower() for loc_q in locs_lower)
                if not loc_match and not (query.include_remote and remote == "REMOTE"):
                    continue

            results.append(
                RawJob(
                    source=item.get("source", "sample"),
                    source_job_id=item.get("source_job_id"),
                    title=title,
                    company_name=comp,
                    description=desc,
                    location=loc,
                    remote_type=remote,
                    employment_type=item.get("employment_type", "FULL_TIME"),
                    experience_raw=item.get("experience_raw"),
                    salary_raw=item.get("salary_raw"),
                    posted_time_raw=item.get("posted_time_raw"),
                    source_url=item.get("source_url", ""),
                    application_url=item.get("application_url", item.get("source_url", "")),
                    raw_payload=item,
                )
            )

        if query.limit:
            results = results[: query.limit]
        return results

    async def get_job(self, url: str) -> RawJob | None:
        raw_list = self._load_data()
        for item in raw_list:
            if item.get("source_url") == url or item.get("application_url") == url:
                return RawJob(
                    source=item.get("source", "sample"),
                    source_job_id=item.get("source_job_id"),
                    title=item.get("title", ""),
                    company_name=item.get("company_name", ""),
                    description=item.get("description", ""),
                    location=item.get("location"),
                    remote_type=item.get("remote_type", "ONSITE"),
                    employment_type=item.get("employment_type", "FULL_TIME"),
                    experience_raw=item.get("experience_raw"),
                    salary_raw=item.get("salary_raw"),
                    posted_time_raw=item.get("posted_time_raw"),
                    source_url=item.get("source_url", ""),
                    application_url=item.get("application_url", item.get("source_url", "")),
                    raw_payload=item,
                )
        return None

    async def normalize(self, raw: RawJob) -> NormalizedJob:
        norm_title, role_category = normalize_title(raw.title)
        norm_company = raw.company_name.strip()
        norm_loc = normalize_location(raw.location)

        salary_dict = parse_salary_text(raw.salary_raw)
        exp_min, exp_max, exp_text, exp_conf = parse_experience_requirement(raw.experience_raw or raw.description)

        posted_dt, confidence = self.freshness_service.parse_relative_time(raw.posted_time_raw)

        desc = (raw.description or "").strip()
        if not desc:
            desc = f"{raw.title} at {raw.company_name}."
        description_confidence = "HIGH" if len(desc) >= 200 else "LOW"

        # Hash: company + title + location
        import hashlib

        hash_str = f"{norm_company.lower()}|{norm_title.lower()}|{norm_loc.lower()}"
        job_hash = hashlib.sha256(hash_str.encode("utf-8")).hexdigest()

        req_skills = normalize_skills(raw.raw_payload.get("required_skills", []))
        pref_skills = normalize_skills(raw.raw_payload.get("preferred_skills", []))

        quality = calculate_quality_score(
            norm_company,
            raw.salary_raw,
            raw.application_url,
            confidence,
            len(req_skills),
        )

        raw_payload = dict(raw.raw_payload or {})
        raw_payload["experience_text"] = exp_text
        raw_payload["experience_confidence"] = exp_conf
        raw_payload["description_confidence"] = description_confidence

        return NormalizedJob(
            source=raw.source,
            source_job_id=raw.source_job_id,
            title=raw.title,
            normalized_title=norm_title,
            role_category=role_category,
            company_name=raw.company_name,
            normalized_company=norm_company,
            description=desc,
            location=raw.location,
            normalized_location=norm_loc,
            remote_type=raw.remote_type,
            employment_type=raw.employment_type,
            experience_min=exp_min,
            experience_max=exp_max,
            experience_text=exp_text,
            experience_confidence=exp_conf,
            description_confidence=description_confidence,
            salary_min=salary_dict["salary_min"],
            salary_max=salary_dict["salary_max"],
            salary_currency=salary_dict["salary_currency"],
            salary_period=salary_dict["salary_period"],
            salary_raw=raw.salary_raw,
            posted_at=posted_dt,
            posted_at_raw=raw.posted_time_raw,
            posted_at_confidence=confidence,
            source_url=raw.source_url,
            application_url=raw.application_url or raw.source_url,
            job_hash=job_hash,
            required_skills=req_skills,
            preferred_skills=pref_skills,
            quality_score=quality,
            raw_data=raw_payload,
        )

    async def health_check(self) -> bool:
        return self.data_path.exists()
