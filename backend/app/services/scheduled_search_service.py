import uuid
from datetime import datetime, timezone
from typing import Any, Optional
import structlog
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_activity import AgentRun
from app.models.notification import DailyDigest, DigestNotifiedJob
from app.services.agent_activity_service import AgentActivityService
from app.services.job_service import search_jobs_db
from app.services.matching_service import get_matching_service
from app.services.preference_service import get_or_create_preferences
from app.services.profile_service import get_candidate_profile

logger = structlog.get_logger(__name__)


class ScheduledSearchService:
    """
    Orchestrates the scheduled autonomous job hunt.
    Executes on a recurring cron or on-demand:
    1. Reads user preferences and candidate profile.
    2. Searches fresh jobs (<= 24h) excluding previously notified jobs and existing pipeline jobs.
    3. Evaluates 6-dimension match scores and ranks candidates.
    4. Formats morning Daily Digest briefing (including zero-match handling).
    5. Records notified job IDs to prevent duplicate alerts across runs.
    6. Logs agent activity run and milestone events.
    """

    @classmethod
    async def run_scheduled_job_search(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        run_id: Optional[uuid.UUID] = None,
        freshness_hours: int = 24,
        match_threshold_override: Optional[int] = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        logger.info(
            "scheduled_search_started",
            user_id=str(user_id),
            run_id=str(run_id) if run_id else None,
            freshness_hours=freshness_hours,
        )

        active_run = None
        if not run_id and not dry_run:
            active_run = await AgentActivityService.start_run(
                db=db,
                user_id=user_id,
                trigger="scheduled",
                summary="Scheduled morning job hunt execution",
                metrics={"phase": "discovery"},
            )
            run_id = active_run.id
        elif run_id:
            active_run = await AgentActivityService.get_run(db, run_id)

        try:
            # 1. Retrieve Candidate Intelligence & Preferences
            profile = await get_candidate_profile(db, user_id)
            prefs = await get_or_create_preferences(db, user_id)

            target_roles = profile.target_roles if profile and profile.target_roles else []
            preferred_locations = (
                prefs.preferred_locations
                if prefs.preferred_locations
                else (profile.preferred_locations if profile else [])
            )
            threshold = (
                match_threshold_override
                if match_threshold_override is not None
                else (prefs.match_threshold or 60)
            )

            if active_run:
                await AgentActivityService.log_event(
                    db=db,
                    run_id=run_id,
                    event_type="milestone",
                    tool_name="scheduled_search",
                    action_summary=f"Read candidate profile ({len(target_roles)} target roles) and preferences (threshold: {threshold}%)",
                    payload={
                        "target_roles": target_roles,
                        "threshold": threshold,
                        "locations": preferred_locations,
                    },
                )

            # 2. Search Fresh Jobs excluding previously notified jobs and pipeline jobs
            fresh_jobs = await search_jobs_db(
                db=db,
                roles=target_roles if target_roles else None,
                locations=preferred_locations if preferred_locations else None,
                freshness_hours=freshness_hours,
                include_remote=True,
                exclude_user_id=user_id,
                exclude_statuses=["SAVED", "APPLIED", "IGNORED", "PREPARING", "READY_TO_APPLY", "INTERVIEW", "REJECTED", "OFFER"],
                exclude_notified=True,
                excluded_companies=prefs.excluded_companies,
                limit=50,
            )

            if active_run:
                await AgentActivityService.log_event(
                    db=db,
                    run_id=run_id,
                    event_type="status_update",
                    tool_name="scheduled_search",
                    action_summary=f"Discovered {len(fresh_jobs)} fresh unnotified candidate opportunities",
                    payload={"fresh_jobs_count": len(fresh_jobs)},
                )

            # 3. Match & Rank Jobs
            matching_svc = get_matching_service()
            evaluated_jobs = []

            for j in fresh_jobs:
                entity = j.get("_entity")
                if not entity:
                    continue
                score_data = matching_svc.evaluate_job(entity, profile, prefs)
                score = score_data.get("overall_score", 0.0)
                evaluated_jobs.append(
                    {
                        "job_id": str(entity.id),
                        "title": entity.title,
                        "company": entity.company_name,
                        "location": entity.location,
                        "salary": entity.salary_raw or "Not disclosed",
                        "application_url": entity.application_url,
                        "score": score,
                        "recommendation": score_data.get("recommendation", "Consider"),
                        "matched_skills": score_data.get("matched_skills", []),
                        "missing_skills": score_data.get("missing_skills", []),
                        "explanation": score_data.get("explanation", ""),
                        "age_hours": j.get("age_hours"),
                    }
                )

            # Sort by score descending
            evaluated_jobs.sort(key=lambda x: x["score"], reverse=True)

            # Strong matches meeting or exceeding threshold
            strong_matches = [j for j in evaluated_jobs if j["score"] >= threshold]
            top_recommendations = strong_matches[:5]

            # 4. Construct Digest Summary
            now_utc = datetime.now(timezone.utc)
            date_str = now_utc.strftime("%A, %B %d, %Y")

            if top_recommendations:
                status = "DELIVERED"
                lines = [
                    f"# 🌅 Daily Tech Job Digest — {date_str}",
                    "**Active Fresh Feed**: Opportunities posted strictly within the last 24 hours.",
                    "",
                    "## Top Recommendations For You",
                    "",
                ]
                for idx, job in enumerate(top_recommendations, 1):
                    lines.append(f"### {idx}. {job['title']} @ {job['company']} ({int(job['score'])}% Match)")
                    lines.append(f"- **Location**: {job['location'] or 'India'} | **Salary**: {job['salary']}")
                    fit_desc = job['explanation'] or f"Strong match for {job['title']} with {len(job['matched_skills'])} overlapping skills."
                    lines.append(f"- **Key Fit**: {fit_desc}")
                    lines.append(f"- **Apply URL**: {job['application_url']}")
                    lines.append("")

                lines.append("## Summary Statistics")
                lines.append(f"- Fresh Opportunities Discovered: {len(fresh_jobs)}")
                lines.append(f"- Strong Matches (≥{threshold}%): {len(strong_matches)}")
                if target_roles:
                    lines.append(f"- Target Roles Evaluated: {', '.join(target_roles[:4])}")
                lines.append("")
                lines.append("👉 *Remember: Click links to apply manually in your browser. Tell me to mark as APPLIED when submitted.*")
                summary_text = "\n".join(lines)
            else:
                # Zero-match day handling
                status = "NO_MATCHES"
                lines = [
                    f"# 🌅 Daily Tech Job Digest — {date_str}",
                    "**Active Fresh Feed**: Opportunities posted strictly within the last 24 hours.",
                    "",
                    "## Today's Overview",
                    f"Our autonomous search scanned fresh opportunities posted across configured source boards in the last {freshness_hours} hours.",
                    f"- **Status**: No fresh opportunities met your {threshold}% match score threshold today.",
                    f"- Total fresh jobs evaluated: {len(fresh_jobs)}",
                    "",
                    "### Recommendations to broaden your morning hunt:",
                    "1. Consider lowering your match threshold by 5–10% (`update_preferences(match_threshold=...)`).",
                    "2. Add adjacent target roles or include remote opportunities.",
                    "3. Relax location constraints to cover additional tech hubs.",
                    "",
                    "We will monitor the pipeline and wake up tomorrow morning to check for new postings.",
                ]
                summary_text = "\n".join(lines)

            # 5. Persist Daily Digest & Notified Job IDs (unless dry_run)
            digest = None
            notified_ids = [j["job_id"] for j in top_recommendations]

            if not dry_run:
                digest = DailyDigest(
                    user_id=user_id,
                    run_id=run_id,
                    digest_date=now_utc,
                    summary=summary_text,
                    job_ids=notified_ids,
                    total_found=len(fresh_jobs),
                    strong_matches_count=len(strong_matches),
                    status=status,
                    metadata_info={
                        "freshness_hours": freshness_hours,
                        "threshold": threshold,
                        "total_evaluated": len(evaluated_jobs),
                    },
                )
                db.add(digest)
                await db.flush()

                for jid_str in notified_ids:
                    try:
                        jid = uuid.UUID(jid_str)
                        notified_record = DigestNotifiedJob(
                            user_id=user_id,
                            job_id=jid,
                            digest_id=digest.id,
                            notified_at=now_utc,
                        )
                        db.add(notified_record)
                    except Exception as err:
                        logger.warning("digest_notified_job_add_error", error=str(err), job_id=jid_str)

                await db.commit()
                await db.refresh(digest)

                if active_run:
                    await AgentActivityService.log_event(
                        db=db,
                        run_id=run_id,
                        event_type="milestone",
                        tool_name="scheduled_search",
                        action_summary=f"Generated Daily Job Digest ({status}): {len(top_recommendations)} recommendations recorded",
                        payload={"digest_id": str(digest.id), "status": status, "top_count": len(top_recommendations)},
                    )
                    await AgentActivityService.complete_run(
                        db=db,
                        run_id=run_id,
                        summary=f"Completed scheduled job search. Status: {status}. Recommended {len(top_recommendations)} jobs.",
                        metrics={
                            "total_discovered": len(fresh_jobs),
                            "strong_matches": len(strong_matches),
                            "recommended": len(top_recommendations),
                        },
                    )

            return {
                "status": status,
                "digest_id": str(digest.id) if digest else None,
                "run_id": str(run_id) if run_id else None,
                "summary": summary_text,
                "total_found": len(fresh_jobs),
                "strong_matches_count": len(strong_matches),
                "recommended_jobs": top_recommendations,
                "dry_run": dry_run,
            }

        except Exception as e:
            logger.error("scheduled_search_failed", user_id=str(user_id), error=str(e))
            if active_run:
                await AgentActivityService.fail_run(
                    db=db, run_id=run_id, error_message=str(e)
                )
            raise

    @classmethod
    async def get_recent_digests(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        limit: int = 7,
    ) -> list[DailyDigest]:
        stmt = (
            select(DailyDigest)
            .where(DailyDigest.user_id == user_id)
            .order_by(desc(DailyDigest.digest_date))
            .limit(limit)
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def get_latest_digest(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> Optional[DailyDigest]:
        stmt = (
            select(DailyDigest)
            .where(DailyDigest.user_id == user_id)
            .order_by(desc(DailyDigest.digest_date))
            .limit(1)
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @classmethod
    async def create_digest_manual(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        summary: str,
        job_ids: list[str],
        status: str = "DELIVERED",
        metadata_info: Optional[dict[str, Any]] = None,
        run_id: Optional[uuid.UUID] = None,
    ) -> DailyDigest:
        now_utc = datetime.now(timezone.utc)
        digest = DailyDigest(
            user_id=user_id,
            run_id=run_id,
            digest_date=now_utc,
            summary=summary,
            job_ids=job_ids,
            total_found=len(job_ids),
            strong_matches_count=len(job_ids),
            status=status,
            metadata_info=metadata_info or {},
        )
        db.add(digest)
        await db.flush()

        for jid_str in job_ids:
            try:
                jid = uuid.UUID(jid_str)
                notified = DigestNotifiedJob(
                    user_id=user_id,
                    job_id=jid,
                    digest_id=digest.id,
                    notified_at=now_utc,
                )
                db.add(notified)
            except Exception:
                pass

        await db.commit()
        await db.refresh(digest)
        return digest
