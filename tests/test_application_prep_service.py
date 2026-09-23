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
          "categorized_skills": {
            "Languages": ["Python"],
            "Frameworks": ["FastAPI", "PyTorch"]
          },
          "highlighted_skills": ["PyTorch", "FastAPI"],
          "experience": [
            {
              "source_experience_index": 0,
              "selected_bullets": [
                {
                  "source_bullet_index": 0,
                  "content": "Built machine learning pipelines with PyTorch and FastAPI"
                }
              ]
            }
          ]
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
            assert "Languages" in result["tailored_content"]["categorized_skills"]

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
        resume = Resume(
            id=uuid.uuid4(),
            user_id=user.id,
            filename="resume.pdf",
            raw_text="Experienced engineer specializing in distributed backend architecture and high-throughput Python pipelines.",
            extracted_data={
                "candidate_name": "Alex Mercer",
                "email": "alex.mercer@example.com",
            },
            resume_hash="dummyhash123",
            is_active=True,
        )
        db_session.add_all([user, job, profile, resume])
        await db_session.commit()

        mock_cl_json = """
        {
          "opening": "I am thrilled to apply for the Senior Backend Lead role at NextGen.",
          "evidence_paragraph": "Over 5 years building scalable distributed backends with Python.",
          "company_connection": "NextGen's high-throughput architecture aligns with my background.",
          "closing": "I look forward to discussing how my experience can support your team."
        }
        """
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
            mock_provider.generate_response.side_effect = [mock_cl_json, mock_answers_json]
            mock_create_ai.return_value = mock_provider

            # Test cover letter
            cl_res = await ApplicationPrepService.generate_cover_letter(
                db=db_session, user_id=user.id, job_id=job.id, tone="PROFESSIONAL"
            )
            assert cl_res["status"] == "ok"
            assert "Senior Backend Lead role at NextGen" in cl_res["cover_letter"]
            # Verify prompt contained candidate info and strict grounding
            call_args = mock_provider.generate_response.call_args_list[0]
            messages = call_args[1]["messages"] if "messages" in call_args[1] else call_args[0][0]
            user_msg = next(m["content"] for m in messages if m["role"] == "user")
            system_msg = next(m["content"] for m in messages if m["role"] == "system")
            assert "Alex Mercer" in user_msg
            assert "TONE: PROFESSIONAL" in user_msg
            assert "DO NOT GENERATE HEADERS" in system_msg


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


@pytest.mark.asyncio
async def test_get_or_create_preparation_duplicate_concurrency():
    async with async_session_factory() as db_session:
        user = User(id=uuid.uuid4(), email=f"user-{uuid.uuid4()}@example.com")
        job = Job(
            id=uuid.uuid4(),
            source="LINKEDIN",
            title="Backend Engineer",
            company_name="Acme",
            description="Backend role",
            source_url="https://example.com/job",
            application_url="https://example.com/job/apply",
            job_hash=str(uuid.uuid4()),
        )
        db_session.add_all([user, job])
        await db_session.commit()

        # Pre-create the preparation record
        prep1 = await ApplicationPrepService.get_or_create_preparation(db_session, user.id, job.id)
        assert prep1 is not None

        # Simulate a duplicate creation attempt where select initially returns None (simulating race)
        # but commit raises IntegrityError due to existing (user_id, job_id)
        with patch.object(db_session, "commit") as mock_commit:
            from sqlalchemy.exc import IntegrityError
            mock_commit.side_effect = IntegrityError("duplicate key", params=None, orig=Exception("UniqueViolationError"))
            
            # Second call should handle IntegrityError, rollback, and return the existing record
            prep2 = await ApplicationPrepService.get_or_create_preparation(db_session, user.id, job.id)
            assert prep2.id == prep1.id


@pytest.mark.asyncio
async def test_openai_compatible_provider_generate_response():
    from app.intelligence.providers.openai_compatible import OpenAICompatibleProvider
    from unittest.mock import MagicMock

    provider = OpenAICompatibleProvider(
        base_url="https://api.openai.com/v1",
        api_key="test-key",
        model="gpt-4o-mini",
    )
    with patch.object(provider, "complete", new_callable=AsyncMock) as mock_complete:
        mock_complete.return_value = "Generated text content"
        res = await provider.generate_response([{"role": "user", "content": "Hello"}])
        assert res == "Generated text content"
        mock_complete.assert_awaited_once_with([{"role": "user", "content": "Hello"}])


@pytest.mark.asyncio
async def test_resume_metric_preservation_and_grounding():
    # Unit test validating _validate_and_sanitize_resume metric preservation & hallucination checks
    source_exp = [
        {
            "title": "Senior Engineer",
            "company": "ScaleTech",
            "description": [
                "Reduced API latency by 45% and improved throughput to 50k RPS.",
                "Mentored 6 junior engineers and optimized SQL queries."
            ]
        }
    ]
    source_proj = [
        {
            "name": "Search Engine",
            "technologies": ["Python", "Elasticsearch"],
            "description": ["Built distributed search indexing 2M documents."]
        }
    ]
    candidate_skills = ["Python", "FastAPI", "PostgreSQL", "Elasticsearch", "Docker"]
    candidate_catalog = {
        "Languages": ["Python"],
        "Databases": ["PostgreSQL", "Elasticsearch"],
        "Cloud / DevOps": ["Docker"]
    }

    # Case 1: LLM tries to strip metrics (e.g. changing 45% to "significantly") and inject fake skill "Kubernetes"
    llm_output_degraded = {
        "tailored_summary": "Expert engineer focused on high performance systems.",
        "categorized_skills": {
            "Languages": ["Python"],
            "Cloud / DevOps": ["Kubernetes"]  # Hallucinated skill not in candidate_skills
        },
        "highlighted_skills": ["Python"],
        "experience": [
            {
                "source_experience_index": 0,
                "selected_bullets": [
                    {
                        "source_bullet_index": 0,
                        "content": "Optimized API latency significantly and scaled throughput."  # Missing 45% and 50k RPS!
                    }
                ]
            }
        ],
        "projects": [
            {
                "source_project_index": 0,
                "selected_bullets": [
                    {
                        "source_bullet_index": 0,
                        "content": "Built search system indexing millions of docs."
                    }
                ]
            }
        ]
    }

    sanitized = ApplicationPrepService._validate_and_sanitize_resume(
        tailored_json=llm_output_degraded,
        source_exp=source_exp,
        source_proj=source_proj,
        candidate_skills=candidate_skills,
        candidate_skills_catalog=candidate_catalog,
    )

    # 1. Verify hallucinated skill "Kubernetes" was stripped
    assert "Kubernetes" not in sanitized["categorized_skills"].get("Cloud / DevOps", [])

    # 2. Verify degraded bullet was reverted to original to preserve exact metric "45%" and "50k RPS"
    exp_bullets = sanitized["experience"][0]["selected_bullets"]
    assert len(exp_bullets) > 0
    assert "45%" in exp_bullets[0]["content"]
    assert "50k RPS" in exp_bullets[0]["content"]


@pytest.mark.asyncio
async def test_cover_letter_tones_and_research():
    async with async_session_factory() as db_session:
        user = User(id=uuid.uuid4(), email=f"user-{uuid.uuid4()}@example.com")
        job = Job(
            id=uuid.uuid4(),
            source="LINKEDIN",
            title="Principal AI Architect",
            company_name="InnovateAI",
            description="Leading multimodal model deployments and vector retrieval architectures.",
            source_url="https://example.com/ai",
            application_url="https://example.com/ai/apply",
            job_hash=str(uuid.uuid4()),
            raw_data={
                "browser_research": {
                    "company_summary": "InnovateAI builds enterprise multimodal RAG platforms.",
                    "products": ["SearchCopilot", "VisionEngine"],
                    "tech_stack": ["Python", "PyTorch", "Kubernetes"]
                }
            }
        )
        profile = CandidateProfile(
            user_id=user.id,
            skills=["Python", "PyTorch", "System Design"],
            target_roles=["AI Architect"],
            experience_level="SENIOR",
        )
        db_session.add_all([user, job, profile])
        await db_session.commit()

        mock_concise_json = """
        {
          "opening": "I am applying for the Principal AI Architect position at InnovateAI.",
          "evidence_paragraph": "Built multimodal search serving 2M users with 99.9% uptime.",
          "company_connection": "Your work on SearchCopilot directly mirrors my production experience.",
          "closing": "Let us schedule a conversation to discuss architectural alignment."
        }
        """

        with patch("app.services.application_prep_service.create_ai_provider") as mock_create_ai:
            mock_provider = AsyncMock()
            mock_provider.generate_response.return_value = mock_concise_json
            mock_create_ai.return_value = mock_provider

            # Generate CONCISE cover letter
            cl_res = await ApplicationPrepService.generate_cover_letter(
                db=db_session, user_id=user.id, job_id=job.id, tone="CONCISE"
            )
            assert cl_res["status"] == "ok"
            assert "SearchCopilot" in cl_res["cover_letter"]
            assert "Principal AI Architect" in cl_res["cover_letter"]

            # Verify prompt received normalized research and concise tone instructions
            call_args = mock_provider.generate_response.call_args_list[0]
            messages = call_args[1]["messages"] if "messages" in call_args[1] else call_args[0][0]
            user_msg = next(m["content"] for m in messages if m["role"] == "user")
            assert "TONE: CONCISE" in user_msg
            assert "SearchCopilot" in user_msg
            assert "InnovateAI builds enterprise multimodal" in user_msg

