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
    """Verify all 10 MCP tools are registered and no auto-apply tools exist."""
    tools = [t.name for t in server._tool_manager.list_tools()]
    assert len(tools) == 10
    expected_tools = [
        "get_candidate_profile",
        "search_jobs",
        "get_job",
        "match_job",
        "rank_jobs",
        "save_job",
        "ignore_job",
        "update_application_status",
        "get_saved_jobs",
        "get_search_history",
    ]
    for t in expected_tools:
        assert t in tools

    # Strict guardrails
    assert "apply_job" not in tools
    assert "submit_application" not in tools
    assert "auto_apply" not in tools


@pytest.mark.asyncio
async def test_mcp_get_candidate_profile():
    """Verify get_candidate_profile tool execution returns valid profile."""
    result = await server.call_tool("get_candidate_profile", {})
    assert not result.is_error
    data = json.loads(result.content[0].text)
    assert data["status"] == "ok"
    assert "target_roles" in data
    assert "skills" in data
    assert data["experience_level"] in ("ENTRY_LEVEL", "FRESHER")
    assert data["experience_years"] == 0


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
async def test_mcp_get_search_history():
    """Verify get_search_history tool returns past searches."""
    result = await server.call_tool("get_search_history", {"limit": 5})
    assert not result.is_error
    data = json.loads(result.content[0].text)
    assert isinstance(data, dict)
    assert "searches" in data
    assert isinstance(data["searches"], list)
    assert len(data["searches"]) >= 1
    assert "query_text" in data["searches"][0]


@pytest.mark.asyncio
async def test_mcp_get_saved_jobs():
    """Verify get_saved_jobs tool returns saved_jobs dict."""
    result = await server.call_tool("get_saved_jobs", {})
    assert not result.is_error
    data = json.loads(result.content[0].text)
    assert isinstance(data, dict)
    assert "saved_jobs" in data
    assert isinstance(data["saved_jobs"], list)


@pytest.mark.asyncio
async def test_mcp_update_status_invalid():
    """Verify update_application_status rejects invalid status."""
    result = await server.call_tool(
        "update_application_status",
        {
            "job_id": "00000000-0000-0000-0000-000000000000",
            "status": "INVALID_STATUS_TEST",
        },
    )
    assert not result.is_error
    data = json.loads(result.content[0].text)
    assert "error" in data
