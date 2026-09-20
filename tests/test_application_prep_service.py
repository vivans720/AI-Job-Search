import uuid
import pytest
from unittest.mock import AsyncMock, patch

from app.database import async_session_factory
from app.models.application_preparation import ApplicationPreparation
from app.models.candidate_profile import CandidateProfile
from app.models.job import Job
from app.models.resume import Resume
from app.models.user import User
from app.services.application_prep_service import ApplicationPrepService


@pytest.mark.asyncio
async def test_prepare_resume_existing():
    async with async_session_factory() as db_session:
        user = User(id=uuid.uuid4(), email=f"user-{uuid.uuid4()}@example.com")
        job = Job(
            id=uuid.uuid4(),
            source="LINKEDIN",
            title="Senior Python Backend Engineer",
            company_name="Acme Inc",
            description="Looking for senior python dev with fastapi and postgres",
            source_url="https://example.com/job",
            application_url="https://example.com/job/apply",
            job_hash=str(uuid.uuid4()),
            required_skills=["Python", "FastAPI"],
        )
        resume = Resume(
            id=uuid.uuid4(),
            user_id=user.id,
            filename="resume.pdf",
            raw_text="Experienced Python engineer with 4 years building APIs",
            resume_hash=str(uuid.uuid4()),
            is_active=True,
        )
        profile = CandidateProfile(
            user_id=user.id,
            skills=["Python", "PostgreSQL", "Docker"],
            target_roles=["Backend Engineer"],
            experience_level="MID",
        )
        db_session.add_all([user, job, resume, profile])
        await db_session.commit()

        # Test EXISTING mode
        result = await ApplicationPrepService.prepare_resume_for_job(
            db=db_session, user_id=user.id, job_id=job.id, mode="EXISTING"
        )
        assert result["status"] == "ok"
        assert result["resume_mode"] == "EXISTING"
        assert result["resume_id"] == str(resume.id)

        prep = await ApplicationPrepService.get_or_create_preparation(db_session, user.id, job.id)
        assert prep.resume_mode == "EXISTING"
        assert prep.tailored_resume_content is None


@pytest.mark.asyncio
async def test_prepare_resume_tailored_anti_hallucination():
    async with async_session_factory() as db_session:
        user = User(id=uuid.uuid4(), email=f"user-{uuid.uuid4()}@example.com")
        job = Job(
            id=uuid.uuid4(),
            source="LINKEDIN",
            title="AI Engineer",
            company_name="TechCorp",
            description="Requires PyTorch, LangChain, and FastAPI",
            source_url="https://example.com/ai-job",
            application_url="https://example.com/ai-job/apply",
            job_hash=str(uuid.uuid4()),
            required_skills=["PyTorch", "FastAPI"],
        )
        resume = Resume(
            id=uuid.uuid4(),
            user_id=user.id,
            filename="ai_resume.pdf",
            raw_text="Built machine learning pipelines using PyTorch and FastAPI.",
            resume_hash=str(uuid.uuid4()),
            is_active=True,
        )
        profile = CandidateProfile(
            user_id=user.id,
            skills=["PyTorch", "FastAPI", "Python"],
            target_roles=["AI Engineer"],
            experience_level="MID",
        )
        db_session.add_all([user, job, resume, profile])
        await db_session.commit()

        mock_llm_response = """
        {
          "tailored_summary": "Experienced engineer with PyTorch and FastAPI expertise.",
          "highlighted_skills": ["PyTorch", "FastAPI"],
          "tailored_bullet_points": ["Built machine learning pipelines with PyTorch and FastAPI"],
          "match_rationale": "Direct overlap on key ML & API skills"
        }
        """

        with patch("app.services.application_prep_service.create_ai_provider") as mock_create_ai:
            mock_provider = AsyncMock()
            mock_provider.generate_response.return_value = mock_llm_response
            mock_create_ai.return_value = mock_provider

            result = await ApplicationPrepService.prepare_resume_for_job(
                db=db_session, user_id=user.id, job_id=job.id, mode="TAILORED"
            )
            assert result["status"] == "ok"
            assert result["resume_mode"] == "TAILORED"
            assert result["tailored_content"]["highlighted_skills"] == ["PyTorch", "FastAPI"]

            prep = await ApplicationPrepService.get_or_create_preparation(db_session, user.id, job.id)
            assert prep.resume_mode == "TAILORED"
            assert prep.tailored_resume_content["highlighted_skills"] == ["PyTorch", "FastAPI"]


@pytest.mark.asyncio
async def test_generate_cover_letter_and_answers():
    async with async_session_factory() as db_session:
        user = User(id=uuid.uuid4(), email=f"user-{uuid.uuid4()}@example.com")
        job = Job(
            id=uuid.uuid4(),
            source="NAUKRI",
            title="Senior Backend Lead",
            company_name="NextGen",
            description="Lead engineering team building distributed systems.",
            source_url="https://example.com/lead",
            application_url="https://example.com/lead/apply",
            job_hash=str(uuid.uuid4()),
            required_skills=["Python", "System Design"],
        )
        profile = CandidateProfile(
            user_id=user.id,
            skills=["Python", "System Design"],
            target_roles=["Backend Lead"],
            experience_level="SENIOR",
        )
        db_session.add_all([user, job, profile])
        await db_session.commit()

        mock_cl_text = "Dear Hiring Manager,\n\nI am thrilled to apply for the Senior Backend Lead position..."
        mock_answers_json = """
        [
          {
            "question": "What is your experience with Python?",
            "answer": "Over 5 years building scalable distributed backends.",
            "source_facts": ["Python in profile skills"],
            "requires_user_input": false
          }
        ]
        """

        with patch("app.services.application_prep_service.create_ai_provider") as mock_create_ai:
            mock_provider = AsyncMock()
            mock_provider.generate_response.side_effect = [mock_cl_text, mock_answers_json]
            mock_create_ai.return_value = mock_provider

            # Test cover letter
            cl_res = await ApplicationPrepService.generate_cover_letter(
                db=db_session, user_id=user.id, job_id=job.id
            )
            assert cl_res["status"] == "ok"
            assert "Dear Hiring Manager" in cl_res["cover_letter"]

            # Test question answers
            ans_res = await ApplicationPrepService.generate_application_answers(
                db=db_session,
                user_id=user.id,
                job_id=job.id,
                questions=["What is your experience with Python?"],
            )
            assert ans_res["status"] == "ok"
            assert len(ans_res["answers"]) == 1
            assert ans_res["answers"][0]["question"] == "What is your experience with Python?"

            # Test status transitions
            status_res = await ApplicationPrepService.update_preparation_status(
                db=db_session, user_id=user.id, job_id=job.id, status="READY_FOR_REVIEW"
            )
            assert status_res["prep_status"] == "READY_FOR_REVIEW"

            status_res2 = await ApplicationPrepService.update_preparation_status(
                db=db_session, user_id=user.id, job_id=job.id, status="APPROVED"
            )
            assert status_res2["prep_status"] == "APPROVED"
