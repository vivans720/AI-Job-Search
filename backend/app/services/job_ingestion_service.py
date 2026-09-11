import uuid
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.database import async_session_factory
from app.intelligence.embedding_provider import get_embedding_provider
from app.intelligence.service import AIService
from app.models.candidate_profile import CandidateProfile
from app.models.company import Company
from app.models.job import Job
from app.models.preference import Preference
from app.models.user import User
from app.services.dedup_service import get_dedup_service
from app.services.freshness_service import get_freshness_service
from app.services.matching_service import get_matching_service
from app.services.skill_extraction_service import get_skill_extraction_service
from app.sources.base import JobSearchQuery, JobSource, NormalizedJob, RawJob
from app.utils.normalization import normalize_skills
from app.utils.sync_logger import log_sync_event
from app.utils.type_normalization import make_json_serializable
from app.utils.validation import validate_normalized_job

logger = structlog.get_logger(__name__)


class JobIngestionService:
    """
    Coordinates end-to-end Phase 43 Job Intelligence Pipeline:
    Discovery -> Normalization -> 24h Freshness Filter -> Fast L1-L4 Dedup ->
    AI/Hybrid Skill Normalization & Extraction -> 384d Vector Embedding ->
    Level 5 Semantic Dedup -> Database Persistence with Savepoints -> Candidate Match Evaluation
    """

    def __init__(self):
        self.freshness_service = get_freshness_service()
        self.dedup_service = get_dedup_service()
        self.embedding_provider = get_embedding_provider()
        self.skill_extractor = get_skill_extraction_service()
        self.matching_service = get_matching_service()

    async def ingest_source(
        self,
        db: AsyncSession,
        source: JobSource,
        query: JobSearchQuery | None = None,
    ) -> dict[str, Any]:
        q = query or JobSearchQuery()
        raw_jobs = await source.search(q)
        total_discovered = len(raw_jobs)
        logger.info(
            "ingestion_discovered_raw",
            source=source.source_name,
            count=total_discovered,
        )

        filtered_by_validation = 0
        filtered_by_freshness = 0
        filtered_by_experience = 0

        # 1. Normalization & validation
        normalized_jobs: list[NormalizedJob] = []
        for r in raw_jobs:
            try:
                norm = await source.normalize(r)
                if norm is None:
                    filtered_by_freshness += 1
                    continue
            except Exception as e:
                logger.error(
                    "normalization_failed",
                    source=source.source_name,
                    source_job_id=getattr(r, "source_job_id", "unknown"),
                    error=str(e),
                )
                filtered_by_validation += 1
                continue

            try:
                is_valid, reason = validate_normalized_job(norm)
                if not is_valid:
                    filtered_by_validation += 1
                    logger.warning(
                        "job_validation_rejected",
                        source=source.source_name,
                        reason=reason,
                        title=getattr(norm, "title", "unknown"),
                        job_hash=getattr(norm, "job_hash", "unknown"),
                    )
                    continue
                normalized_jobs.append(norm)
            except Exception as e:
                logger.error("validator_crash", source=source.source_name, error=str(e))
                filtered_by_validation += 1
                continue

        # 2. Freshness filter (strictly <= 24 hours, confidence != LOW)
        fresh_jobs: list[NormalizedJob] = []
        for j in normalized_jobs:
            is_fresh, reason, age = self.freshness_service.evaluate_freshness(
                posted_at=j.posted_at,
                confidence=j.posted_at_confidence,
                freshness_hours=q.freshness_hours,
                source=source.source_name,
                title=j.title,
                scraped_at=j.scraped_at,
            )
            if is_fresh:
                fresh_jobs.append(j)
            else:
                filtered_by_freshness += 1

        logger.info(
            "freshness_filtering_completed",
            fresh_count=len(fresh_jobs),
            filtered_count=filtered_by_freshness,
        )

        # 3. Recall-First Architecture: All fresh jobs are preserved
        # Experience and seniority are preserved as metadata for frontend filtering and AI ranking
        surviving_jobs: list[NormalizedJob] = list(fresh_jobs)
        filtered_by_experience = 0

        logger.info(
            "recall_first_experience_filtering_bypassed",
            surviving_count=len(surviving_jobs),
            fresh_count=len(fresh_jobs),
        )

        # 4. Stage 1: Cheap deterministic deduplication (Levels 1-4: URL, Source ID, Meta, Fuzzy text)
        canonical_jobs, cheap_audit_log = self.dedup_service.deduplicate_batch(surviving_jobs)

        # 5. Phase 43: AI & Hybrid Skill Extraction + Taxonomy Normalization on surviving canonical jobs
        ai_extracted_count = 0
        skills_normalized_count = 0

        for j in canonical_jobs:
            try:
                # If skills are empty or minimally populated, trigger skill extraction
                current_skills = j.required_skills or []
                if not current_skills or len(current_skills) < 2:
                    extracted = await self.skill_extractor.extract_skills(
                        description=j.description,
                        title=j.title,
                        explicit_skills=current_skills,
                    )
                    if extracted.required_skills:
                        j.required_skills = extracted.required_skills
                        ai_extracted_count += 1
                    if extracted.preferred_skills and not j.preferred_skills:
                        j.preferred_skills = extracted.preferred_skills

                # Always ensure all skills pass canonical taxonomy normalization
                if j.required_skills:
                    norm_req = normalize_skills(j.required_skills)
                    if norm_req != j.required_skills:
                        skills_normalized_count += 1
                    j.required_skills = norm_req

                if j.preferred_skills:
                    norm_pref = normalize_skills(j.preferred_skills)
                    j.preferred_skills = [p for p in norm_pref if p.lower() not in {r.lower() for r in j.required_skills}]

            except Exception as ai_err:
                logger.warning(
                    "job_intelligence_skill_extraction_failed",
                    source=source.source_name,
                    title=j.title,
                    error=str(ai_err),
                )

        logger.info(
            "job_intelligence_pipeline_skills_processed",
            source=source.source_name,
            ai_extracted_count=ai_extracted_count,
            skills_normalized_count=skills_normalized_count,
        )

        # 6. Generate dense 384d semantic vector embeddings for surviving candidates
        texts_to_embed = [
            f"{j.normalized_title} at {j.normalized_company}. {j.description} Skills: {', '.join(j.required_skills)}"
            for j in canonical_jobs
        ]
        embeddings = []
        try:
            embeddings = self.embedding_provider.embed_batch(texts_to_embed) if texts_to_embed else []
        except Exception as emb_err:
            logger.warning("embedding_generation_failed_continuing_without_embeddings", error=str(emb_err))

        # 7. Stage 2: Semantic embedding deduplication (Level 5) on surviving candidates
        if embeddings and len(canonical_jobs) > 1:
            canonical_jobs, semantic_audit_log = self.dedup_service.deduplicate_batch(
                canonical_jobs, embeddings=embeddings
            )
            audit_log = cheap_audit_log + semantic_audit_log
        else:
            audit_log = cheap_audit_log

        deduplicated_count = len(audit_log)

        # 8. Database Persistence with Savepoints (begin_nested)
        saved_count = 0
        updated_count = 0
        persisted_job_entities: list[Job] = []

        for i, norm_job in enumerate(canonical_jobs):
            emb = embeddings[i] if i < len(embeddings) else None

            try:
                async with db.begin_nested():
                    # Get or create Company
                    comp_stmt = select(Company).where(Company.normalized_name == norm_job.normalized_company.lower())
                    comp_res = await db.execute(comp_stmt)
                    company = comp_res.scalar_one_or_none()

                    if not company:
                        company = Company(
                            id=uuid.uuid4(),
                            name=norm_job.company_name,
                            normalized_name=norm_job.normalized_company.lower(),
                        )
                        db.add(company)
                        await db.flush()

                    # Check if job exists by job_hash or source_url
                    job_stmt = select(Job).where(
                        (Job.job_hash == norm_job.job_hash) | (Job.source_url == norm_job.source_url)
                    )
                    job_res = await db.execute(job_stmt)
                    existing_job = job_res.scalar_one_or_none()

                    if existing_job:
                        # Update timestamps and activate
                        existing_job.last_seen_at = datetime.now(timezone.utc)
                        existing_job.is_active = True
                        if norm_job.raw_data:
                            existing_job.raw_data = make_json_serializable(norm_job.raw_data)
                        if norm_job.posted_at and (not existing_job.posted_at or norm_job.posted_at > existing_job.posted_at):
                            existing_job.posted_at = norm_job.posted_at
                            existing_job.posted_at_confidence = norm_job.posted_at_confidence
                        if norm_job.required_skills and not existing_job.required_skills:
                            existing_job.required_skills = norm_job.required_skills
                        if emb is not None and existing_job.embedding is None:
                            existing_job.embedding = emb
                        updated_count += 1
                        persisted_job_entities.append(existing_job)
                    else:
                        new_job = Job(
                            id=uuid.uuid4(),
                            source=norm_job.source[:50] if norm_job.source else "unknown",
                            source_job_id=norm_job.source_job_id[:255] if norm_job.source_job_id else "",
                            title=norm_job.title[:255],
                            normalized_title=norm_job.normalized_title[:255] if norm_job.normalized_title else None,
                            role_category=norm_job.role_category[:50] if norm_job.role_category else None,
                            company_id=company.id,
                            company_name=company.name[:255],
                            description=norm_job.description,
                            location=norm_job.location[:255] if norm_job.location else None,
                            normalized_location=norm_job.normalized_location[:255] if norm_job.normalized_location else None,
                            remote_type=(norm_job.remote_type or "ONSITE")[:50],
                            employment_type=(norm_job.employment_type or "FULL_TIME")[:50],
                            experience_min=norm_job.experience_min,
                            experience_max=norm_job.experience_max,
                            experience_text=norm_job.experience_text[:255] if norm_job.experience_text else None,
                            experience_confidence=(norm_job.experience_confidence or "LOW")[:20],
                            description_confidence=(norm_job.description_confidence or "HIGH")[:20],
                            salary_min=norm_job.salary_min,
                            salary_max=norm_job.salary_max,
                            salary_currency=(norm_job.salary_currency or "INR")[:10],
                            salary_period=(norm_job.salary_period or "YEAR")[:20],
                            salary_raw=norm_job.salary_raw[:255] if norm_job.salary_raw else None,
                            posted_at=norm_job.posted_at,
                            posted_at_raw=norm_job.posted_at_raw[:100] if norm_job.posted_at_raw else None,
                            posted_at_confidence=(norm_job.posted_at_confidence or "LOW")[:20],
                            first_seen_at=norm_job.first_seen_at,
                            last_seen_at=norm_job.last_seen_at,
                            scraped_at=norm_job.scraped_at,
                            source_url=norm_job.source_url[:500] if norm_job.source_url else None,
                            application_url=norm_job.application_url[:500] if norm_job.application_url else None,
                            job_hash=norm_job.job_hash[:64] if norm_job.job_hash else None,
                            raw_data=make_json_serializable(norm_job.raw_data) if norm_job.raw_data else {},
                            required_skills=norm_job.required_skills,
                            preferred_skills=norm_job.preferred_skills,
                            embedding=emb,
                            quality_score=norm_job.quality_score,
                            is_active=True,
                        )
                        db.add(new_job)
                        saved_count += 1
                        persisted_job_entities.append(new_job)
            except Exception as single_err:
                logger.warning(
                    "job_persistence_savepoint_failed",
                    source=source.source_name,
                    title=norm_job.title,
                    error=str(single_err),
                )
                continue

        await db.commit()

        # 9. Phase 43: Candidate Matching Stage
        # For default active user/profile, precalculate matches for saved jobs
        matches_evaluated_count = 0
        try:
            user_stmt = select(User).limit(1)
            user_res = await db.execute(user_stmt)
            default_user = user_res.scalar_one_or_none()
            if default_user:
                prof_stmt = select(CandidateProfile).where(CandidateProfile.user_id == default_user.id)
                prof_res = await db.execute(prof_stmt)
                candidate_profile = prof_res.scalar_one_or_none()

                pref_stmt = select(Preference).where(Preference.user_id == default_user.id)
                pref_res = await db.execute(pref_stmt)
                candidate_prefs = pref_res.scalar_one_or_none()

                if candidate_profile and persisted_job_entities:
                    for p_job in persisted_job_entities:
                        try:
                            await self.matching_service.get_or_calculate_match(
                                db=db,
                                job=p_job,
                                profile=candidate_profile,
                                preferences=candidate_prefs,
                            )
                            matches_evaluated_count += 1
                        except Exception as m_err:
                            logger.debug("job_matching_evaluation_skipped", job_id=str(p_job.id), error=str(m_err))
        except Exception as match_stage_err:
            logger.warning("matching_stage_post_ingest_failed", error=str(match_stage_err))

        saved_jobs_count = sum(1 for j in canonical_jobs if j.employment_type != "INTERNSHIP")
        saved_internships_count = sum(1 for j in canonical_jobs if j.employment_type == "INTERNSHIP")

        stats = {
            "source": source.source_name,
            "total_discovered": total_discovered,
            "total_scraped": total_discovered,
            "filtered_by_validation": filtered_by_validation,
            "dropped_validation": filtered_by_validation,
            "filtered_by_freshness": filtered_by_freshness,
            "dropped_freshness": filtered_by_freshness,
            "fresh_jobs": len(fresh_jobs),
            "filtered_by_experience": filtered_by_experience,
            "dropped_seniority": filtered_by_experience,
            "eligible_candidates": len(surviving_jobs),
            "deduplicated": deduplicated_count,
            "canonical_saved": saved_count,
            "saved_canonical": saved_count,
            "updated_existing": updated_count,
            "saved_jobs": saved_jobs_count,
            "saved_internships": saved_internships_count,
            "ai_extracted_skills": ai_extracted_count,
            "normalized_skills": skills_normalized_count,
            "embeddings_generated": len(embeddings),
            "matches_evaluated": matches_evaluated_count,
            "duplicates_log": audit_log,
        }
        log_sync_event(stats)
        return stats
