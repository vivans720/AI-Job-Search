import hashlib
import re
from difflib import SequenceMatcher
from typing import Sequence
import numpy as np
import structlog

from app.sources.base import NormalizedJob

logger = structlog.get_logger(__name__)


def compute_job_hash(
    company: str,
    title: str,
    location: str,
    employment_type: str = "FULL_TIME",
    source_job_id: str | None = None,
) -> str:
    """
    Generates a robust, multi-dimensional fingerprint to prevent structural hash collisions.
    """
    def clean(val: str | None) -> str:
        if not val:
            return "generic"
        return re.sub(r"[^a-z0-9]", "", val.strip().lower())

    c_comp = clean(company)
    c_titl = clean(title)
    c_locn = clean(location)
    c_empt = clean(employment_type)
    c_sjid = clean(source_job_id)

    raw_key = f"{c_comp}|{c_titl}|{c_locn}|{c_empt}|{c_sjid}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def compute_description_similarity(desc1: str, desc2: str) -> float:
    """Level 4: Fast token-based similarity approximation followed by ratio."""
    tokens1 = set(desc1.lower().split())
    tokens2 = set(desc2.lower().split())
    if not tokens1 or not tokens2:
        return 0.0

    # Jaccard pre-filter
    intersection = tokens1.intersection(tokens2)
    union = tokens1.union(tokens2)
    jaccard = len(intersection) / len(union)

    if jaccard < 0.65:
        return jaccard

    # Refined sequence ratio on first 500 characters
    return SequenceMatcher(None, desc1[:500].lower(), desc2[:500].lower()).ratio()


def cosine_similarity(v1: Sequence[float], v2: Sequence[float]) -> float:
    """Level 5: Embedding cosine similarity."""
    a = np.array(v1)
    b = np.array(v2)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    if norm == 0:
        return 0.0
    return float(np.dot(a, b) / norm)


def is_direct_company_url(url: str) -> bool:
    """Returns True if the URL appears to be a direct company career portal rather than aggregator."""
    lower = url.lower()
    aggregators = [
        "naukri.com",
        "internshala.com",
        "linkedin.com",
        "indeed.com",
        "instahyre.com",
        "wellfound.com",
        "cutshort.io",
    ]
    if any(agg in lower for agg in aggregators):
        return False
    return any(keyword in lower for keyword in ["careers", "jobs", "apply", "greenhouse.io", "lever.co", "workday.com", "ashbyhq.com"])


def select_canonical_job(job1: NormalizedJob, job2: NormalizedJob) -> tuple[NormalizedJob, NormalizedJob]:
    """
    Chooses the better canonical representation between two duplicates.
    Preserves source metadata from both records so no source information is lost.
    Returns (canonical, duplicate).
    """
    job1_is_direct = is_direct_company_url(job1.application_url)
    job2_is_direct = is_direct_company_url(job2.application_url)

    if job1_is_direct and not job2_is_direct:
        better, lesser = job1, job2
    elif job2_is_direct and not job1_is_direct:
        better, lesser = job2, job1
    elif len(job1.description) > len(job2.description) + 100:
        better, lesser = job1, job2
    elif len(job2.description) > len(job1.description) + 100:
        better, lesser = job2, job1
    elif job1.posted_at and job2.posted_at:
        if job1.posted_at >= job2.posted_at:
            better, lesser = job1, job2
        else:
            better, lesser = job2, job1
    else:
        better, lesser = job1, job2

    # Preserve lesser source metadata without loss
    if not isinstance(better.raw_data, dict):
        better.raw_data = {}
    other_sources = better.raw_data.setdefault("other_sources", [])
    lesser_info = {
        "source": lesser.source,
        "source_job_id": lesser.source_job_id,
        "source_url": lesser.source_url,
        "application_url": lesser.application_url,
        "posted_at": lesser.posted_at.isoformat() if lesser.posted_at else None,
        "raw_data": lesser.raw_data,
    }
    if not any(s.get("source_url") == lesser.source_url for s in other_sources):
        other_sources.append(lesser_info)

    return better, lesser


class DeduplicationService:
    """
    Multi-tier deduplication engine (5 Levels).
    Merges duplicate job listings into canonical items.
    """

    def __init__(self, description_threshold: float = 0.85, embedding_threshold: float = 0.92):
        self.desc_threshold = description_threshold
        self.embed_threshold = embedding_threshold

    def are_duplicates(
        self,
        job1: NormalizedJob,
        job2: NormalizedJob,
        embed1: list[float] | None = None,
        embed2: list[float] | None = None,
    ) -> tuple[bool, str]:
        """
        Tests if job1 and job2 are duplicates across 5 levels.
        Returns (is_duplicate, reason).
        """
        # Level 1: Exact URL match
        if (
            (job1.source_url and job1.source_url == job2.source_url)
            or (job1.application_url and job1.application_url == job2.application_url)
        ):
            return True, "LEVEL_1_EXACT_URL"

        # Level 2: Source + source_job_id match
        if (
            job1.source == job2.source
            and job1.source_job_id
            and job1.source_job_id == job2.source_job_id
        ):
            return True, "LEVEL_2_SOURCE_JOB_ID"

        # Level 3: Normalized multi-dimensional metadata match
        hash1 = compute_job_hash(
            job1.normalized_company,
            job1.normalized_title,
            job1.normalized_location,
            job1.employment_type or "FULL_TIME",
            job1.source_job_id,
        )
        hash2 = compute_job_hash(
            job2.normalized_company,
            job2.normalized_title,
            job2.normalized_location,
            job2.employment_type or "FULL_TIME",
            job2.source_job_id,
        )
        if hash1 == hash2:
            return True, "LEVEL_3_NORMALIZED_METADATA"

        # Level 4: Fuzzy description similarity
        if job1.normalized_company == job2.normalized_company:
            sim = compute_description_similarity(job1.description, job2.description)
            if sim >= self.desc_threshold:
                return True, f"LEVEL_4_FUZZY_DESCRIPTION ({round(sim, 2)})"

        # Level 5: Embedding cosine similarity
        if embed1 and embed2 and job1.normalized_company == job2.normalized_company:
            sim = cosine_similarity(embed1, embed2)
            if sim >= self.embed_threshold:
                return True, f"LEVEL_5_EMBEDDING_SIMILARITY ({round(sim, 2)})"

        return False, "UNIQUE"

    def deduplicate_batch(
        self,
        jobs: list[NormalizedJob],
        embeddings: list[list[float]] | None = None,
    ) -> tuple[list[NormalizedJob], list[dict[str, str]]]:
        """
        Takes a list of NormalizedJob items and deduplicates them.
        Returns (canonical_jobs, duplicate_audit_log).
        """
        if not jobs:
            return [], []

        canonical: list[NormalizedJob] = []
        canonical_embeddings: list[list[float]] = []
        audit_log: list[dict[str, str]] = []

        for i, job in enumerate(jobs):
            current_embed = embeddings[i] if embeddings and i < len(embeddings) else None
            is_dup = False

            for c_idx, existing in enumerate(canonical):
                existing_embed = (
                    canonical_embeddings[c_idx] if canonical_embeddings else None
                )
                dup_found, reason = self.are_duplicates(
                    job, existing, current_embed, existing_embed
                )

                if dup_found:
                    is_dup = True
                    better, lesser = select_canonical_job(existing, job)
                    canonical[c_idx] = better
                    if current_embed and better == job:
                        canonical_embeddings[c_idx] = current_embed

                    audit_log.append(
                        {
                            "duplicate_title": lesser.title,
                            "duplicate_source": lesser.source,
                            "canonical_title": better.title,
                            "canonical_source": better.source,
                            "reason": reason,
                        }
                    )
                    break

            if not is_dup:
                canonical.append(job)
                if current_embed:
                    canonical_embeddings.append(current_embed)

        logger.info(
            "deduplication_completed",
            input_count=len(jobs),
            canonical_count=len(canonical),
            duplicates_removed=len(audit_log),
        )
        return canonical, audit_log


_default_dedup_service: DeduplicationService | None = None

DedupService = DeduplicationService


def get_dedup_service() -> DeduplicationService:
    global _default_dedup_service
    if _default_dedup_service is None:
        _default_dedup_service = DeduplicationService()
    return _default_dedup_service
