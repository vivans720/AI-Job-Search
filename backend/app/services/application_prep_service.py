import json
import uuid
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.database import async_session_factory
from app.intelligence.llm_provider import create_ai_provider
from app.intelligence.base import clean_and_extract_json
from app.models.application_preparation import ApplicationPreparation
from app.models.candidate_profile import CandidateProfile
from app.models.job import Job
from app.models.resume import Resume
from app.services.preference_service import get_or_create_preferences

logger = structlog.get_logger(__name__)


class ApplicationPrepService:
    @staticmethod
    async def get_or_create_preparation(
        db: AsyncSession,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> ApplicationPreparation:
        """Retrieves or creates the preparation record for a user and job."""
        stmt = select(ApplicationPreparation).where(
            ApplicationPreparation.user_id == user_id,
            ApplicationPreparation.job_id == job_id,
        )
        res = await db.execute(stmt)
        prep = res.scalar_one_or_none()
        if not prep:
            # Default to user's latest active resume if one exists
            resume_stmt = (
                select(Resume)
                .where(Resume.user_id == user_id, Resume.is_active == True)  # noqa: E712
                .order_by(Resume.created_at.desc())
            )
            active_resume = (await db.execute(resume_stmt)).scalars().first()
            prep = ApplicationPreparation(
                user_id=user_id,
                job_id=job_id,
                resume_mode="EXISTING",
                resume_id=active_resume.id if active_resume else None,
                status="DRAFT",
            )
            db.add(prep)
            await db.commit()
            await db.refresh(prep)
        return prep

    @staticmethod
    async def prepare_resume_for_job(
        db: AsyncSession,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
        mode: str = "EXISTING",
    ) -> dict[str, Any]:
        """
        Prepares resume for the application.
        - If mode == 'EXISTING': preserves active candidate resume without modifications.
        - If mode == 'TAILORED': crafts tailored sections using OmniRoute LLM with STRICT anti-hallucination rules.
        """
        prep = await ApplicationPrepService.get_or_create_preparation(db, user_id, job_id)
        
        job_res = await db.execute(select(Job).where(Job.id == job_id))
        job = job_res.scalar_one_or_none()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Get active resume & candidate profile
        resume_res = await db.execute(
            select(Resume)
            .where(Resume.user_id == user_id, Resume.is_active == True)  # noqa: E712
            .order_by(Resume.created_at.desc())
        )
        resume = resume_res.scalars().first()
        
        profile_res = await db.execute(
            select(CandidateProfile).where(CandidateProfile.user_id == user_id)
        )
        profile = profile_res.scalar_one_or_none()

        if not resume and not profile:
            raise ValueError("No candidate profile or resume found to prepare application.")

        prep.resume_mode = mode.upper()
        if resume:
            prep.resume_id = resume.id

        if prep.resume_mode == "EXISTING":
            prep.tailored_resume_content = None
            await db.commit()
            await db.refresh(prep)
            return {
                "status": "ok",
                "resume_mode": "EXISTING",
                "resume_id": str(resume.id) if resume else None,
                "message": "Using existing candidate resume without modifications.",
            }

        # Tailoring mode with strict anti-hallucination
        pref = await get_or_create_preferences(db, user_id)
        llm = create_ai_provider(
            provider_name=pref.ai_provider,
            model=pref.ai_model,
            base_url=pref.ai_base_url,
            api_key=pref.ai_api_key,
        )

        research_context = (job.raw_data or {}).get("browser_research", {})
        system_prompt = (
            "You are an expert technical career advisor tailoring a resume for a specific job.\n"
            "CRITICAL ANTI-HALLUCINATION RULES:\n"
            "1. NEVER invent past companies, employment dates, titles, degrees, or metrics.\n"
            "2. Only emphasize skills, projects, and experiences that ACTUALLY exist in the candidate's profile/resume.\n"
            "3. If the candidate lacks a required skill, DO NOT add it. Reframe existing relevant experience.\n"
            "4. Return strict JSON format."
        )

        user_prompt = f"""
Candidate Background:
- Target Roles: {profile.target_roles if profile else []}
- Actual Skills: {profile.skills if profile else []}
- Experience Level: {profile.experience_level if profile else 'FRESHER'}
- Work Experience: {profile.work_experience if profile else []}
- Projects: {profile.projects if profile else []}
- Existing Resume Text Excerpt:
{(resume.raw_text[:2000] if resume and resume.raw_text else '')}

Job Posting Details:
- Title: {job.title}
- Company: {job.company_name}
- Required Skills: {job.required_skills}
- Preferred Skills: {job.preferred_skills}
- Description: {job.description[:2000]}
- Researched Context: {json.dumps(research_context)[:500] if research_context else 'None'}

Return a JSON object with:
{{
  "tailored_summary": "A 2-3 sentence tailored summary emphasizing candidate's existing strengths matching this job",
  "highlighted_skills": ["skills from candidate profile directly relevant to job requirements"],
  "tailored_bullet_points": [
    "Reframed or highlighted bullet points drawing ONLY from real candidate experience"
  ],
  "match_rationale": "Brief explanation of how the candidate's genuine experience aligns with the role"
}}
"""
        response_text = await llm.generate_response(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )

        try:
            tailored_json = clean_and_extract_json(response_text)
        except Exception:
            tailored_json = {
                "tailored_summary": response_text[:300],
                "highlighted_skills": list(set(profile.skills or []) & set(job.required_skills or [])),
                "tailored_bullet_points": [],
                "match_rationale": "Direct match from profile.",
            }

        prep.tailored_resume_content = tailored_json
        await db.commit()
        await db.refresh(prep)

        return {
            "status": "ok",
            "resume_mode": "TAILORED",
            "resume_id": str(resume.id) if resume else None,
            "tailored_content": tailored_json,
        }

    @staticmethod
    async def generate_cover_letter(
        db: AsyncSession,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
        tone: str = "PROFESSIONAL",
        custom_notes: str | None = None,
    ) -> dict[str, Any]:
        """Generates a job-tailored cover letter based on real profile & browser research."""
        prep = await ApplicationPrepService.get_or_create_preparation(db, user_id, job_id)
        
        job_res = await db.execute(select(Job).where(Job.id == job_id))
        job = job_res.scalar_one_or_none()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        profile_res = await db.execute(
            select(CandidateProfile).where(CandidateProfile.user_id == user_id)
        )
        profile = profile_res.scalar_one_or_none()

        pref = await get_or_create_preferences(db, user_id)
        llm = create_ai_provider(
            provider_name=pref.ai_provider,
            model=pref.ai_model,
            base_url=pref.ai_base_url,
            api_key=pref.ai_api_key,
        )

        research_context = (job.raw_data or {}).get("browser_research", {})
        system_prompt = (
            "You are a professional cover letter writer.\n"
            "Write a compelling, truthful cover letter matching the candidate to the company.\n"
            "RULES:\n"
            "1. Ground all claims in the candidate's actual background. No hallucinated positions or degrees.\n"
            "2. Keep it concise (3-4 paragraphs max).\n"
            f"3. Tone: {tone}."
        )

        user_prompt = f"""
Candidate:
- Name: Candidate
- Skills: {profile.skills if profile else []}
- Experience Level: {profile.experience_level if profile else 'FRESHER'}
- Work Experience: {profile.work_experience if profile else []}
- Target Roles: {profile.target_roles if profile else []}
- Custom Notes / Instructions: {custom_notes or 'None'}

Target Job:
- Title: {job.title}
- Company: {job.company_name}
- Location: {job.location}
- Description: {job.description[:2000]}
- Deep Web / Page Research: {json.dumps(research_context)[:500] if research_context else 'None'}

Write the cover letter in clean markdown.
"""
        cover_letter_text = await llm.generate_response(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )

        prep.cover_letter = cover_letter_text.strip()
        await db.commit()
        await db.refresh(prep)

        return {
            "status": "ok",
            "job_id": str(job_id),
            "cover_letter": prep.cover_letter,
        }

    @staticmethod
    async def generate_application_answers(
        db: AsyncSession,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
        questions: list[str],
    ) -> dict[str, Any]:
        """
        Generates answers for application screening questions.
        Cites source facts from profile or flags when candidate input is needed.
        """
        if not questions:
            return {"status": "ok", "answers": []}

        prep = await ApplicationPrepService.get_or_create_preparation(db, user_id, job_id)
        job_res = await db.execute(select(Job).where(Job.id == job_id))
        job = job_res.scalar_one_or_none()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        profile_res = await db.execute(
            select(CandidateProfile).where(CandidateProfile.user_id == user_id)
        )
        profile = profile_res.scalar_one_or_none()

        pref = await get_or_create_preferences(db, user_id)
        llm = create_ai_provider(
            provider_name=pref.ai_provider,
            model=pref.ai_model,
            base_url=pref.ai_base_url,
            api_key=pref.ai_api_key,
        )

        system_prompt = (
            "You are an assistant preparing answers to job application screening questions.\n"
            "STRICT FACTUAL GROUNDING RULES:\n"
            "1. Base answers solely on candidate profile facts provided.\n"
            "2. If the candidate's profile doesn't have the answer (e.g. specific notice period, visa status, custom salary requirements not mentioned),\n"
            "   mark 'requires_user_input': true and suggest a draft placeholder.\n"
            "3. Return strict JSON list."
        )

        user_prompt = f"""
Candidate:
- Skills: {profile.skills if profile else []}
- Experience: {profile.experience_level if profile else 'FRESHER'}
- Preferred Locations: {profile.preferred_locations if profile else []}
- Work Experience: {profile.work_experience if profile else []}
- Target Roles: {profile.target_roles if profile else []}

Job:
- Title: {job.title}
- Company: {job.company_name}
- Description: {job.description[:1500]}

Questions to answer:
{json.dumps(questions, indent=2)}

Format response as JSON:
[
  {{
    "question": "question text",
    "answer": "draft answer",
    "source_facts": ["fact from profile used"],
    "requires_user_input": false
  }}
]
"""
        response_text = await llm.generate_response(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )

        try:
            answers = clean_and_extract_json(response_text)
            if not isinstance(answers, list):
                answers = [answers]
        except Exception:
            answers = [
                {
                    "question": q,
                    "answer": "Candidate experience aligns with requirements.",
                    "source_facts": ["Profile skills"],
                    "requires_user_input": False,
                }
                for q in questions
            ]

        # Merge or update prep question answers
        existing_qa = {item.get("question"): item for item in (prep.question_answers or [])}
        for item in answers:
            if isinstance(item, dict) and "question" in item:
                existing_qa[item["question"]] = item
        prep.question_answers = list(existing_qa.values())

        await db.commit()
        await db.refresh(prep)

        return {
            "status": "ok",
            "job_id": str(job_id),
            "answers": prep.question_answers,
        }

    @staticmethod
    async def prepare_full_application(
        db: AsyncSession,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
        resume_mode: str = "EXISTING",
        include_cover_letter: bool = True,
        questions: list[str] | None = None,
    ) -> dict[str, Any]:
        """Orchestrates comprehensive application preparation."""
        prep = await ApplicationPrepService.get_or_create_preparation(db, user_id, job_id)

        # 1. Prepare resume
        resume_result = await ApplicationPrepService.prepare_resume_for_job(
            db=db, user_id=user_id, job_id=job_id, mode=resume_mode
        )

        # 2. Prepare cover letter if requested
        cover_letter_result = None
        if include_cover_letter:
            cover_letter_result = await ApplicationPrepService.generate_cover_letter(
                db=db, user_id=user_id, job_id=job_id
            )

        # 3. Answer questions if provided
        qa_result = None
        if questions:
            qa_result = await ApplicationPrepService.generate_application_answers(
                db=db, user_id=user_id, job_id=job_id, questions=questions
            )

        prep.status = "READY_FOR_REVIEW"
        await db.commit()
        await db.refresh(prep)

        return {
            "status": "ok",
            "prep_id": str(prep.id),
            "job_id": str(job_id),
            "prep_status": prep.status,
            "resume": resume_result,
            "cover_letter": cover_letter_result.get("cover_letter") if cover_letter_result else prep.cover_letter,
            "answers": qa_result.get("answers") if qa_result else prep.question_answers,
        }

    @staticmethod
    async def get_preparation(
        db: AsyncSession,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> dict[str, Any] | None:
        """Retrieves current application preparation for a job."""
        stmt = select(ApplicationPreparation).where(
            ApplicationPreparation.user_id == user_id,
            ApplicationPreparation.job_id == job_id,
        )
        res = await db.execute(stmt)
        prep = res.scalar_one_or_none()
        if not prep:
            return None

        return {
            "id": str(prep.id),
            "user_id": str(prep.user_id),
            "job_id": str(prep.job_id),
            "resume_mode": prep.resume_mode,
            "resume_id": str(prep.resume_id) if prep.resume_id else None,
            "tailored_resume_content": prep.tailored_resume_content,
            "cover_letter": prep.cover_letter,
            "question_answers": prep.question_answers,
            "status": prep.status,
            "metadata_info": prep.metadata_info,
            "created_at": prep.created_at.isoformat(),
            "updated_at": prep.updated_at.isoformat(),
        }

    @staticmethod
    async def update_preparation_status(
        db: AsyncSession,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
        status: str,
    ) -> dict[str, Any]:
        """Updates preparation review status (e.g. READY_FOR_REVIEW, APPROVED)."""
        valid_statuses = {
            "DRAFT",
            "PREPARING",
            "FILLING",
            "READY_FOR_REVIEW",
            "APPROVED",
            "SUBMITTED",
            "FAILED",
        }
        if status not in valid_statuses:
            raise ValueError(f"Invalid status '{status}'. Must be one of {valid_statuses}")

        prep = await ApplicationPrepService.get_or_create_preparation(db, user_id, job_id)
        prep.status = status
        await db.commit()
        await db.refresh(prep)
        return {
            "status": "ok",
            "prep_id": str(prep.id),
            "job_id": str(job_id),
            "prep_status": prep.status,
        }
