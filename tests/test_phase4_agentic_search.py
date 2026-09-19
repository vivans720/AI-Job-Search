import sys
from pathlib import Path
import pytest
import yaml

mcp_dir = Path(__file__).resolve().parent.parent / "mcp-server"
if str(mcp_dir) not in sys.path:
    sys.path.insert(0, str(mcp_dir))

from tools.profile_tools import handle_get_candidate_profile
from tools.search_tools import handle_search_jobs, handle_semantic_search_jobs
from tools.match_tools import handle_rank_jobs, handle_match_job


def test_agentic_search_skill_documentation():
    skill_file = Path(__file__).resolve().parent.parent / "skills" / "job-search" / "SKILL.md"
    assert skill_file.exists()
    content = skill_file.read_text(encoding="utf-8")
    parts = content.split("---")
    assert len(parts) >= 3
    fm = yaml.safe_load(parts[1])
    assert fm["name"] == "job-search"
    assert "agentic-search" in fm.get("metadata", {}).get("hermes", {}).get("tags", [])

    # Check key agentic rules present in skill
    assert "Agentic Search Decision Framework" in content
    assert "Structured Search" in content
    assert "Semantic Search" in content
    assert "Iterative Refinement" in content
    assert "Maximum 3 search iterations" in content
    assert "Sufficiency Condition" in content


@pytest.mark.asyncio
async def test_simulated_structured_search_flow():
    """Verify structured search query handles parameters cleanly."""
    profile = await handle_get_candidate_profile()
    assert isinstance(profile, dict)

    target_roles = profile.get("target_roles", ["Software Engineer"])
    res = await handle_search_jobs(
        roles=target_roles[:2],
        freshness_hours=48,
        limit=5,
    )
    assert isinstance(res, dict)
    assert "fresh_jobs_found" in res
    assert "jobs" in res
    assert isinstance(res["jobs"], list)


@pytest.mark.asyncio
async def test_simulated_semantic_search_flow():
    """Verify semantic search queries pgvector cleanly and returns result count."""
    res = await handle_semantic_search_jobs(
        query="Full stack developer react python fastapi",
        limit=5,
        freshness_hours=48,
    )
    assert isinstance(res, dict)
    assert "results_count" in res
    assert "jobs" in res
    assert isinstance(res["jobs"], list)


@pytest.mark.asyncio
async def test_simulated_agentic_refinement_and_ranking():
    """
    Simulates Hermes decision loop:
    1. First search
    2. Check yield
    3. If jobs returned, rank them
    4. Verify deterministic ranking output format
    """
    # 1. Search
    res = await handle_search_jobs(
        query="developer",
        freshness_hours=72,
        limit=5,
    )
    jobs = res.get("jobs", [])

    if jobs:
        job_ids = [j["id"] for j in jobs if "id" in j]
        ranked = await handle_rank_jobs(job_ids=job_ids)
        assert "ranked_jobs" in ranked
        assert isinstance(ranked["ranked_jobs"], list)
        if ranked["ranked_jobs"]:
            top = ranked["ranked_jobs"][0]
            assert "score" in top
            assert "recommendation" in top
            assert "application_url" in top
    else:
        # Fallback query if no jobs match
        res_semantic = await handle_semantic_search_jobs(
            query="software",
            limit=3,
            freshness_hours=72,
        )
        assert "results_count" in res_semantic


def test_installed_hermes_skill_sync():
    """Verify installed ~/.hermes skill matches project skill."""
    proj_skill = Path("skills/job-search/SKILL.md")
    home_skill = Path.home() / ".hermes" / "skills" / "productivity" / "job-search" / "SKILL.md"

    assert home_skill.exists(), "Hermes job-search skill not synced to home directory"
    assert proj_skill.read_text() == home_skill.read_text(), "Home skill content differs from repo skill"
