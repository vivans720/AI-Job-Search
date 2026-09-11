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

from tools.profile_tools import handle_get_candidate_profile
from tools.search_tools import handle_get_search_history, handle_search_jobs
from tools.job_tools import (
    handle_get_job,
    handle_get_saved_jobs,
    handle_ignore_job,
    handle_save_job,
    handle_update_application_status,
)
from tools.match_tools import handle_match_job, handle_rank_jobs

server = MCPServer("job-agent-india")


@server.tool(
    name="get_candidate_profile",
    description="Returns structured candidate intelligence extracted from the user's resume, including target roles, skills, experience level, and preferences.",
)
async def get_candidate_profile() -> dict[str, Any]:
    return await handle_get_candidate_profile()


@server.tool(
    name="search_jobs",
    description="Search for fresh job and internship opportunities strictly within the 24-hour freshness window. Never returns stale jobs.",
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
    name="get_job",
    description="Get full details of a specific job by ID, including original application URL, description, requirements, and match score.",
)
async def get_job(job_id: str) -> dict[str, Any]:
    return await handle_get_job(job_id=job_id)


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


@server.tool(
    name="save_job",
    description="Save a job to the candidate's saved list for manual application later.",
)
async def save_job(job_id: str, notes: str | None = None) -> dict[str, Any]:
    return await handle_save_job(job_id=job_id, notes=notes)


@server.tool(
    name="ignore_job",
    description="Mark a job as ignored so it does not clutter recommendations.",
)
async def ignore_job(job_id: str) -> dict[str, Any]:
    return await handle_ignore_job(job_id=job_id)


@server.tool(
    name="update_application_status",
    description="Update manual tracking status for a job (DISCOVERED, SAVED, VIEWED, APPLIED, INTERVIEW, REJECTED, OFFER, IGNORED). NOTE: Never auto-applies.",
)
async def update_application_status(
    job_id: str, status: str, notes: str | None = None
) -> dict[str, Any]:
    return await handle_update_application_status(job_id=job_id, status=status, notes=notes)


@server.tool(
    name="get_saved_jobs",
    description="List saved jobs and applications by tracking status.",
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
