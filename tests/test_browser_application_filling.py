import json
import os
import sys
import uuid
import tempfile
from pathlib import Path
import pytest
from aiohttp import web

mcp_dir = Path(__file__).resolve().parent.parent / "mcp-server"
if str(mcp_dir) not in sys.path:
    sys.path.insert(0, str(mcp_dir))

from sqlalchemy import select
from server import server
from app.database import async_session_factory
from app.models.job import Job
from app.models.resume import Resume
from app.models.candidate_profile import CandidateProfile
from app.models.application_preparation import ApplicationPreparation
from app.services.user_service import get_or_create_default_user
from app.services.browser_application_service import BrowserApplicationService


# Mock HTML form simulating a company job portal application
MOCK_FORM_HTML = """
<!DOCTYPE html>
<html>
<head><title>CloudScale - Job Application</title></head>
<body>
    <h1>Application for Lead Distributed Systems Engineer</h1>
    <form id="job-app-form">
        <label for="full_name">Full Name</label>
        <input type="text" id="full_name" name="full_name" />

        <label for="email">Email</label>
        <input type="email" id="email" name="email" />

        <label for="phone">Phone</label>
        <input type="tel" id="phone" name="phone" />

        <label for="linkedin">LinkedIn</label>
        <input type="url" id="linkedin" name="linkedin" />

        <label for="resume">Attach Resume</label>
        <input type="file" id="resume" name="resume" />

        <label for="cover_letter">Cover Letter</label>
        <textarea id="cover_letter" name="cover_letter"></textarea>

        <label for="screening_q">Why are you interested in CloudScale?</label>
        <textarea id="screening_q" name="screening_q" placeholder="screening question"></textarea>

        <!-- SUBMISSION BARRIER BUTTON -->
        <button type="submit" id="submit-btn">Submit Application</button>
    </form>
</body>
</html>
"""


@pytest.mark.asyncio
async def test_browser_application_fill_and_submission_barrier():
    """
    Phase 10 Core Test:
    Verify that BrowserApplicationService navigates to application form,
    populates candidate details, answers, and resume,
    and CRITICALLY stops before clicking Submit, transitioning state to READY_FOR_REVIEW.
    """
    # 1. Run local aiohttp server serving the mock application form
    app = web.Application()
    async def form_handler(request):
        return web.Response(text=MOCK_FORM_HTML, content_type="text/html")
    app.router.add_get("/apply", form_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 8989)
    await site.start()
    mock_url = "http://127.0.0.1:8989/apply"

    # 2. Create test fixtures (User, Job, Profile, Resume, Prep)
    temp_resume_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    temp_resume_file.write(b"%PDF-1.4 Mock resume file contents")
    temp_resume_file.close()

    try:
        async with async_session_factory() as db:
            user = await get_or_create_default_user(db)
            job = Job(
                id=uuid.uuid4(),
                source="LINKEDIN",
                title="Lead Distributed Systems Engineer",
                company_name="CloudScale",
                description="Distributed systems role in Go/Python.",
                source_url="https://example.com/job/dist-lead",
                application_url=mock_url,
                job_hash=str(uuid.uuid4()),
            )
            resume = Resume(
                id=uuid.uuid4(),
                user_id=user.id,
                filename="cloudscale_resume.pdf",
                file_path=temp_resume_file.name,
                raw_text="6 years experience with Go and Python systems.",
                resume_hash=str(uuid.uuid4()),
                extracted_data={
                    "name": "John Doe Engineer",
                    "email": "john.doe@example.com",
                    "phone": "+91 9999988888",
                    "linkedin": "https://linkedin.com/in/johndoe",
                },
            )
            prof_stmt = select(CandidateProfile).where(CandidateProfile.user_id == user.id)
            profile = (await db.execute(prof_stmt)).scalar_one_or_none()
            if not profile:
                profile = CandidateProfile(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    skills=["Python", "Go", "Distributed Systems"],
                    experience_level="MID",
                    preferred_locations=["Bangalore"],
                )
                db.add(profile)
            else:
                profile.skills = ["Python", "Go", "Distributed Systems"]
                profile.preferred_locations = ["Bangalore"]

            prep = ApplicationPreparation(
                id=uuid.uuid4(),
                user_id=user.id,
                job_id=job.id,
                resume_mode="EXISTING",
                resume_id=resume.id,
                cover_letter="I am excited to apply for Lead Distributed Systems Engineer.",
                question_answers=[
                    {
                        "question": "Why are you interested in CloudScale?",
                        "answer": "CloudScale solves high throughput distributed challenges that fit my skills.",
                    }
                ],
                status="PREPARING",
            )
            db.add_all([job, resume, prep])
            await db.commit()

            # 3. Execute BrowserApplicationService
            result = await BrowserApplicationService.fill_application_form(
                db=db,
                user_id=user.id,
                job_id=job.id,
                dry_run=False,
                timeout_seconds=20,
                headless=True,
                mock_page_url=mock_url,
            )

            # 4. Verify outcomes and safety guarantees
            assert result["status"] == "ok"
            assert result["prep_status"] == "READY_FOR_REVIEW"
            assert result["stopped_before_submit"] is True
            assert result["submit_button_detected"] is True
            assert result["fields_filled_count"] >= 4

            details = result["details"]
            assert details["submit_button_detected"] is True
            assert "Submit Application" in details["submit_button_text"]
            assert len(details["files_attached"]) == 1

            # 5. Check DB persistence of audit result
            await db.refresh(prep)
            assert prep.status == "READY_FOR_REVIEW"
            assert prep.metadata_info.get("browser_fill_result") is not None
            assert prep.metadata_info["browser_fill_result"]["stopped_before_submit"] is True

            # 6. Call MCP tool fill_application directly
            tool_res = await server.call_tool(
                "fill_application",
                {"job_id": str(job.id), "dry_run": True},
            )
            assert not tool_res.is_error
            tool_data = json.loads(tool_res.content[0].text)
            assert tool_data["status"] == "ok"
            assert tool_data["stopped_before_submit"] is True

    finally:
        await runner.cleanup()
        if os.path.exists(temp_resume_file.name):
            os.remove(temp_resume_file.name)
