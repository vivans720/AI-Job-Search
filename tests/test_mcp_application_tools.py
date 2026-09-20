import json
import pytest
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

mcp_dir = Path(__file__).resolve().parent.parent / "mcp-server"
if str(mcp_dir) not in sys.path:
    sys.path.insert(0, str(mcp_dir))

from server import server
from app.database import async_session_factory
from app.models.job import Job
from app.models.resume import Resume
from app.models.candidate_profile import CandidateProfile
from app.services.user_service import get_or_create_default_user


@pytest.mark.asyncio
async def test_mcp_application_prep_tools_registration():
    """Verify Phase 9 application preparation tools are registered."""
    tools = [t.name for t in server._tool_manager.list_tools()]
    phase9_tools = [
        "prepare_application",
        "prepare_resume",
        "generate_cover_letter",
        "generate_application_answers",
        "get_application_preparation",
        "fill_application",
    ]
    for t in phase9_tools:
        assert t in tools, f"Missing tool: {t}"

    # Guardrail: Form submission must NOT exist in Phase 9 or Phase 10
    assert "submit_application" not in tools
    assert "auto_apply" not in tools


@pytest.mark.asyncio
async def test_mcp_prepare_application_tool_flow():
    """Verify calling prepare_application MCP tool creates artifacts and enters READY_FOR_REVIEW."""
    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)
        job = Job(
            id=uuid.uuid4(),
            source="LINKEDIN",
            title="Lead Distributed Systems Engineer",
            company_name="CloudScale",
            description="Build resilient high-throughput distributed systems in Python and Go.",
            source_url="https://example.com/job/dist-lead",
            application_url="https://example.com/job/dist-lead/apply",
            job_hash=str(uuid.uuid4()),
            required_skills=["Python", "Go", "Distributed Systems"],
        )
        resume = Resume(
            id=uuid.uuid4(),
            user_id=user.id,
            filename="primary_resume.pdf",
            raw_text="Over 6 years of backend engineering in Python and distributed systems.",
            resume_hash=str(uuid.uuid4()),
            is_active=True,
        )
        from app.services.profile_service import get_candidate_profile
        profile = await get_candidate_profile(db, user.id)
        if not profile:
            profile = CandidateProfile(
                user_id=user.id,
                skills=["Python", "Go", "Distributed Systems", "PostgreSQL"],
                target_roles=["Distributed Systems Engineer"],
                experience_level="FRESHER",
            )
            db.add(profile)
        else:
            profile.skills = ["Python", "Go", "Distributed Systems", "PostgreSQL"]
            profile.target_roles = ["Distributed Systems Engineer"]
            profile.experience_level = "FRESHER"

        db.add_all([job, resume])
        await db.commit()

        job_id_str = str(job.id)

    mock_cl = "Dear CloudScale Team,\n\nI am thrilled to apply for Lead Distributed Systems Engineer..."
    mock_qa = json.dumps([
        {
            "question": "What is your experience with Go?",
            "answer": "Built high-throughput services using Go.",
            "source_facts": ["Go in candidate profile skills"],
            "requires_user_input": False
        }
    ])

    with patch("app.services.application_prep_service.create_ai_provider") as mock_create_ai:
        mock_provider = AsyncMock()
        mock_provider.generate_response.side_effect = [mock_cl, mock_qa]
        mock_create_ai.return_value = mock_provider

        # 1. Call prepare_application tool
        prep_res = await server.call_tool(
            "prepare_application",
            {
                "job_id": job_id_str,
                "resume_mode": "EXISTING",
                "include_cover_letter": True,
                "questions": ["What is your experience with Go?"],
            },
        )
        assert not prep_res.is_error
        data = json.loads(prep_res.content[0].text)
        assert data["status"] == "ok"
        assert data["prep_status"] == "READY_FOR_REVIEW"
        assert "Dear CloudScale Team" in data["cover_letter"]
        assert len(data["answers"]) == 1

        # 2. Verify retrieval via get_application_preparation tool
        get_res = await server.call_tool("get_application_preparation", {"job_id": job_id_str})
        assert not get_res.is_error
        get_data = json.loads(get_res.content[0].text)
        assert get_data["status"] == "ok"
        prep_record = get_data["preparation"]
        assert prep_record["status"] == "READY_FOR_REVIEW"
        assert prep_record["resume_mode"] == "EXISTING"
