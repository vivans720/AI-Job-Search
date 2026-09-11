from datetime import datetime, timezone, timedelta
from collections import Counter
import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.saved_job import SavedJob
from app.models.candidate_profile import CandidateProfile
from app.models.preference import Preference
from app.schemas.dashboard import (
    DashboardFunnel,
    ApplicationStatusSummary,
    SkillGapItem,
    SourceHealthSummary,
    SyncStatusSummary,
    DashboardResponse,
)
from app.services.job_service import search_jobs_db
from app.sources.registry import get_source_registry
from app.utils.sync_logger import get_recent_sync_logs

logger = structlog.get_logger(__name__)


def _get_greeting() -> str:
    now = datetime.now()
    hour = now.hour
    if 5 <= hour < 12:
        return "Good morning"
    elif 12 <= hour < 17:
        return "Good afternoon"
    elif 17 <= hour < 22:
        return "Good evening"
    return "Good night"


async def get_dashboard_data(
    db: AsyncSession,
    user_id,
    profile: CandidateProfile | None,
    preferences: Preference | None,
) -> DashboardResponse:
    greeting = _get_greeting()
    user_name = None
    if profile and profile.manual_overrides:
        user_name = profile.manual_overrides.get("name") or profile.manual_overrides.get("full_name")

    now = datetime.now(timezone.utc)
    freshness_cutoff = now - timedelta(hours=24)

    # 1. Fresh jobs count in DB
    fresh_query = select(func.count(Job.id)).where(Job.created_at >= freshness_cutoff)
    fresh_res = await db.execute(fresh_query)
    fresh_count = fresh_res.scalar_or_none() or 0

    # 2. Get top matching jobs (personalized)
    scored_jobs = await search_jobs_db(
        db=db,
        user_profile=profile,
        preferences=preferences,
        sort_by="match",
        view="for_you",
        page=1,
        page_size=100,
        exclude_rejected=True,
    )

    strong_matches = [j for j in scored_jobs if (j.match.overall_score if j.match else 0.0) >= 70.0]
    excellent_matches = [j for j in scored_jobs if (j.match.overall_score if j.match else 0.0) >= 85.0]

    funnel = DashboardFunnel(
        fresh_jobs_count=fresh_count,
        strong_matches_count=len(strong_matches),
        excellent_matches_count=len(excellent_matches),
    )

    recommended_jobs = scored_jobs[:5]

    # 3. New jobs (sorted by freshness)
    new_jobs_raw = await search_jobs_db(
        db=db,
        user_profile=profile,
        preferences=preferences,
        sort_by="freshness",
        view="all",
        page=1,
        page_size=5,
        exclude_rejected=True,
    )
    new_jobs = new_jobs_raw[:5]

    # 4. Application tracker summary
    status_query = select(SavedJob.status, func.count(SavedJob.id)).where(SavedJob.user_id == user_id).group_by(SavedJob.status)
    status_res = await db.execute(status_query)
    status_counts = dict(status_res.all())

    app_summary = ApplicationStatusSummary(
        total_tracked=sum(status_counts.values()),
        saved=status_counts.get("SAVED", 0),
        applied=status_counts.get("APPLIED", 0),
        interviewing=status_counts.get("INTERVIEWING", 0),
        offered=status_counts.get("OFFER", 0),
        rejected=status_counts.get("REJECTED", 0),
    )

    # 5. Skill gap analysis
    user_skills_set = set()
    if profile and profile.skills:
        user_skills_set = {s.lower().strip() for s in profile.skills}

    gap_counter = Counter()
    total_relevant_jobs = len(scored_jobs)
    for j in scored_jobs:
        if j.match and j.match.missing_skills:
            for s in j.match.missing_skills:
                s_clean = s.strip()
                if s_clean:
                    gap_counter[s_clean] += 1
        else:
            job_skills = j.required_skills or []
            for s in job_skills:
                s_clean = s.strip().lower()
                if s_clean and s_clean not in user_skills_set:
                    gap_counter[s.strip()] += 1

    skill_gaps = []
    for skill, freq in gap_counter.most_common(6):
        pct = round((freq / total_relevant_jobs * 100.0), 1) if total_relevant_jobs > 0 else 0.0
        skill_gaps.append(SkillGapItem(skill=skill, frequency=freq, demand_percentage=pct))

    # 6. Source health
    registry = get_source_registry()
    health_results = await registry.health_check_all()
    source_details = {}
    from app.sources.rate_limiter import SOURCE_RATE_LIMITS

    for name, src in registry._sources.items():
        metrics = src.get_metrics().model_dump() if hasattr(src, "get_metrics") else {}
        limits = SOURCE_RATE_LIMITS.get(name, SOURCE_RATE_LIMITS.get("default", {}))
        source_details[name] = {
            "healthy": health_results.get(name, False),
            "enabled": src.enabled,
            "status": getattr(src, "status", "ok"),
            "rate_limit": f"{limits.get('rate', 0)} req/{int(limits.get('per', 60))}s",
            "metrics": metrics,
        }

    healthy_count = sum(1 for is_h in health_results.values() if is_h)
    all_healthy = healthy_count == len(health_results) if health_results else False

    source_health = SourceHealthSummary(
        healthy_count=healthy_count,
        total_sources=len(health_results),
        status="ok" if all_healthy else "degraded",
        sources=health_results,
        details=source_details,
    )

    # 7. Sync status
    recent_syncs = get_recent_sync_logs(limit=1)
    sync_status = SyncStatusSummary()
    if recent_syncs:
        latest = recent_syncs[0]
        sync_status = SyncStatusSummary(
            last_sync_time=latest.get("timestamp"),
            status=latest.get("status", "completed"),
            duration_seconds=latest.get("duration_seconds", 0.0),
            jobs_discovered=latest.get("jobs_discovered", 0),
            jobs_added=latest.get("jobs_added", 0),
        )

    return DashboardResponse(
        greeting=greeting,
        user_name=user_name,
        funnel=funnel,
        recommended_jobs=recommended_jobs,
        new_jobs=new_jobs,
        application_summary=app_summary,
        skill_gaps=skill_gaps,
        source_health=source_health,
        sync_status=sync_status,
    )
