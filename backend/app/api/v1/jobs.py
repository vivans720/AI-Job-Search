import math
import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.database import get_db
from app.models.job import Job
from app.models.saved_job import SavedJob
from app.schemas.job import (
    BatchJobStatusResponse,
    BatchJobStatusUpdateRequest,
    JobDetail,
    JobListItem,
    JobRankRequest,
    JobStatusUpdateRequest,
    SavedJobResponse,
)
from app.schemas.match import MatchBreakdown, WhyThisJobResponse
from app.services.job_service import (
    batch_save_or_update_job_status,
    get_job_by_id,
    get_job_facets_db,
    get_saved_jobs_for_user,
    save_or_update_job_status,
    search_jobs_db,
)
from app.services.matching_service import get_matching_service
from app.services.preference_service import get_or_create_preferences
from app.services.profile_service import get_candidate_profile
from app.services.user_service import get_or_create_default_user

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["jobs"])


@router.get("/jobs", response_model=list[JobListItem])
async def search_jobs_endpoint(
    response: Response,
    query: str | None = Query(None, description="Search term for title/skills"),
    role: list[str] | None = Query(None, description="Filter by role(s)"),
    location: list[str] | None = Query(None, description="Filter by location(s)"),
    experience_min: int | None = Query(None, description="Minimum experience required"),
    experience_max: int | None = Query(None, description="Maximum experience required"),
    freshness_hours: int = Query(24, description="Freshness window in hours (default 24)"),
    include_remote: bool = Query(True, description="Include remote opportunities"),
    strict_location: bool = Query(False, description="Enforce strict location match against preferred locations"),
    sort_by: str = Query("match", description="Sort by 'match', 'freshness', or 'salary'"),
    source: str | None = Query(None, description="Filter by source board ('internshala', 'naukri', 'linkedin')"),
    exclude_unpaid: bool = Query(False, description="Filter out affirmatively unpaid positions"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    limit: int | None = Query(None, ge=1, le=200, description="Legacy limit override"),
    exclude_rejected: bool = Query(True, description="Exclude saved, tracked, and rejected jobs"),
    db: AsyncSession = Depends(get_db),
):
    """
    Search fresh jobs (strictly <= freshness_hours) and score them against candidate profile.
    In Recall-First architecture: Does NOT destructively drop jobs due to low AI scores or title mismatches.
    Returns paginated items and populates X-Total-Count, X-Page, X-Page-Size, X-Total-Pages headers.
    """
    user = await get_or_create_default_user(db)
    profile = await get_candidate_profile(db, user.id)
    prefs = await get_or_create_preferences(db, user.id)

    matching_svc = get_matching_service()

    effective_page_size = limit if limit is not None else page_size

    # In recall-first: experience filters are only applied if explicitly requested by user in query
    effective_exp_min = experience_min
    effective_exp_max = experience_max

    # Fetch all locations unless explicitly filtered by query parameter
    effective_locations = location
    effective_include_remote = include_remote if include_remote is not None else True
    exclude_statuses = ["SAVED", "APPLIED", "INTERVIEW", "OFFER", "REJECTED", "IGNORED"] if exclude_rejected else None

    jobs_data = await search_jobs_db(
        db=db,
        query=query,
        roles=role,
        locations=effective_locations,
        experience_min=effective_exp_min,
        experience_max=effective_exp_max,
        freshness_hours=freshness_hours,
        include_remote=effective_include_remote,
        source=source,
        limit=None,
        exclude_unpaid=exclude_unpaid,
        exclude_user_id=user.id if exclude_rejected else None,
        exclude_statuses=exclude_statuses,
    )

    # Pre-fetch saved statuses for user
    saved_stmt = select(SavedJob.job_id, SavedJob.status).where(SavedJob.user_id == user.id)
    saved_res = await db.execute(saved_stmt)
    saved_map = {row[0]: row[1] for row in saved_res.all()}

    results: list[dict[str, Any]] = []

    for item in jobs_data:
        job_id = uuid.UUID(item["id"])
        job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one_or_none()
        if not job:
            continue

        match_info = None
        if profile:
            eval_res = matching_svc.evaluate_job(
                job, profile, prefs, strict_location=strict_location
            )
            match_info = MatchBreakdown(
                overall_score=eval_res["overall_score"],
                skill_score=eval_res["skill_score"],
                semantic_score=eval_res["semantic_score"],
                experience_score=eval_res["experience_score"],
                role_score=eval_res["role_score"],
                location_score=eval_res["location_score"],
                preference_score=eval_res["preference_score"],
                matched_skills=eval_res["matched_skills"],
                missing_skills=eval_res["missing_skills"],
                transferable_skills=eval_res["transferable_skills"],
                required_skills=eval_res.get("required_skills"),
                preferred_skills=eval_res.get("preferred_skills"),
                transferable_details=eval_res.get("transferable_details", []),
                experience_eligible=eval_res.get("experience_eligible", True),
                location_eligible=eval_res.get("location_eligible", True),
                confidence=eval_res.get("confidence", 1.0),
                confidence_label=eval_res.get("confidence_label", "HIGH"),
                explanation=eval_res["explanation"],
                recommendation=eval_res["recommendation"],
            )

        job_dict = dict(item)
        job_dict["match"] = match_info
        job_dict["saved_status"] = saved_map.get(job_id)
        results.append(job_dict)

    if sort_by == "match" and profile:
        results.sort(
            key=lambda x: (
                x["match"].overall_score if x.get("match") else 0.0,
                x.get("quality_score", 0.0),
            ),
            reverse=True,
        )
    elif sort_by == "freshness":
        results.sort(
            key=lambda x: x.get("posted_at") or "",
            reverse=True,
        )
    elif sort_by == "salary":
        results.sort(
            key=lambda x: (
                x.get("salary_max") or 0.0,
                x.get("salary_min") or 0.0,
            ),
            reverse=True,
        )

    total_count = len(results)
    total_pages = math.ceil(total_count / effective_page_size) if total_count > 0 else 1
    start_idx = (page - 1) * effective_page_size
    end_idx = start_idx + effective_page_size
    paged_results = results[start_idx:end_idx]

    response.headers["X-Total-Count"] = str(total_count)
    response.headers["X-Page"] = str(page)
    response.headers["X-Page-Size"] = str(effective_page_size)
    response.headers["X-Total-Pages"] = str(total_pages)

    return paged_results


@router.get("/jobs/facets")
async def get_job_facets_endpoint(
    query: str | None = Query(None, description="Search term"),
    freshness_hours: int = Query(24, description="Freshness window in hours"),
    location: list[str] | None = Query(None, description="Filter by location(s)"),
    source: str | None = Query(None, description="Filter by source board"),
    employment_type: str | None = Query(None, description="Filter by employment type ('JOBS', 'INTERNSHIPS')"),
    experience_min: int | None = Query(None, description="Minimum experience required"),
    experience_max: int | None = Query(None, description="Maximum experience required"),
    exclude_rejected: bool = Query(True, description="Exclude saved and rejected jobs"),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns global facet aggregations (locations, sources, employment types, experience)
    for all active fresh listings in database, dynamically scoped by active filters.
    """
    user = await get_or_create_default_user(db)
    exclude_statuses = ["SAVED", "APPLIED", "INTERVIEW", "OFFER", "REJECTED", "IGNORED"] if exclude_rejected else None
    return await get_job_facets_db(
        db=db,
        query=query,
        freshness_hours=freshness_hours,
        locations=location,
        source=source,
        employment_type=employment_type,
        experience_min=experience_min,
        experience_max=experience_max,
        exclude_user_id=user.id if exclude_rejected else None,
        exclude_statuses=exclude_statuses,
    )


@router.get("/jobs/saved", response_model=list[SavedJobResponse])
async def list_saved_jobs_endpoint(
    status: str | None = Query(None, description="Optional status filter"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve saved jobs and tracked application stages."""
    user = await get_or_create_default_user(db)
    return await get_saved_jobs_for_user(db, user.id, status=status)


@router.get("/jobs/{job_id}", response_model=JobDetail)
async def get_job_detail_endpoint(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full details of a specific job with match breakdown and application status."""
    try:
        parsed_id = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    job_data = await get_job_by_id(db, parsed_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    user = await get_or_create_default_user(db)
    profile = await get_candidate_profile(db, user.id)
    prefs = await get_or_create_preferences(db, user.id)

    # Check saved status
    saved_stmt = select(SavedJob).where(SavedJob.user_id == user.id, SavedJob.job_id == parsed_id)
    saved_res = await db.execute(saved_stmt)
    saved = saved_res.scalar_one_or_none()

    match_info = None
    if profile:
        job = (await db.execute(select(Job).where(Job.id == parsed_id))).scalar_one_or_none()
        if job:
            eval_res = get_matching_service().evaluate_job(job, profile, prefs)
            match_info = MatchBreakdown(
                overall_score=eval_res["overall_score"],
                skill_score=eval_res["skill_score"],
                semantic_score=eval_res["semantic_score"],
                experience_score=eval_res["experience_score"],
                role_score=eval_res["role_score"],
                location_score=eval_res["location_score"],
                preference_score=eval_res["preference_score"],
                matched_skills=eval_res["matched_skills"],
                missing_skills=eval_res["missing_skills"],
                transferable_skills=eval_res["transferable_skills"],
                required_skills=eval_res.get("required_skills"),
                preferred_skills=eval_res.get("preferred_skills"),
                transferable_details=eval_res.get("transferable_details", []),
                experience_eligible=eval_res.get("experience_eligible", True),
                location_eligible=eval_res.get("location_eligible", True),
                explanation=eval_res["explanation"],
                recommendation=eval_res["recommendation"],
            )

    job_detail = dict(job_data)
    job_detail["match"] = match_info
    job_detail["saved_status"] = saved.status if saved else None
    return job_detail


@router.post("/jobs/{job_id}/match", response_model=MatchBreakdown)
async def calculate_match_endpoint(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Calculates and persists 6-dimension match analysis for a job."""
    try:
        parsed_id = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    job = (await db.execute(select(Job).where(Job.id == parsed_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    user = await get_or_create_default_user(db)
    profile = await get_candidate_profile(db, user.id)
    if not profile:
        raise HTTPException(status_code=400, detail="Candidate profile not found. Please upload resume first.")

    prefs = await get_or_create_preferences(db, user.id)
    match_rec = await get_matching_service().get_or_calculate_match(db, job, profile, prefs)

    req_set = set(job.required_skills or [])
    pref_set = set(job.preferred_skills or [])
    return MatchBreakdown(
        overall_score=match_rec.overall_score,
        skill_score=match_rec.skill_score,
        semantic_score=match_rec.semantic_score,
        experience_score=match_rec.experience_score,
        role_score=match_rec.role_score,
        location_score=match_rec.location_score,
        preference_score=match_rec.preference_score,
        matched_skills=match_rec.matched_skills,
        missing_skills=match_rec.missing_skills,
        transferable_skills=match_rec.transferable_skills,
        required_skills={"matched": [s for s in match_rec.matched_skills if s in req_set], "missing": match_rec.missing_skills},
        preferred_skills={"matched": [s for s in match_rec.matched_skills if s in pref_set], "missing": [s for s in pref_set if s not in match_rec.matched_skills]},
        explanation=match_rec.explanation,
        recommendation=match_rec.recommendation,
    )


@router.get("/jobs/{job_id}/why", response_model=WhyThisJobResponse)
async def get_why_this_job_endpoint(
    job_id: str,
    use_llm: bool = Query(True, description="Enable LLM rationale synthesis"),
    db: AsyncSession = Depends(get_db),
):
    """Phase 45: 'Why This Job?' Engine — Returns evidence breakdown, verdicts, and talking points."""
    try:
        parsed_id = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    job = (await db.execute(select(Job).where(Job.id == parsed_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    user = await get_or_create_default_user(db)
    profile = await get_candidate_profile(db, user.id)
    if not profile:
        raise HTTPException(status_code=400, detail="Candidate profile not found. Please upload resume first.")

    prefs = await get_or_create_preferences(db, user.id)
    eval_res = get_matching_service().evaluate_job(job, profile, prefs)

    from app.intelligence.service import AIService
    ai_service = AIService()

    candidate_years = float(profile.experience_years or 0.0)
    job_exp_min = float(job.experience_min) if job.experience_min is not None else None
    job_exp_max = float(job.experience_max) if job.experience_max is not None else None

    return await ai_service.generate_why_this_job(
        job_id=str(job.id),
        job_title=job.title,
        company_name=job.company_name,
        match_breakdown=eval_res,
        candidate_years=candidate_years,
        job_exp_min=job_exp_min,
        job_exp_max=job_exp_max,
        job_location=job.location or "India",
        job_remote_type=job.remote_type,
        candidate_preferred_locations=profile.preferred_locations,
        candidate_remote_allowed=getattr(profile, "remote_preference", True),
        use_llm=use_llm,
    )



@router.post("/jobs/rank")
async def rank_jobs_endpoint(
    req: JobRankRequest,
    db: AsyncSession = Depends(get_db),
):
    """Ranks provided job IDs by match score against candidate profile."""
    user = await get_or_create_default_user(db)
    profile = await get_candidate_profile(db, user.id)
    if not profile:
        raise HTTPException(status_code=400, detail="Candidate profile not found")

    valid_ids = []
    for jid in req.job_ids:
        try:
            valid_ids.append(uuid.UUID(jid))
        except ValueError:
            continue

    if not valid_ids:
        return {"ranked_jobs": []}

    prefs = await get_or_create_preferences(db, user.id)
    matching_svc = get_matching_service()

    jobs = (await db.execute(select(Job).where(Job.id.in_(valid_ids)))).scalars().all()
    scored = []

    for j in jobs:
        ev = matching_svc.evaluate_job(j, profile, prefs)
        scored.append(
            {
                "job_id": str(j.id),
                "title": j.title,
                "company": j.company_name,
                "score": ev["overall_score"],
                "recommendation": ev["recommendation"],
                "application_url": j.application_url,
                "matched_skills": ev["matched_skills"],
                "missing_skills": ev["missing_skills"],
                "quality_score": j.quality_score,
                "posted_at": j.posted_at.isoformat() if j.posted_at else None,
            }
        )

    scored.sort(key=lambda x: (x["score"], x["quality_score"]), reverse=True)
    return {"ranked_jobs": scored}


@router.post("/jobs/{job_id}/status", response_model=SavedJobResponse)
async def update_job_status_endpoint(
    job_id: str,
    req: JobStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Update manual application tracking status.
    NOTE: System never applies automatically.
    """
    try:
        parsed_id = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    user = await get_or_create_default_user(db)
    try:
        res = await save_or_update_job_status(db, user.id, parsed_id, req.status, req.notes)
        return SavedJobResponse(
            saved_id=res["id"],
            job_id=res["job_id"],
            title=res["title"],
            company=res["company"],
            status=res["status"],
            notes=res["notes"],
            application_url=res["application_url"],
            updated_at=res["updated_at"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/jobs/batch-status", response_model=BatchJobStatusResponse)
async def update_jobs_batch_status_endpoint(
    req: BatchJobStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Batch update application tracking status for multiple jobs atomically.
    Useful for 'Reject All on Page' and batch workflows.
    """
    try:
        parsed_ids = [uuid.UUID(j_id) for j_id in req.job_ids]
    except ValueError:
        raise HTTPException(status_code=400, detail="One or more job IDs have invalid UUID format")

    user = await get_or_create_default_user(db)
    try:
        res = await batch_save_or_update_job_status(
            db=db,
            user_id=user.id,
            job_ids=parsed_ids,
            status=req.status,
            notes=req.notes,
        )
        return BatchJobStatusResponse(
            updated_count=res["updated_count"],
            status=res["status"],
            job_ids=res["job_ids"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/dashboard/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
):
    """Returns real-time aggregated metrics for the dashboard home."""
    user = await get_or_create_default_user(db)
    profile = await get_candidate_profile(db, user.id)
    prefs = await get_or_create_preferences(db, user.id)

    from app.core.redis import get_redis
    redis = await get_redis()
    cache_key = f"stats:dashboard:{user.id}"
    if redis:
        try:
            cached_data = await redis.get(cache_key)
            if cached_data:
                import json
                return json.loads(cached_data)
        except Exception:
            pass

    # 1. Fresh jobs (excluding saved, tracked, and rejected jobs)
    fresh_jobs = await search_jobs_db(
        db,
        freshness_hours=prefs.freshness_hours,
        limit=None,
        exclude_user_id=user.id,
        exclude_statuses=["SAVED", "APPLIED", "INTERVIEW", "OFFER", "REJECTED", "IGNORED"],
    )

    # 2. Score jobs for profile
    matching_svc = get_matching_service()
    scored_jobs = []
    strong_matches = 0

    for item in fresh_jobs:
        job_id = uuid.UUID(item["id"])
        job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one_or_none()
        if not job or not profile:
            continue
        ev = matching_svc.evaluate_job(job, profile, prefs)
        if ev["overall_score"] >= 80.0:
            strong_matches += 1
        item_copy = dict(item)
        item_copy["score"] = ev["overall_score"]
        item_copy["recommendation"] = ev["recommendation"]
        scored_jobs.append(item_copy)

    scored_jobs.sort(key=lambda x: x["score"], reverse=True)

    # 3. Pipeline stats
    saved_stmt = select(SavedJob).where(SavedJob.user_id == user.id)
    saved_res = await db.execute(saved_stmt)
    saved_all = saved_res.scalars().all()

    pipeline_counts = {
        "SAVED": 0,
        "VIEWED": 0,
        "APPLIED": 0,
        "INTERVIEW": 0,
        "OFFER": 0,
        "REJECTED": 0,
    }
    for s in saved_all:
        if s.status in pipeline_counts:
            pipeline_counts[s.status] += 1

    res_payload = {
        "total_fresh_jobs": len(fresh_jobs),
        "strong_matches": strong_matches,
        "freshness_hours": prefs.freshness_hours,
        "timezone": "Asia/Kolkata",
        "pipeline": pipeline_counts,
        "total_tracked": len(saved_all),
        "top_recommendations": scored_jobs[:3],
        "candidate": {
            "target_roles": profile.target_roles if profile else [],
            "experience_level": profile.experience_level if profile else "FRESHER",
            "skills_count": len(profile.skills or []) if profile else 0,
        },
    }

    if redis:
        try:
            import json
            await redis.set(cache_key, json.dumps(res_payload, default=str), ex=120)
        except Exception:
            pass

    return res_payload


@router.get("/jobs/sync/status/{job_id}")
async def get_job_sync_status(job_id: str):
    """Retrieves asynchronous crawl/ingestion job status and metrics."""
    from app.services.queue_service import task_queue

    status_data = await task_queue.get_job_status(job_id)
    if not status_data:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found or expired")
    return status_data


@router.post("/jobs/sync", status_code=202)
async def trigger_job_sync(
    response: Response,
    source: str = Query("all", description="Job source to sync ('all', 'internshala', 'naukri', 'linkedin')"),
    freshness_hours: int = Query(24, description="Maximum age of job postings in hours (1, 4, 8, 12, 16, 24)"),
    async_mode: bool = Query(True, description="Enqueue in background queue (202) or run synchronous (200)"),
    db: AsyncSession = Depends(get_db),
):
    """Triggers live ingestion from job board(s). Enqueues to Redis worker by default."""
    from app.core.rate_limiter import check_rate_limit
    from app.services.queue_service import task_queue

    # Rate limiting on sync: max 10 sync calls per 60s
    allowed, remaining = await check_rate_limit("sync_jobs", limit=10, window_seconds=60)
    if not allowed:
        raise HTTPException(status_code=429, detail="Sync rate limit exceeded. Please wait a minute.")

    # Clamp freshness_hours to allowed values
    allowed_freshness = [1, 4, 8, 12, 16, 24]
    if freshness_hours not in allowed_freshness:
        freshness_hours = min(allowed_freshness, key=lambda x: abs(x - freshness_hours))

    source_clean = source.strip().lower()

    if async_mode:
        job_id = await task_queue.enqueue(
            task_type="sync_source",
            payload={"source": source_clean, "freshness_hours": freshness_hours},
        )
        if job_id:
            response.status_code = 202
            return {
                "job_id": job_id,
                "status": "queued",
                "source": source_clean,
                "freshness_hours": freshness_hours,
                "message": "Job enqueued for background worker processing.",
            }
        logger.warning("redis_queue_unavailable_falling_back_to_sync")

    # Synchronous fallback if async_mode=False or Redis enqueue failed
    response.status_code = 200
    from app.services.job_ingestion_service import JobIngestionService
    from app.sources.base import JobSearchQuery
    from app.sources.registry import get_source_registry
    from app.core.cache import invalidate_cache

    registry = get_source_registry()

    sources_to_sync = []
    if source_clean in ["all", "*", ""]:
        sources_to_sync = registry.get_enabled_sources()
    else:
        src = registry.get_source(source_clean)
        if not src:
            raise HTTPException(status_code=404, detail=f"Source '{source}' not found in registry")
        sources_to_sync = [src]

    # Ingest using strictly user-specified tech skills (independent of candidate resume/profile)
    target_skills = ["javascript", "typescript", "react", "node.js", "python"]

    ingestion_service = JobIngestionService()
    query = JobSearchQuery(
        skills=target_skills,
        freshness_hours=freshness_hours,
        experience_max=2,
        include_jobs=True,
        include_internships=True,
    )

    aggregated_stats = {
        "status": "success",
        "source": source_clean,
        "total_discovered": 0,
        "filtered_by_freshness": 0,
        "fresh_jobs": 0,
        "filtered_by_experience": 0,
        "eligible_candidates": 0,
        "deduplicated": 0,
        "canonical_saved": 0,
        "updated_existing": 0,
        "saved_jobs": 0,
        "saved_internships": 0,
        "ai_extracted_skills": 0,
        "normalized_skills": 0,
        "embeddings_generated": 0,
        "matches_evaluated": 0,
        "sources_synced": [],
        "sources": {},
        "failed_sources": [],
        "duplicates_log": [],
    }

    for src in sources_to_sync:
        src_status = "success"
        src_err = None
        stats = {}
        try:
            stats = await registry.sync_source_isolated(src, db, ingestion_service, query)
            aggregated_stats["sources_synced"].append(src.source_name)
            for k in [
                "total_discovered",
                "filtered_by_freshness",
                "fresh_jobs",
                "filtered_by_experience",
                "eligible_candidates",
                "deduplicated",
                "canonical_saved",
                "updated_existing",
                "saved_jobs",
                "saved_internships",
                "ai_extracted_skills",
                "normalized_skills",
                "embeddings_generated",
                "matches_evaluated",
            ]:
                aggregated_stats[k] += stats.get(k, 0)
            if stats.get("status") == "blocked":
                src_status = "blocked"
                src_err = stats.get("error")
            elif stats.get("status") == "failed":
                src_status = "failed"
                src_err = stats.get("error")
        except Exception as e:
            logger.error("sync_source_failed", error=str(e), source=src.source_name)
            aggregated_stats["failed_sources"].append({"source": src.source_name, "error": str(e)})
            if "403" in str(e) or "block" in str(e).lower():
                src_status = "blocked"
            else:
                src_status = "failed"
            src_err = str(e)

        report = {
            "status": src_status,
            "discovered": stats.get("total_discovered", 0),
            "accepted": stats.get("canonical_saved", 0) + stats.get("updated_existing", 0),
        }
        if src_err:
            report["error"] = src_err
        aggregated_stats["sources"][src.source_name] = report

    if aggregated_stats["sources"]:
        statuses = [s["status"] for s in aggregated_stats["sources"].values()]
        if all(s == "success" for s in statuses):
            aggregated_stats["status"] = "success"
        elif all(s == "blocked" for s in statuses):
            aggregated_stats["status"] = "blocked"
        elif any(s == "success" for s in statuses):
            aggregated_stats["status"] = "partial_success"
        else:
            aggregated_stats["status"] = "failed"
    else:
        aggregated_stats["status"] = "failed"

    # Invalidate cached queries on fresh sync
    await invalidate_cache("stats:*")
    await invalidate_cache("query:*")

    return aggregated_stats



@router.post("/agent/briefing")
async def trigger_agent_briefing(
    db: AsyncSession = Depends(get_db),
):
    """Generates an AI morning briefing using OmniRoute LLM and deterministic matches."""
    import json
    from app.intelligence.llm_provider import get_llm_provider

    user = await get_or_create_default_user(db)
    profile = await get_candidate_profile(db, user.id)
    if not profile:
        raise HTTPException(status_code=400, detail="Candidate profile required")

    prefs = await get_or_create_preferences(db, user.id)
    matching_svc = get_matching_service()

    # Get fresh jobs (excluding saved, tracked, and rejected jobs)
    fresh_jobs = await search_jobs_db(
        db,
        freshness_hours=prefs.freshness_hours,
        limit=30,
        exclude_user_id=user.id,
        exclude_statuses=["SAVED", "APPLIED", "INTERVIEW", "OFFER", "REJECTED", "IGNORED"],
    )
    scored = []

    for item in fresh_jobs:
        job_id = uuid.UUID(item["id"])
        job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one_or_none()
        if not job:
            continue
        ev = matching_svc.evaluate_job(job, profile, prefs)
        if not ev["is_excluded"]:
            scored.append({
                "job_id": str(job.id),
                "title": job.title,
                "company": job.company_name,
                "score": ev["overall_score"],
                "recommendation": ev["recommendation"],
                "matched_skills": ev["matched_skills"],
                "missing_skills": ev["missing_skills"],
                "application_url": job.application_url,
                "salary": item.get("salary", "Not disclosed"),
                "location": item.get("location", "India"),
                "age_hours": item.get("age_hours"),
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    top_matches = scored[:5]

    llm = get_llm_provider()
    system_prompt = (
        "You are Job Agent India. Synthesize a concise, motivating executive briefing for the candidate.\n"
        "Rules:\n"
        "1. Never claim to apply automatically. The candidate applies manually.\n"
        "2. Only recommend fresh verified jobs.\n"
        "3. Highlight why each job matches the candidate's target roles and skills.\n"
        "4. Keep markdown formatting clean with bullet points."
    )

    payload = {
        "candidate": {
            "target_roles": profile.target_roles,
            "skills": (profile.skills or [])[:15],
            "experience_years": profile.experience_years,
        },
        "top_matches": top_matches,
    }

    try:
        briefing_text = await llm.complete(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Summarize today's top opportunities for me:\n{json.dumps(payload, indent=2)}"},
            ],
            temperature=0.3,
        )
    except Exception as e:
        briefing_text = f"Top matches evaluated by 6-dimension scoring engine. OmniRoute LLM synthesis note: {e}"

    return {
        "briefing": briefing_text,
        "top_matches": top_matches,
        "total_fresh_evaluated": len(scored),
    }


class PipelineEnrichRequest(BaseModel):
    job_ids: list[str] | None = None
    limit: int = 20


@router.post("/jobs/pipeline/enrich")
async def trigger_pipeline_enrichment_endpoint(
    req: PipelineEnrichRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 43: Trigger Job Intelligence Pipeline enrichment on target jobs.
    Runs AI extraction, skill normalization, 384d embedding, and match scoring.
    """
    from app.intelligence.extractors import enrich_job_record_llm
    from app.intelligence.embedding_provider import get_embedding_provider
    from app.models.candidate_profile import CandidateProfile

    stmt = select(Job).where(Job.is_active == True)  # noqa: E712
    if req.job_ids:
        try:
            parsed_ids = [uuid.UUID(jid) for jid in req.job_ids]
            stmt = stmt.where(Job.id.in_(parsed_ids))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid job UUID in list")
    else:
        # Default to un-enriched jobs
        stmt = stmt.order_by(desc(Job.created_at)).limit(min(req.limit, 50))

    res = await db.execute(stmt)
    jobs_to_enrich = res.scalars().all()

    emb_provider = get_embedding_provider()
    user = await get_or_create_default_user(db)
    profile = await get_candidate_profile(db, user.id)
    prefs = await get_or_create_preferences(db, user.id)
    matching_svc = get_matching_service()

    enriched_count = 0
    embedded_count = 0
    matched_count = 0

    for job in jobs_to_enrich:
        try:
            # 1. AI Enrichment
            enrichment = await enrich_job_record_llm(job.id, db)
            if enrichment:
                enriched_count += 1

            # 2. Embedding
            text = f"{job.normalized_title or job.title} at {job.company_name}. {job.description} Skills: {', '.join(job.required_skills or [])}"
            emb = emb_provider.embed_text(text)
            if emb:
                job.embedding = emb
                embedded_count += 1

            # 3. Match calculation
            if profile:
                await matching_svc.get_or_calculate_match(db, job, profile, prefs)
                matched_count += 1
        except Exception as e:
            logger.warning("pipeline_job_enrich_single_failed", job_id=str(job.id), error=str(e))

    await db.commit()

    return {
        "status": "success",
        "total_requested": len(jobs_to_enrich),
        "ai_enriched": enriched_count,
        "embeddings_generated": embedded_count,
        "matches_evaluated": matched_count,
    }



