import sys
from pathlib import Path
from typing import Any

# Ensure backend and mcp-server directories are on python path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
mcp_dir = root_dir / "mcp-server"

for p in [str(backend_dir), str(mcp_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from mcp.server.mcpserver import MCPServer
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer  # Fallback for mcp 1.x

from tools.profile_tools import (
    handle_get_candidate_profile,
    handle_get_preferences,
    handle_update_preferences,
)
from tools.search_tools import (
    handle_get_search_history,
    handle_search_jobs,
    handle_semantic_search_jobs,
    handle_sync_jobs,
)
from tools.job_tools import (
    handle_dismiss_job,
    handle_get_application,
    handle_get_job,
    handle_get_jobs,
    handle_get_pipeline,
    handle_get_saved_jobs,
    handle_ignore_job,
    handle_save_job,
    handle_update_application,
    handle_update_application_status,
)
from tools.match_tools import handle_match_job, handle_rank_jobs

server = MCPServer("job-agent-india")


# -------------------------------------------------------------------------
# Profile & Preferences Tools
# -------------------------------------------------------------------------

@server.tool(
    name="get_candidate_profile",
    description="Returns structured candidate intelligence extracted from the user's resume, including target roles, skills, experience level, and preferences.",
)
async def get_candidate_profile() -> dict[str, Any]:
    return await handle_get_candidate_profile()


@server.tool(
    name="get_preferences",
    description="Returns candidate job search and synchronization preferences (freshness, locations, experience level, role types, source boards).",
)
async def get_preferences() -> dict[str, Any]:
    return await handle_get_preferences()


@server.tool(
    name="update_preferences",
    description="Updates candidate search and filtering preferences safely. Validates fields and values.",
)
async def update_preferences(updates: dict[str, Any]) -> dict[str, Any]:
    return await handle_update_preferences(updates=updates)


# -------------------------------------------------------------------------
# Job Search & Ingestion Tools
# -------------------------------------------------------------------------

@server.tool(
    name="search_jobs",
    description="Search for fresh job and internship opportunities strictly within the freshness window (<=24h default). Never returns stale jobs.",
)
async def search_jobs(
    query: str | None = None,
    roles: list[str] | None = None,
    locations: list[str] | None = None,
    experience_max: int | None = None,
    freshness_hours: int = 24,
    include_remote: bool = True,
    limit: int = 20,
) -> dict[str, Any]:
    return await handle_search_jobs(
        query=query,
        roles=roles,
        locations=locations,
        experience_max=experience_max,
        freshness_hours=freshness_hours,
        include_remote=include_remote,
        limit=limit,
    )


@server.tool(
    name="semantic_search_jobs",
    description="Performs semantic vector search over fresh jobs using pgvector cosine distance based on conceptual meaning rather than exact keywords.",
)
async def semantic_search_jobs(
    query: str,
    limit: int = 10,
    freshness_hours: int = 24,
) -> dict[str, Any]:
    return await handle_semantic_search_jobs(
        query=query,
        limit=limit,
        freshness_hours=freshness_hours,
    )


@server.tool(
    name="get_job",
    description="Get full details of a specific job by ID, including original application URL, description, requirements, and match score.",
)
async def get_job(job_id: str) -> dict[str, Any]:
    return await handle_get_job(job_id=job_id)


@server.tool(
    name="get_jobs",
    description="Get details for multiple jobs at once given a list of job UUID strings.",
)
async def get_jobs(job_ids: list[str]) -> dict[str, Any]:
    return await handle_get_jobs(job_ids=job_ids)


@server.tool(
    name="sync_jobs",
    description="Triggers live aggregation and sync from job boards (LinkedIn, Naukri, Internshala, Indeed). Rate-limited and non-blocking.",
)
async def sync_jobs(
    source: str = "ALL",
    freshness_hours: int = 24,
    skills: list[str] | None = None,
) -> dict[str, Any]:
    return await handle_sync_jobs(
        source=source,
        freshness_hours=freshness_hours,
        skills=skills,
    )


# -------------------------------------------------------------------------
# Matching & Ranking Tools
# -------------------------------------------------------------------------

@server.tool(
    name="match_job",
    description="Evaluate and return match breakdown for a specific job against candidate profile (skills, semantic similarity, experience, role relevance, location).",
)
async def match_job(job_id: str) -> dict[str, Any]:
    return await handle_match_job(job_id=job_id)


@server.tool(
    name="rank_jobs",
    description="Rank a list of job IDs by relevance and match score against candidate profile. Returns ordered list with score breakdown.",
)
async def rank_jobs(job_ids: list[str]) -> dict[str, Any]:
    return await handle_rank_jobs(job_ids=job_ids)


# -------------------------------------------------------------------------
# Curation, Bookmarking & Pipeline Tools
# -------------------------------------------------------------------------

@server.tool(
    name="save_job",
    description="Save a job to candidate's saved list for manual application later.",
)
async def save_job(job_id: str, notes: str | None = None) -> dict[str, Any]:
    return await handle_save_job(job_id=job_id, notes=notes)


@server.tool(
    name="dismiss_job",
    description="Dismiss or ignore a job so it does not appear in candidate recommendations.",
)
async def dismiss_job(job_id: str, reason: str | None = None) -> dict[str, Any]:
    return await handle_dismiss_job(job_id=job_id, reason=reason)


@server.tool(
    name="ignore_job",
    description="Mark a job as ignored so it does not clutter recommendations (alias of dismiss_job).",
)
async def ignore_job(job_id: str) -> dict[str, Any]:
    return await handle_ignore_job(job_id=job_id)


@server.tool(
    name="get_pipeline",
    description="List all tracked jobs in the candidate pipeline. Optionally filter by status (SAVED, VIEWED, APPLIED, INTERVIEW, OFFER, REJECTED).",
)
async def get_pipeline(status: str | None = None) -> dict[str, Any]:
    return await handle_get_pipeline(status=status)


@server.tool(
    name="get_application",
    description="Get tracking details, status stage, and notes for a specific job application.",
)
async def get_application(job_id: str) -> dict[str, Any]:
    return await handle_get_application(job_id=job_id)


@server.tool(
    name="update_application",
    description="Update tracking stage and notes for a job application. (NOTE: Never auto-applies. Candidate applies manually).",
)
async def update_application(
    job_id: str, status: str, notes: str | None = None
) -> dict[str, Any]:
    return await handle_update_application(job_id=job_id, status=status, notes=notes)


@server.tool(
    name="update_application_status",
    description="Update manual tracking status for a job (DISCOVERED, SAVED, VIEWED, APPLIED, INTERVIEW, REJECTED, OFFER, IGNORED).",
)
async def update_application_status(
    job_id: str, status: str, notes: str | None = None
) -> dict[str, Any]:
    return await handle_update_application_status(job_id=job_id, status=status, notes=notes)


@server.tool(
    name="get_saved_jobs",
    description="List saved jobs and applications by tracking status (alias of get_pipeline).",
)
async def get_saved_jobs(status: str | None = None) -> dict[str, Any]:
    return await handle_get_saved_jobs(status=status)


@server.tool(
    name="get_search_history",
    description="Retrieve recent search queries and their discovery/freshness statistics.",
)
async def get_search_history(limit: int = 10) -> dict[str, Any]:
    return await handle_get_search_history(limit=limit)


if __name__ == "__main__":
    transport = "stdio"
    if len(sys.argv) > 1 and sys.argv[1] in ("sse", "streamable-http"):
        transport = sys.argv[1]
    server.run(transport=transport)
