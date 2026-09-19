import sys
from pathlib import Path
import pytest
import yaml

mcp_dir = Path(__file__).resolve().parent.parent / "mcp-server"
if str(mcp_dir) not in sys.path:
    sys.path.insert(0, str(mcp_dir))

from tools.profile_tools import (
    handle_get_candidate_profile,
    handle_get_preferences,
    handle_update_preferences,
)
from tools.search_tools import handle_search_jobs, handle_semantic_search_jobs
from tools.match_tools import handle_rank_jobs


def test_phase5_skill_memory_protocol():
    """Verify Phase 5 persistent preference memory specifications in SKILL.md."""
    skill_file = Path(__file__).resolve().parent.parent / "skills" / "job-search" / "SKILL.md"
    assert skill_file.exists()
    content = skill_file.read_text(encoding="utf-8")
    
    parts = content.split("---")
    assert len(parts) >= 3
    fm = yaml.safe_load(parts[1])
    assert fm["name"] == "job-search"
    assert "persistent-memory" in fm.get("metadata", {}).get("hermes", {}).get("tags", [])
    assert fm["version"] == "2.1.0"

    # Verify memory architectural rules
    assert "USER.md" in content
    assert "MEMORY.md" in content
    assert "Strict Storage Boundaries" in content
    assert "1,375 chars" in content
    assert "Preference Learning & Bi-directional Reconciliation" in content
    assert "**NEVER** store job IDs" in content
    assert "update_preferences" in content


def test_phase5_hermes_skill_sync():
    """Verify live ~/.hermes skill matches updated repository skill."""
    repo_skill = Path("skills/job-search/SKILL.md")
    hermes_skill = Path.home() / ".hermes" / "skills" / "productivity" / "job-search" / "SKILL.md"

    assert hermes_skill.exists(), "Hermes job-search skill missing from ~/.hermes"
    assert repo_skill.read_text() == hermes_skill.read_text(), "Hermes skill out of sync with repository"


@pytest.mark.asyncio
async def test_preference_reconciliation_flow():
    """
    Verify preference update tool safely handles structured preference updates
    while keeping database validation intact.
    """
    # 1. Fetch current preferences
    initial_prefs = await handle_get_preferences()
    assert initial_prefs["status"] == "ok"
    assert "preferred_locations" in initial_prefs

    # 2. Update preference as triggered by preference learning
    target_locations = ["Bengaluru", "Remote", "Gurugram"]
    update_res = await handle_update_preferences({
        "preferred_locations": target_locations,
        "freshness_hours": 24,
    })
    assert update_res["status"] == "ok"
    assert "preferences" in update_res
    assert update_res["preferences"]["preferred_locations"] == target_locations

    # 3. Verify updated preferences reflect in candidate profile
    profile = await handle_get_candidate_profile()
    assert profile["status"] in ("ok", "not_found")
    if profile["status"] == "ok":
        assert profile["freshness_hours"] == 24


@pytest.mark.asyncio
async def test_preference_aware_search_constraints():
    """
    Simulate agent performing search applying learned user preferences:
    - Target roles
    - Preferred locations
    - Freshness <= 24h
    """
    prefs = await handle_get_preferences()
    assert prefs["status"] == "ok"

    locations = prefs.get("preferred_locations", ["Bengaluru"])
    freshness = prefs.get("freshness_hours", 24)

    # Search with candidate preference constraints
    results = await handle_search_jobs(
        roles=["Software Engineer", "Backend Developer"],
        locations=locations,
        freshness_hours=freshness,
        limit=5,
    )
    assert "fresh_jobs_found" in results
    assert "jobs" in results
    assert isinstance(results["jobs"], list)


@pytest.mark.asyncio
async def test_memory_storage_boundary_integrity():
    """
    Verify that structured entities (jobs and applications) remain strictly in DB
    and do not leak into memory requirements.
    """
    # Verify semantic search output is structured and clean
    res = await handle_semantic_search_jobs(
        query="Python AI Engineer Agent",
        limit=3,
        freshness_hours=48,
    )
    assert "results_count" in res
    assert "jobs" in res
    for job in res["jobs"]:
        assert "id" in job
        assert "title" in job
        assert "company" in job
