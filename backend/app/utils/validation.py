import structlog
from app.sources.base import NormalizedJob

logger = structlog.get_logger(__name__)


def validate_normalized_job(job: NormalizedJob) -> tuple[bool, str | None]:
    """
    Validates normalized job schema integrity before database persistence.
    Guarantees required fields, valid URLs, meaningful title/company, and sufficient description.

    Returns:
        tuple of (is_valid: bool, reason: str | None)
    """
    if not job.title or len(job.title.strip()) < 3:
        return False, "title_too_short_or_empty"

    if not job.company_name or len(job.company_name.strip()) < 2:
        return False, "company_name_too_short_or_empty"

    if not job.source_url or not (job.source_url.startswith("http://") or job.source_url.startswith("https://")):
        return False, "invalid_source_url"

    if not job.application_url or not (job.application_url.startswith("http://") or job.application_url.startswith("https://")):
        return False, "invalid_application_url"

    if not job.description or len(job.description.strip()) < 10:
        return False, "description_too_short_or_empty"

    if not job.job_hash or len(job.job_hash.strip()) < 8:
        return False, "invalid_or_missing_job_hash"

    return True, None
