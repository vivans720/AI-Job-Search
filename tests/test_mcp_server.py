import json
import pytest
import sys
from pathlib import Path

# Add mcp-server directory
mcp_dir = Path(__file__).resolve().parent.parent / "mcp-server"
if str(mcp_dir) not in sys.path:
    sys.path.insert(0, str(mcp_dir))

from server import server


@pytest.mark.asyncio
async def test_mcp_tools_registration():
    """Verify all Phase 2 specified MCP tools are registered and strictly no auto-apply or raw SQL tools exist."""
    tools = [t.name for t in server._tool_manager.list_tools()]
    
    # Required Phase 2 spec tools
    phase2_required_tools = [
        "get_candidate_profile",
        "get_preferences",
        "search_jobs",
        "get_job",
        "get_jobs",
        "semantic_search_jobs",
        "sync_jobs",
        "save_job",
        "dismiss_job",
        "get_pipeline",
        "get_application",
        "update_application",
        "update_preferences",
    ]
    for t in phase2_required_tools:
        assert t in tools, f"Missing required Phase 2 tool: {t}"

    # Strict guardrails against autonomous submission or unrestricted DB execution
    assert "apply_job" not in tools
    assert "submit_application" not in tools
    assert "auto_apply" not in tools
    assert "execute_sql" not in tools
    assert "run_query" not in tools


@pytest.mark.asyncio
async def test_mcp_get_candidate_profile():
    """Verify get_candidate_profile tool execution returns valid profile."""
    result = await server.call_tool("get_candidate_profile", {})
    assert not result.is_error
    data = json.loads(result.content[0].text)
    assert data["status"] == "ok"
    assert "target_roles" in data
    assert "skills" in data
    assert data["experience_level"].upper() in ("ENTRY_LEVEL", "FRESHER")
    assert data["experience_years"] == 0


@pytest.mark.asyncio
async def test_mcp_get_and_update_preferences():
    """Verify get_preferences and update_preferences tools work correctly."""
    get_res = await server.call_tool("get_preferences", {})
    assert not get_res.is_error
    pref_data = json.loads(get_res.content[0].text)
    assert pref_data["status"] == "ok"
    assert "freshness_hours" in pref_data
    assert "preferred_locations" in pref_data

    # Update preferences safely
    update_res = await server.call_tool(
        "update_preferences",
        {"updates": {"freshness_hours": 16, "preferred_locations": ["Bengaluru", "Hyderabad"]}},
    )
    assert not update_res.is_error
    update_data = json.loads(update_res.content[0].text)
    assert update_data["status"] == "ok"
    assert update_data["preferences"]["freshness_hours"] == 16
    assert "Bengaluru" in update_data["preferences"]["preferred_locations"]

    # Invalidate with bad value
    bad_res = await server.call_tool(
        "update_preferences",
        {"updates": {"freshness_hours": 999}},
    )
    assert not bad_res.is_error
    bad_data = json.loads(bad_res.content[0].text)
    assert "error" in bad_data


@pytest.mark.asyncio
async def test_mcp_search_jobs():
    """Verify search_jobs tool execution returns fresh jobs structure."""
    result = await server.call_tool(
        "search_jobs",
        {"roles": ["Backend Developer", "AI Engineer"], "freshness_hours": 24},
    )
    assert not result.is_error
    data = json.loads(result.content[0].text)
    assert "fresh_jobs_found" in data
    assert data["freshness_window_hours"] == 24
    assert data["timezone"] == "Asia/Kolkata"
    assert isinstance(data["jobs"], list)


@pytest.mark.asyncio
async def test_mcp_semantic_search_jobs():
    """Verify semantic_search_jobs returns structure with query and jobs."""
    result = await server.call_tool(
        "semantic_search_jobs",
        {"query": "Python FastAPI backend engineer", "limit": 5, "freshness_hours": 24},
    )
    assert not result.is_error
    data = json.loads(result.content[0].text)
    assert data["query"] == "Python FastAPI backend engineer"
    assert "results_count" in data
    assert isinstance(data["jobs"], list)


@pytest.mark.asyncio
async def test_mcp_get_search_history():
    """Verify get_search_history tool returns past searches."""
    result = await server.call_tool("get_search_history", {"limit": 5})
    assert not result.is_error
    data = json.loads(result.content[0].text)
    assert isinstance(data, dict)
    assert "searches" in data
    assert isinstance(data["searches"], list)


@pytest.mark.asyncio
async def test_mcp_get_jobs_batch():
    """Verify get_jobs handles valid and invalid UUID strings gracefully."""
    result = await server.call_tool(
        "get_jobs",
        {"job_ids": ["00000000-0000-0000-0000-000000000000", "invalid-uuid-123"]},
    )
    assert not result.is_error
    data = json.loads(result.content[0].text)
    assert "jobs" in data
    assert "invalid_ids" in data
    assert "invalid-uuid-123" in data["invalid_ids"]


@pytest.mark.asyncio
async def test_mcp_pipeline_and_application_lifecycle():
    """Verify pipeline and application tracking tools (get_pipeline, update_application, get_application)."""
    # 1. Pipeline check
    pipe_res = await server.call_tool("get_pipeline", {})
    assert not pipe_res.is_error
    pipe_data = json.loads(pipe_res.content[0].text)
    assert "saved_jobs" in pipe_data

    # 2. Search a job to get a valid job_id for testing
    search_res = await server.call_tool("search_jobs", {"limit": 1})
    jobs = json.loads(search_res.content[0].text).get("jobs", [])
    if jobs:
        test_job_id = jobs[0]["id"]

        # Save job
        save_res = await server.call_tool("save_job", {"job_id": test_job_id, "notes": "Phase 2 test note"})
        assert not save_res.is_error
        save_data = json.loads(save_res.content[0].text)
        assert save_data["status"] == "SAVED"

        # Update application stage
        up_app_res = await server.call_tool(
            "update_application",
            {"job_id": test_job_id, "status": "VIEWED", "notes": "Viewed job details"},
        )
        assert not up_app_res.is_error
        up_app_data = json.loads(up_app_res.content[0].text)
        assert up_app_data["status"] == "VIEWED"

        # Get application details
        get_app_res = await server.call_tool("get_application", {"job_id": test_job_id})
        assert not get_app_res.is_error
        get_app_data = json.loads(get_app_res.content[0].text)
        assert get_app_data["job_id"] == test_job_id
        assert get_app_data["status"] == "VIEWED"
        assert get_app_data["notes"] == "Viewed job details"

        # Dismiss job
        dismiss_res = await server.call_tool("dismiss_job", {"job_id": test_job_id})
        assert not dismiss_res.is_error
        dismiss_data = json.loads(dismiss_res.content[0].text)
        assert dismiss_data["status"] == "IGNORED"


@pytest.mark.asyncio
async def test_mcp_sync_jobs_enqueue():
    """Verify sync_jobs enqueues a background sync task."""
    result = await server.call_tool("sync_jobs", {"source": "LINKEDIN", "freshness_hours": 24})
    assert not result.is_error
    data = json.loads(result.content[0].text)
    assert data["status"] in ("enqueued", "rate_limited")


@pytest.mark.asyncio
async def test_mcp_update_status_invalid():
    """Verify update_application rejects invalid status."""
    result = await server.call_tool(
        "update_application",
        {
            "job_id": "00000000-0000-0000-0000-000000000000",
            "status": "INVALID_STATUS_TEST",
        },
    )
    assert not result.is_error
    data = json.loads(result.content[0].text)
    assert "error" in data
