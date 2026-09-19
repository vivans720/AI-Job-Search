import sys
import uuid
from pathlib import Path
import pytest
import yaml

# Put paths
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
mcp_dir = root_dir / "mcp-server"

for p in [str(backend_dir), str(mcp_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from app.database import async_session_factory
from app.models.agent_activity import AgentRun, AgentEvent
from app.services.agent_activity_service import AgentActivityService
from app.services.user_service import get_or_create_default_user
from tools.activity_tools import handle_notify_activity


def test_phase6_skill_observability_specification():
    """Verify Phase 6 skill specification, version bump, and rules."""
    skill_file = root_dir / "skills" / "job-search" / "SKILL.md"
    assert skill_file.exists()
    content = skill_file.read_text(encoding="utf-8")

    parts = content.split("---")
    assert len(parts) >= 3
    fm = yaml.safe_load(parts[1])
    assert fm["name"] == "job-search"
    assert fm["version"] == "2.2.0"
    assert "observability" in fm.get("metadata", {}).get("hermes", {}).get("tags", [])

    # Observability guardrails
    assert "Observability & Transparency" in content
    assert "notify_activity" in content
    assert "NEVER leak internal raw chain-of-thought" in content


@pytest.mark.asyncio
async def test_agent_activity_service_lifecycle():
    """Test creating run, logging events, and completing run."""
    async with async_session_factory() as db:
        user = await get_or_create_default_user(db)
        
        # 1. Start Run
        run = await AgentActivityService.start_run(
            db=db,
            user_id=user.id,
            trigger="test_run",
            summary="Testing Agent Activity Stream",
        )
        assert run.id is not None
        assert run.status == "running"
        assert run.user_id == user.id

        # 2. Log Tool & Milestone Events
        event1 = await AgentActivityService.log_event(
            db=db,
            run_id=run.id,
            action_summary="Planned search for Bangalore tech jobs",
            event_type="milestone",
            tool_name="notify_activity",
        )
        assert event1.id is not None
        assert event1.run_id == run.id

        event2 = await AgentActivityService.log_event(
            db=db,
            run_id=run.id,
            action_summary="Searched jobs for 'Full Stack'",
            event_type="tool_complete",
            tool_name="search_jobs",
            payload={"item_count": 12},
            duration_ms=145,
        )
        assert event2.duration_ms == 145

        # 3. Retrieve events
        events = await AgentActivityService.get_run_events(db, run.id)
        assert len(events) >= 2
        summaries = [e.action_summary for e in events]
        assert "Planned search for Bangalore tech jobs" in summaries

        # 4. Complete Run
        completed_run = await AgentActivityService.complete_run(
            db=db,
            run_id=run.id,
            summary="Shortlisted 5 opportunities",
            metrics={"shortlisted": 5},
        )
        assert completed_run is not None
        assert completed_run.status == "completed"
        assert completed_run.metrics["shortlisted"] == 5
        assert completed_run.completed_at is not None


@pytest.mark.asyncio
async def test_notify_activity_mcp_tool():
    """Test MCP tool notify_activity execution."""
    res = await handle_notify_activity(
        message="Analyzing 15 candidate matches",
        category="analyzing",
        metadata={"total_analyzed": 15},
    )
    assert res["status"] == "ok"
    assert res["recorded"] is True
    assert "Analyzing 15 candidate matches" in res["action_summary"]
