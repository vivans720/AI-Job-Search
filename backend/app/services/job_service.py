import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.config import settings
from app.models.candidate_profile import CandidateProfile
from app.models.job import Job
from app.models.match import Match
from app.models.saved_job import SavedJob

logger = structlog.get_logger(__name__)

VALID_STATUSES = {
    "DISCOVERED",
    "SAVED",
    "VIEWED",
    "APPLIED",
    "INTERVIEW",
    "REJECTED",
    "OFFER",
    "IGNORED",
}


async def search_jobs_db(
    db: AsyncSession,
    query: str | None = None,
    roles: list[str] | None = None,
    locations: list[str] | None = None,
    experience_min: int | None = None,
    experience_max: int | None = None,
    freshness_hours: int = 24,
    include_remote: bool = True,
    source: str | None = None,
    limit: int | None = 20,
    exclude_unpaid: bool = False,
    exclude_user_id: uuid.UUID | None = None,
    exclude_statuses: list[str] | None = None,
    excluded_companies: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Search database for fresh jobs.
    Freshness rule is strictly backend-enforced (posted_at >= now - freshness_hours).
    Jobs with posted_at=None or low confidence are excluded from the primary fresh feed.
    If exclude_user_id is provided, jobs with status in exclude_statuses (default REJECTED, IGNORED) are excluded.
    In Recall-First architecture: Does NOT drop jobs due to titles or skill mismatch.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=freshness_hours)

    stmt = select(Job).where(
        Job.is_active == True,  # noqa: E712
        Job.posted_at.is_not(None),
        Job.posted_at >= cutoff,
        Job.posted_at_confidence.in_(["HIGH", "MEDIUM"]),
        Job.source != "sample",
    )

    if exclude_user_id is not None:
        statuses_to_exclude = [
            s.upper()
            for s in (
                exclude_statuses
                or ["SAVED", "APPLIED", "INTERVIEW", "OFFER", "REJECTED", "IGNORED"]
            )
        ]
        rejected_subquery = (
            select(SavedJob.job_id)
            .where(
                SavedJob.user_id == exclude_user_id,
                SavedJob.status.in_(statuses_to_exclude),
            )
        )
        stmt = stmt.where(Job.id.not_in(rejected_subquery))

    if source and source.lower() != "all":
        stmt = stmt.where(Job.source == source.lower())

    if experience_max is not None:
        if experience_max == 0:
            # Fresher: jobs accepting 0 experience, or internships, or unspecified entry-level
            stmt = stmt.where(
                (Job.experience_min == 0)
                | (Job.employment_type == "INTERNSHIP")
                | (
                    Job.experience_min.is_(None)
                    & ((Job.experience_max <= 1) | Job.experience_max.is_(None))
                )
            )
        else:
            # Jobs accepting early career candidates with <= experience_max years
            stmt = stmt.where(
                (Job.experience_min <= experience_max)
                | (Job.experience_min.is_(None) & (Job.experience_max <= experience_max))
                | (Job.experience_min.is_(None) & Job.experience_max.is_(None))
                | (Job.employment_type == "INTERNSHIP")
            )

    if experience_min is not None and experience_min > 0:
        # Exclude jobs strictly below experience_min
        stmt = stmt.where(
            (Job.experience_max >= experience_min)
            | (Job.experience_max.is_(None) & (Job.experience_min >= experience_min))
            | (Job.experience_min >= experience_min)
            | (Job.experience_min.is_(None) & Job.experience_max.is_(None))
        )

    if not include_remote:
        stmt = stmt.where(Job.remote_type != "REMOTE")

    stmt = stmt.order_by(desc(Job.posted_at))
    # In Recall-First: Do not prematurely truncate with low SQL LIMIT when post-scoring/ranking is expected.
    if limit is not None and not query and not roles and not locations and not exclude_unpaid:
        # Optimization only when no in-memory filtering or re-ranking is needed
        stmt = stmt.limit(max(limit * 5, 200))

    result = await db.execute(stmt)
    jobs = result.scalars().all()

    # In-memory keyword/role/location filtering if requested
    filtered: list[Job] = []
    query_lower = query.lower() if query else None
    locs_lower = [loc.lower() for loc in locations] if locations else []

    from app.utils.normalization import is_unpaid_salary_text, matches_target_role

    for job in jobs:
        # Exclude affirmatively unpaid positions only if explicitly requested
        if exclude_unpaid:
            is_unpaid = (
                (job.salary_max == 0.0 and job.salary_min == 0.0)
                or (job.salary_raw and is_unpaid_salary_text(job.salary_raw))
                or (isinstance(job.raw_data, dict) and job.raw_data.get("is_unpaid") is True)
            )
            if is_unpaid:
                continue

        if query_lower:
            text_haystack = f"{job.title} {job.description} {' '.join(job.required_skills or [])}".lower()
            if query_lower not in text_haystack:
                continue

        if roles:
            if not matches_target_role(job.title, roles, job.role_category):
                continue

        if locations:
            from app.core.location_taxonomy import match_location_criteria
            if not match_location_criteria(
                job_normalized_location=job.normalized_location,
                job_raw_location=job.location,
                filter_locations=locations,
                job_remote_type=job.remote_type,
            ):
                continue

        if excluded_companies:
            comp_lower = (job.company_name or "").lower().strip()
            if any(
                exc.lower().strip() in comp_lower or comp_lower in exc.lower().strip()
                for exc in excluded_companies
                if exc.strip()
            ):
                continue

        filtered.append(job)

    results_data = []
    for j in filtered:
        age_hours = (
            round((datetime.now(timezone.utc) - j.posted_at).total_seconds() / 3600.0, 1)
            if j.posted_at
            else None
        )
        exp_display = (
            "Internship"
            if j.employment_type == "INTERNSHIP"
            else (
                j.experience_text
                if j.experience_text
                else (
                    f"{j.experience_min}-{j.experience_max} years"
                    if j.experience_min is not None and j.experience_max is not None
                    else (f"{j.experience_min}+ years" if j.experience_min is not None else "Experience unspecified")
                )
            )
        )
        other_sources = []
        if isinstance(j.raw_data, dict) and "other_sources" in j.raw_data:
            other_sources = j.raw_data["other_sources"]

        results_data.append(
            {
                "id": str(j.id),
                "title": j.title,
                "company": j.company_name,
                "company_logo_url": getattr(j, "company_logo_url", None),
                "location": j.location,
                "normalized_location": j.normalized_location,
                "remote_type": j.remote_type,
                "employment_type": j.employment_type or "FULL_TIME",
                "experience": exp_display,
                "experience_min": j.experience_min,
                "experience_max": j.experience_max,
                "experience_confidence": getattr(j, "experience_confidence", "LOW") or "LOW",
                "description_confidence": getattr(j, "description_confidence", "HIGH") or "HIGH",
                "salary": j.salary_raw or "Not disclosed",
                "salary_min": j.salary_min,
                "salary_max": j.salary_max,
                "posted_at": j.posted_at.isoformat() if j.posted_at else None,
                "age_hours": age_hours,
                "source": j.source,
                "application_url": j.application_url,
                "required_skills": j.required_skills or [],
                "quality_score": j.quality_score,
                "other_sources": other_sources,
                "_entity": j,
            }
        )

    if limit is not None:
        return results_data[:limit]
    return results_data


async def get_job_by_id(db: AsyncSession, job_id: uuid.UUID) -> dict[str, Any] | None:
    stmt = select(Job).where(Job.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if not job:
        return None

    # Check for match analysis if available
    match_stmt = select(Match).where(Match.job_id == job_id).order_by(desc(Match.overall_score))
    match_res = await db.execute(match_stmt)
    match = match_res.scalars().first()

    exp_display = (
        "Internship"
        if job.employment_type == "INTERNSHIP"
        else (
            job.experience_text
            if job.experience_text
            else (
                f"{job.experience_min}-{job.experience_max} years"
                if job.experience_min is not None and job.experience_max is not None
                else (f"{job.experience_min}+ years" if job.experience_min is not None else "Experience unspecified")
            )
        )
    )
    other_sources = []
    if isinstance(job.raw_data, dict) and "other_sources" in job.raw_data:
        other_sources = job.raw_data["other_sources"]

    return {
        "id": str(job.id),
        "title": job.title,
        "company": job.company_name,
        "company_logo_url": getattr(job, "company_logo_url", None),
        "location": job.location,
        "remote_type": job.remote_type,
        "employment_type": job.employment_type or "FULL_TIME",
        "experience": exp_display,
        "experience_min": job.experience_min,
        "experience_max": job.experience_max,
        "experience_confidence": getattr(job, "experience_confidence", "LOW") or "LOW",
        "description_confidence": getattr(job, "description_confidence", "HIGH") or "HIGH",
        "salary": job.salary_raw or "Not disclosed",
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "salary_raw": job.salary_raw or "Not disclosed",
        "posted_at": job.posted_at.isoformat() if job.posted_at else None,
        "posted_at_confidence": job.posted_at_confidence,
        "source": job.source,
        "source_url": job.source_url,
        "application_url": job.application_url,
        "description": job.description,
        "required_skills": job.required_skills or [],
        "preferred_skills": job.preferred_skills or [],
        "quality_score": job.quality_score,
        "other_sources": other_sources,
        "match": {
            "overall_score": match.overall_score,
            "skill_score": match.skill_score,
            "semantic_score": match.semantic_score,
            "matched_skills": match.matched_skills,
            "missing_skills": match.missing_skills,
            "explanation": match.explanation,
            "recommendation": match.recommendation,
        }
        if match
        else None,
    }


async def save_or_update_job_status(
    db: AsyncSession,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    status: str,
    notes: str | None = None,
) -> dict[str, Any]:
    upper_status = status.upper()
    if upper_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {sorted(list(VALID_STATUSES))}")

    # Check if job exists
    job_stmt = select(Job).where(Job.id == job_id)
    job_res = await db.execute(job_stmt)
    job = job_res.scalar_one_or_none()
    if not job:
        raise ValueError(f"Job with ID {job_id} not found")

    stmt = select(SavedJob).where(SavedJob.user_id == user_id, SavedJob.job_id == job_id)
    result = await db.execute(stmt)
    saved = result.scalar_one_or_none()

    if saved:
        saved.status = upper_status
        if notes is not None:
            saved.notes = notes
    else:
        saved = SavedJob(
            id=uuid.uuid4(),
            user_id=user_id,
            job_id=job_id,
            status=upper_status,
            notes=notes,
        )
        db.add(saved)

    await db.commit()
    await db.refresh(saved)
    logger.info("job_status_updated", user_id=str(user_id), job_id=str(job_id), status=upper_status)

    return {
        "id": str(saved.id),
        "job_id": str(saved.job_id),
        "title": job.title,
        "company": job.company_name,
        "status": saved.status,
        "notes": saved.notes,
        "application_url": job.application_url,
        "updated_at": saved.updated_at.isoformat() if saved.updated_at else datetime.now(timezone.utc).isoformat(),
    }


async def unsave_job(
    db: AsyncSession,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
) -> bool:
    """Remove a job from saved/tracked jobs for user."""
    stmt = select(SavedJob).where(SavedJob.user_id == user_id, SavedJob.job_id == job_id)
    result = await db.execute(stmt)
    saved = result.scalar_one_or_none()
    if not saved:
        return False

    await db.delete(saved)
    await db.commit()
    logger.info("job_unsaved", user_id=str(user_id), job_id=str(job_id))
    return True


async def batch_save_or_update_job_status(
    db: AsyncSession,
    user_id: uuid.UUID,
    job_ids: list[uuid.UUID],
    status: str,
    notes: str | None = None,
) -> dict[str, Any]:
    upper_status = status.upper()
    if upper_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {sorted(list(VALID_STATUSES))}")

    if not job_ids:
        return {"updated_count": 0, "status": upper_status, "job_ids": []}

    existing_stmt = select(SavedJob).where(
        SavedJob.user_id == user_id,
        SavedJob.job_id.in_(job_ids),
    )
    existing_res = await db.execute(existing_stmt)
    existing_map = {s.job_id: s for s in existing_res.scalars().all()}

    updated_ids: list[str] = []
    for j_id in job_ids:
        if j_id in existing_map:
            saved = existing_map[j_id]
            saved.status = upper_status
            if notes is not None:
                saved.notes = notes
        else:
            saved = SavedJob(
                id=uuid.uuid4(),
                user_id=user_id,
                job_id=j_id,
                status=upper_status,
                notes=notes,
            )
            db.add(saved)
        updated_ids.append(str(j_id))

    await db.commit()
    logger.info("batch_job_status_updated", user_id=str(user_id), count=len(updated_ids), status=upper_status)

    return {
        "updated_count": len(updated_ids),
        "status": upper_status,
        "job_ids": updated_ids,
    }


async def get_saved_jobs_for_user(
    db: AsyncSession, user_id: uuid.UUID, status: str | None = None
) -> list[dict[str, Any]]:
    # Get candidate profile id if exists
    profile_stmt = select(CandidateProfile.id).where(CandidateProfile.user_id == user_id)
    profile_res = await db.execute(profile_stmt)
    profile_id = profile_res.scalar_one_or_none()

    if profile_id:
        stmt = (
            select(SavedJob, Job, Match)
            .join(Job, SavedJob.job_id == Job.id)
            .outerjoin(
                Match,
                (Match.job_id == Job.id) & (Match.profile_id == profile_id),
            )
            .where(SavedJob.user_id == user_id, Job.source != "sample")
        )
    else:
        stmt = (
            select(SavedJob, Job, None)
            .join(Job, SavedJob.job_id == Job.id)
            .where(SavedJob.user_id == user_id, Job.source != "sample")
        )

    if status:
        stmt = stmt.where(SavedJob.status == status.upper())

    stmt = stmt.order_by(desc(SavedJob.updated_at))
    result = await db.execute(stmt)
    rows = result.all()

    saved_list = []
    for saved, job, match in rows:
        saved_list.append(
            {
                "saved_id": str(saved.id),
                "job_id": str(job.id),
                "title": job.title,
                "company": job.company_name,
                "location": job.location,
                "salary": job.salary_raw or "Not disclosed",
                "status": saved.status,
                "notes": saved.notes,
                "application_url": job.application_url,
                "posted_at": job.posted_at.isoformat() if job.posted_at else None,
                "updated_at": saved.updated_at.isoformat(),
                "match_score": match.overall_score if match else None,
                "match_recommendation": match.recommendation if match else None,
                "match_explanation": match.explanation if match else None,
            }
        )
    return saved_list


async def get_job_facets_db(
    db: AsyncSession,
    query: str | None = None,
    freshness_hours: int = 24,
    locations: list[str] | None = None,
    source: str | None = None,
    employment_type: str | None = None,
    experience_min: int | None = None,
    experience_max: int | None = None,
    exclude_user_id: uuid.UUID | None = None,
    exclude_statuses: list[str] | None = None,
    excluded_companies: list[str] | None = None,
) -> dict[str, Any]:
    """
    Compute global facet counts across all active fresh listings.
    Supports contextual narrowing when filters (e.g. locations, source, experience) are active.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=freshness_hours)

    stmt = select(Job).where(
        Job.is_active == True,  # noqa: E712
        Job.posted_at.is_not(None),
        Job.posted_at >= cutoff,
        Job.posted_at_confidence.in_(["HIGH", "MEDIUM"]),
        Job.source != "sample",
    )

    if source:
        stmt = stmt.where(Job.source == source.lower())

    if exclude_user_id is not None:
        statuses_to_exclude = [
            s.upper()
            for s in (
                exclude_statuses
                or ["SAVED", "APPLIED", "INTERVIEW", "OFFER", "REJECTED", "IGNORED"]
            )
        ]
        rejected_subquery = (
            select(SavedJob.job_id)
            .where(
                SavedJob.user_id == exclude_user_id,
                SavedJob.status.in_(statuses_to_exclude),
            )
        )
        stmt = stmt.where(Job.id.not_in(rejected_subquery))

    res = await db.execute(stmt)
    jobs = res.scalars().all()

    query_lower = query.lower().strip() if query and query.strip() else None
    locs_lower = [loc.lower() for loc in locations] if locations else []

    from app.core.location_taxonomy import match_location_criteria, parse_location_entities

    def matches_location(job: Job) -> bool:
        if not locations:
            return True
        return match_location_criteria(
            job_normalized_location=job.normalized_location,
            job_raw_location=job.location,
            filter_locations=locations,
            job_remote_type=job.remote_type,
        )

    def matches_employment_type(job: Job) -> bool:
        if not employment_type or employment_type.upper() == "ALL":
            return True
        is_intern = job.employment_type == "INTERNSHIP" or "intern" in (job.title or "").lower() or (job.experience_text and "intern" in job.experience_text.lower())
        if employment_type.upper() == "INTERNSHIPS":
            return is_intern
        if employment_type.upper() == "JOBS":
            return not is_intern
        return True

    def matches_experience(job: Job) -> bool:
        min_exp = job.experience_min
        max_exp = job.experience_max
        if experience_max == 0:
            is_intern = job.employment_type == "INTERNSHIP" or (job.experience_text and "intern" in job.experience_text.lower())
            is_fresher_min = min_exp == 0
            is_fresher_text = bool(job.experience_text and "fresher" in job.experience_text.lower())
            is_unspecified = min_exp is None and (max_exp is None or max_exp <= 1)
            return is_intern or is_fresher_min or is_fresher_text or is_unspecified
        if experience_max is not None:
            eff_min = min_exp or 0
            if eff_min > experience_max and (job.employment_type != "INTERNSHIP"):
                return False
        if experience_min is not None and experience_min > 0:
            eff_max = max_exp if max_exp is not None else 99
            eff_min = min_exp if min_exp is not None else 0
            if eff_max < experience_min and eff_min < experience_min:
                return False
        return True

    location_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    type_counts = {"ALL": 0, "JOBS": 0, "INTERNSHIPS": 0}
    exp_counts = {"FRESHER": 0, "0_1": 0, "1_2": 0, "2_3": 0, "3_PLUS": 0}

    for job in jobs:
        if excluded_companies:
            comp_lower = (job.company_name or "").lower().strip()
            if any(
                exc.lower().strip() in comp_lower or comp_lower in exc.lower().strip()
                for exc in excluded_companies
                if exc.strip()
            ):
                continue

        if query_lower:
            haystack = f"{job.title} {job.description} {' '.join(job.required_skills or [])}".lower()
            if query_lower not in haystack:
                continue

        # Location facet count aggregated by canonical entity
        entities = parse_location_entities(job.normalized_location or job.location)
        for ent in entities:
            if ent.name and ent.name != "Unknown":
                location_counts[ent.name] = location_counts.get(ent.name, 0) + 1

        # Check if job satisfies current active location, employment_type, and experience filters
        loc_ok = matches_location(job)
        type_ok = matches_employment_type(job)
        exp_ok = matches_experience(job)

        is_intern = job.employment_type == "INTERNSHIP" or "intern" in (job.title or "").lower() or (job.experience_text and "intern" in job.experience_text.lower())

        # Total count satisfies all active filters
        if loc_ok and type_ok and exp_ok:
            type_counts["ALL"] += 1

        # Role Type counts satisfy location and experience filters
        if loc_ok and exp_ok:
            if is_intern:
                type_counts["INTERNSHIPS"] += 1
            else:
                type_counts["JOBS"] += 1

        # Source counts satisfy location, type, and experience filters
        if loc_ok and type_ok and exp_ok:
            src = (job.source or "").lower()
            if src:
                source_counts[src] = source_counts.get(src, 0) + 1

        # Experience counts satisfy location and type filters
        if loc_ok and type_ok:
            min_exp = job.experience_min
            max_exp = job.experience_max
            is_fresher = (
                min_exp == 0
                or is_intern
                or (job.experience_text and "fresher" in job.experience_text.lower())
                or (min_exp is None and (max_exp is None or max_exp <= 1))
            )
            if is_fresher:
                exp_counts["FRESHER"] += 1

            if (min_exp is not None and min_exp <= 1) or (max_exp is not None and max_exp <= 1) or is_intern:
                exp_counts["0_1"] += 1

            effective_min = min_exp or 0
            effective_max = max_exp if max_exp is not None else effective_min
            if (effective_min <= 2 and effective_max >= 1) or (job.experience_text and any(k in job.experience_text for k in ["1-2", "0-2"])):
                exp_counts["1_2"] += 1

            if (effective_min <= 3 and effective_max >= 2) or (job.experience_text and any(k in job.experience_text for k in ["2-3", "1-3"])):
                exp_counts["2_3"] += 1

            if (effective_max >= 3 or effective_min >= 3):
                exp_counts["3_PLUS"] += 1

    return {
        "total": type_counts["ALL"],
        "types": type_counts,
        "sources": source_counts,
        "locations": location_counts,
        "experience": exp_counts,
    }


async def get_jobs_by_ids(
    db: AsyncSession, job_ids: list[uuid.UUID]
) -> list[dict[str, Any]]:
    """Retrieve multiple jobs by IDs."""
    if not job_ids:
        return []
    results = []
    for jid in job_ids:
        j = await get_job_by_id(db, jid)
        if j:
            results.append(j)
    return results


async def semantic_search_jobs_db(
    db: AsyncSession,
    query: str,
    limit: int = 10,
    freshness_hours: int = 24,
) -> list[dict[str, Any]]:
    """
    Search jobs by semantic similarity using pgvector cosine distance.
    Filters by freshness_hours and active status.
    """
    from app.intelligence.embedding_provider import get_embedding_provider
    query_vector = get_embedding_provider().embed(query)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=freshness_hours)
    stmt = (
        select(Job)
        .where(
            Job.is_active == True,  # noqa: E712
            Job.posted_at.is_not(None),
            Job.posted_at >= cutoff,
            Job.embedding.is_not(None),
            Job.source != "sample",
        )
        .order_by(Job.embedding.cosine_distance(query_vector))
        .limit(limit)
    )
    res = await db.execute(stmt)
    jobs = res.scalars().all()

    results = []
    for job in jobs:
        results.append(
            {
                "id": str(job.id),
                "title": job.title,
                "company": job.company_name,
                "location": job.location,
                "remote_type": job.remote_type,
                "employment_type": job.employment_type or "FULL_TIME",
                "salary": job.salary_raw or "Not disclosed",
                "posted_at": job.posted_at.isoformat() if job.posted_at else None,
                "source": job.source,
                "application_url": job.application_url,
                "required_skills": job.required_skills or [],
                "quality_score": job.quality_score,
            }
        )
    return results


async def record_search_query(
    db: AsyncSession,
    user_id: uuid.UUID,
    query_text: str | None = None,
    structured_query: dict[str, Any] | None = None,
    sources_used: list[str] | None = None,
    total_discovered: int = 0,
    filtered_by_freshness: int = 0,
    deduplicated: int = 0,
    matched: int = 0,
    fresh_results: int = 0,
) -> SearchRecord:
    """Record a search query execution into search history."""
    from app.models.search import SearchRecord

    record = SearchRecord(
        id=uuid.uuid4(),
        user_id=user_id,
        query_text=query_text,
        structured_query=structured_query or {},
        sources_used=sources_used or [],
        total_discovered=total_discovered,
        filtered_by_freshness=filtered_by_freshness,
        deduplicated=deduplicated,
        matched=matched,
        fresh_results=fresh_results,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_search_history(
    db: AsyncSession,
    user_id: uuid.UUID,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Retrieve search history for user."""
    from app.models.search import SearchRecord

    stmt = (
        select(SearchRecord)
        .where(SearchRecord.user_id == user_id)
        .order_by(desc(SearchRecord.created_at))
        .limit(limit)
    )
    res = await db.execute(stmt)
    records = res.scalars().all()

    return [
        {
            "id": str(r.id),
            "query_text": r.query_text,
            "structured_query": r.structured_query,
            "sources_used": r.sources_used,
            "total_discovered": r.total_discovered,
            "fresh_results": r.fresh_results,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]

