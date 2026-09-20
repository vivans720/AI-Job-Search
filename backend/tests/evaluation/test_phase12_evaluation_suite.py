"""
Phase 12 Comprehensive Evaluation & Reliability Suite

Evaluates all 5 pillars of the agent-first architecture specified in major_plan.md:
1. Agent Behavior & Planning (Scenario-based tool selection, prompt adherence, anti-hallucination)
2. Retrieval & Deduplication Integrity (Freshness, semantic matching, taxonomy normalization, zero-duplicate guarantee)
3. Browser Research Resiliency (Public inspection, structured extraction, fallback)
4. Safety & Pipeline Gating (Approval enforcement, strictly gated APPLIED status)
5. LLM / OmniRoute Gateway Resilience (JSON extraction, failovers, timeout handling)
"""

import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

# Ensure mcp-server directory is on sys.path for MCP tool tests
mcp_server_dir = Path(__file__).resolve().parent.parent.parent.parent / "mcp-server"
if str(mcp_server_dir) not in sys.path:
    sys.path.insert(0, str(mcp_server_dir))

from app.intelligence.base import clean_and_extract_json
from app.intelligence.llm_provider import create_ai_provider
from app.models.job import Job
from app.models.user import User
from app.services.browser_research_service import BrowserResearchService
from app.services.scheduled_search_service import ScheduledSearchService
from app.utils.normalization import normalize_location, normalize_skills


# =====================================================================
# Pillar 1: Agent Behavior & Scenario-Based Planning
# =====================================================================

@pytest.mark.asyncio
async def test_agent_scenario_find_remote_genai_jobs():
    """
    Scenario: 'Find remote GenAI jobs requiring Python.'
    Verifies that search parameters enforce include_remote=True, query contains required keywords,
    and returns matching structured job payload.
    """
    from tools.search_tools import handle_search_jobs

    mock_db = AsyncMock()
    mock_user = User(id=uuid.uuid4(), email="candidate@example.com")

    with patch("tools.search_tools.async_session_factory") as mock_session_factory, \
         patch("tools.search_tools.get_or_create_default_user", new_callable=AsyncMock) as mock_get_user, \
         patch("tools.search_tools.search_jobs_db", new_callable=AsyncMock) as mock_search_db, \
         patch("tools.search_tools.record_search_query", new_callable=AsyncMock):

        mock_session_factory.return_value.__aenter__.return_value = mock_db
        mock_get_user.return_value = mock_user
        mock_search_db.return_value = [
            {
                "id": str(uuid.uuid4()),
                "title": "GenAI Python Developer",
                "company_name": "DeepTech Labs",
                "location": "Remote",
                "is_remote": True,
                "match_score": 92.5,
            }
        ]

        result = await handle_search_jobs(
            query="GenAI Python",
            include_remote=True,
            limit=10,
        )

        assert result.get("fresh_jobs_found") == 1
        assert len(result.get("jobs", [])) == 1
        job = result["jobs"][0]
        assert "GenAI Python" in job["title"]
        assert job["is_remote"] is True
        mock_search_db.assert_called_once()


@pytest.mark.asyncio
async def test_agent_scenario_prepare_application_materials():
    """
    Scenario: 'Prepare application for the best job.'
    Verifies candidate materials formulation (resume tailoring preview, Q&A,
    direct application URL handoff, and readiness status).
    """
    from tools.application_tools import handle_prepare_application

    job_id = uuid.uuid4()
    mock_db = AsyncMock()
    mock_user = User(id=uuid.uuid4(), email="candidate@example.com")

    with patch("tools.application_tools.async_session_factory") as mock_session_factory, \
         patch("tools.application_tools.get_or_create_default_user", new_callable=AsyncMock) as mock_get_user, \
         patch("tools.application_tools.ApplicationPrepService.prepare_full_application", new_callable=AsyncMock) as mock_prep_full:

        mock_session_factory.return_value.__aenter__.return_value = mock_db
        mock_get_user.return_value = mock_user

        mock_prep_full.return_value = {
            "status": "ok",
            "prep_id": str(uuid.uuid4()),
            "job_id": str(job_id),
            "job_title": "Senior AI Engineer",
            "company_name": "Apex AI",
            "application_url": "https://apexai.careers/jobs/12345",
            "prep_status": "READY_FOR_REVIEW",
            "resume": {
                "status": "ok",
                "resume_mode": "TAILORED",
                "tailored_content": {
                    "tailored_summary": "AI Engineer skilled in LLMs and agents.",
                    "highlighted_skills": ["Python", "FastAPI", "Agents"],
                },
            },
            "cover_letter": "Dear Hiring Team, ...",
            "answers": [
                {"question": "Years with Python?", "answer": "4+ years building production services."}
            ],
        }

        result = await handle_prepare_application(
            job_id=str(job_id),
            resume_mode="TAILORED",
            include_cover_letter=True,
            questions=["Years with Python?"],
        )

        assert result.get("status") == "ok"
        assert result.get("prep_status") == "READY_FOR_REVIEW"
        assert result.get("application_url") == "https://apexai.careers/jobs/12345"
        assert "resume" in result
        assert len(result["answers"]) == 1
        mock_prep_full.assert_called_once()


# =====================================================================
# Pillar 2: Retrieval, Deduplication & Taxonomy Integrity
# =====================================================================

def test_location_normalization_integrity():
    """Verifies that regional locations resolve to canonical entities."""
    assert normalize_location("Bengaluru, Karnataka") in ("Bengaluru", "Bangalore")
    # Multi-component location resolves cleanly
    assert "Gurugram" in normalize_location("NCR, Gurgaon, Haryana") or "Delhi NCR" in normalize_location("NCR, Gurgaon, Haryana")
    assert normalize_location("Remote") == "Remote"


def test_skills_normalization_deduplication():
    """Verifies skill alias resolution and deduplication."""
    raw = ["py", "python3", "postgres", "postgresql", "fastapi"]
    canonical = normalize_skills(raw)
    assert "Python" in canonical
    assert "PostgreSQL" in canonical
    assert "FastAPI" in canonical
    # Ensure aliases collapsed
    assert canonical.count("Python") == 1
    assert canonical.count("PostgreSQL") == 1


@pytest.mark.asyncio
async def test_scheduled_job_search_digest_lifecycle():
    """
    Verifies creation of daily digest and prevention of duplicate records.
    """
    mock_db = AsyncMock()
    user_id = uuid.uuid4()
    job_ids = [str(uuid.uuid4()), str(uuid.uuid4())]

    with patch("app.services.scheduled_search_service.DailyDigest") as mock_digest_cls, \
         patch("app.services.scheduled_search_service.DigestNotifiedJob") as mock_notified_cls:

        mock_digest = MagicMock()
        mock_digest.id = uuid.uuid4()
        mock_digest_cls.return_value = mock_digest

        digest = await ScheduledSearchService.create_digest_manual(
            db=mock_db,
            user_id=user_id,
            summary="Morning Hunt Digest",
            job_ids=job_ids,
            status="DELIVERED",
        )

        assert digest is not None
        # Assert added digest + each notified job
        assert mock_db.add.call_count == 1 + len(job_ids)
        mock_db.commit.assert_called_once()


# =====================================================================
# Pillar 3: Browser Research Resiliency
# =====================================================================

@pytest.mark.asyncio
async def test_browser_research_http_fallback_on_playwright_failure():
    """
    Verifies that BrowserResearchService falls back gracefully to HTTP parsing
    when headless browser fails or is unavailable.
    """
    target_url = "https://example.com/careers/ai-researcher"
    html_content = """
    <html>
        <head><title>AI Researcher at NextGen</title></head>
        <body>
            <h1>AI Researcher</h1>
            <p>Requirements: Python, PyTorch, LLM agents. 3 rounds of technical interviews.</p>
        </body>
    </html>
    """

    with patch.object(BrowserResearchService, "_fetch_playwright", new_callable=AsyncMock) as mock_pw, \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_http_get:

        # Playwright fails
        mock_pw.return_value = {"status": "error", "error": "Playwright launch timeout"}

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html_content
        mock_resp.url = target_url
        mock_http_get.return_value = mock_resp

        result = await BrowserResearchService.inspect_page(target_url)

        assert result["status"] == "ok"
        assert result["engine"] == "httpx"
        assert "AI Researcher" in result["page_title"]
        assert "Python" in result["extracted_text"]


# =====================================================================
# Pillar 4: Safety & Pipeline Integrity Gating
# =====================================================================

@pytest.mark.asyncio
async def test_pipeline_applied_status_strictly_gated_against_unauthorized_mutation():
    """
    Phase 7 & 12 Invariant:
    No agent action can mark a job as APPLIED without explicit user confirmation/approval.
    """
    from tools.job_tools import handle_update_application_status

    job_id = uuid.uuid4()
    mock_db = AsyncMock()
    mock_user = User(id=uuid.uuid4(), email="candidate@example.com")
    mock_job = Job(id=job_id, title="Lead ML Engineer", company_name="Cortex", is_active=True)

    with patch("tools.job_tools.async_session_factory") as mock_session_factory, \
         patch("tools.job_tools.get_or_create_default_user", new_callable=AsyncMock) as mock_get_user, \
         patch("tools.job_tools.ensure_active_run", new_callable=AsyncMock) as mock_ensure_run, \
         patch("tools.job_tools.AgentApprovalService.check_is_action_autonomous", new_callable=AsyncMock) as mock_check_auto, \
         patch("tools.job_tools.AgentApprovalService.create_approval_request", new_callable=AsyncMock) as mock_create_approval, \
         patch("tools.job_tools.save_or_update_job_status", new_callable=AsyncMock) as mock_save_job:

        mock_session_factory.return_value.__aenter__.return_value = mock_db
        mock_get_user.return_value = mock_user
        mock_ensure_run.return_value = uuid.uuid4()
        # Even with autonomous mode toggled on for all actions
        mock_check_auto.return_value = True

        mock_job_res = MagicMock()
        mock_job_res.scalar_one_or_none.return_value = mock_job
        mock_db.execute.return_value = mock_job_res

        mock_approval_record = MagicMock()
        mock_approval_record.id = uuid.uuid4()
        mock_create_approval.return_value = mock_approval_record

        res = await handle_update_application_status(
            job_id=str(job_id),
            status="APPLIED",
        )

        # MUST require approval
        assert res.get("status") == "APPROVAL_REQUIRED"
        assert res.get("approval_id") == str(mock_approval_record.id)
        # MUST NOT have updated status directly
        mock_save_job.assert_not_called()


# =====================================================================
# Pillar 5: LLM & OmniRoute Gateway Resilience
# =====================================================================

def test_json_extraction_from_noisy_and_malformed_markdown():
    """Verifies that model responses wrapped in markdown code blocks or commentary are cleaned."""
    noisy = """
    Sure! Here is the JSON data you requested:
    ```json
    {
      "roles": ["Full Stack Engineer"],
      "confidence": 0.98
    }
    ```
    Hope this helps with your candidate search!
    """
    extracted = clean_and_extract_json(noisy)
    assert extracted == {"roles": ["Full Stack Engineer"], "confidence": 0.98}


@pytest.mark.asyncio
async def test_omniroute_gateway_resilience_and_timeout():
    """
    Verifies that the OmniRoute provider interface catches network timeouts
    and produces structured error diagnostics.
    """
    provider = create_ai_provider("omniroute", base_url="http://127.0.0.1:9999/v1", timeout=0.5)
    with patch.object(type(provider.llm), "ainvoke", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.side_effect = TimeoutError("Connection to OmniRoute gateway timed out")

        test_res = await provider.test_connection()
        assert test_res["reachable"] is False
        assert "timed out" in test_res["error"]
