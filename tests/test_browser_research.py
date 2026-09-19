import json
import pytest
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

mcp_dir = Path(__file__).resolve().parent.parent / "mcp-server"
backend_dir = Path(__file__).resolve().parent.parent / "backend"
for p in [str(mcp_dir), str(backend_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from server import server
from app.services.browser_research_service import BrowserResearchService


@pytest.mark.asyncio
async def test_browser_research_tools_registration():
    """Verify research_job_page and get_job_research are registered in MCP."""
    tools = [t.name for t in server._tool_manager.list_tools()]
    assert "research_job_page" in tools
    assert "get_job_research" in tools


@pytest.mark.asyncio
async def test_browser_research_service_invalid_url():
    """Verify invalid URL returns proper error object without crashing."""
    res = await BrowserResearchService.inspect_page("invalid://bad-url")
    assert res["status"] == "error"
    assert "Invalid URL" in res["error"]


@pytest.mark.asyncio
async def test_browser_research_service_parse():
    """Verify HTML parsing extracts text, flags forms, and identifies closed jobs."""
    html_sample = """
    <html>
      <head><title>Senior AI Engineer - TechCorp</title></head>
      <body>
        <script>var x = 1;</script>
        <h1>Job Opening: Senior AI Engineer</h1>
        <p>Tech stack: Python, FastAPI, PyTorch, LangChain, PostgreSQL.</p>
        <p>Position has been filled.</p>
        <form action="/apply"><input type="text" name="name"/></form>
      </body>
    </html>
    """
    parsed = BrowserResearchService._parse_content(
        url="https://example.com/job/123",
        final_url="https://example.com/job/123",
        status_code=200,
        title="Senior AI Engineer - TechCorp",
        html=html_sample,
        engine="test",
    )
    assert parsed["status"] == "ok"
    assert parsed["page_title"] == "Senior AI Engineer - TechCorp"
    assert "Tech stack: Python" in parsed["extracted_text"]
    assert parsed["has_apply_form"] is True
    assert parsed["is_closed"] is True


@pytest.mark.asyncio
async def test_mcp_research_job_page_not_found():
    """Verify research_job_page returns not found error for nonexistent job ID."""
    fake_id = str(uuid.uuid4())
    res = await server.call_tool("research_job_page", {"job_id": fake_id})
    assert not res.is_error
    data = json.loads(res.content[0].text)
    assert data["status"] == "error"
    assert f"Job with ID {fake_id} not found" in data["error"]


@pytest.mark.asyncio
async def test_mcp_research_job_page_execution():
    """Verify research_job_page runs inspect_page and persists research findings."""
    from app.database import async_session_factory
    from app.models.job import Job

    job_id = uuid.uuid4()
    async with async_session_factory() as db:
        test_job = Job(
            id=job_id,
            source="linkedin",
            title="Senior Backend Engineer",
            company_name="Acme Global",
            description="Build scalable distributed microservices.",
            source_url="https://example.com/jobs/backend-engineer",
            application_url="https://example.com/apply/backend-engineer",
            job_hash=f"test_hash_{job_id}",
            raw_data={},
        )
        db.add(test_job)
        await db.commit()

    mock_inspect = {
        "status": "ok",
        "url": "https://example.com/apply/backend-engineer",
        "final_url": "https://example.com/apply/backend-engineer",
        "http_status": 200,
        "page_title": "Senior Backend Engineer at Acme Global",
        "is_closed": False,
        "has_apply_form": True,
        "extracted_text": "We are looking for Python and FastAPI specialists.",
        "char_count": 52,
        "researched_at": "2026-09-20T03:20:00Z",
        "engine": "httpx",
    }

    with patch.object(BrowserResearchService, "inspect_page", new=AsyncMock(return_value=mock_inspect)):
        call_res = await server.call_tool("research_job_page", {"job_id": str(job_id)})
        assert not call_res.is_error
        res_data = json.loads(call_res.content[0].text)
        assert res_data["status"] == "ok"
        assert res_data["job_title"] == "Senior Backend Engineer"
        assert res_data["research"]["page_title"] == "Senior Backend Engineer at Acme Global"

        # Check get_job_research retrieval
        cached_res = await server.call_tool("get_job_research", {"job_id": str(job_id)})
        assert not cached_res.is_error
        cached_data = json.loads(cached_res.content[0].text)
        assert cached_data["status"] == "ok"
        assert cached_data["research"]["has_apply_form"] is True
        assert cached_data["research"]["engine"] == "httpx"
