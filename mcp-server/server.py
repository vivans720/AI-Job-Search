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
    handle_batch_save_jobs,
    handle_check_approval_status,
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
from tools.activity_tools import handle_notify_activity
from tools.research_tools import handle_get_job_research, handle_research_job_page
from tools.application_tools import (
    handle_generate_application_answers,
    handle_generate_cover_letter,
    handle_get_application_preparation,
    handle_prepare_application,
    handle_prepare_resume,
)
from tools.digest_tools import (
    handle_create_daily_digest,
    handle_get_daily_digests,
    handle_run_scheduled_job_search,
)
from middleware.activity_logger import log_tool_activity

server = MCPServer("job-agent-india")


# -------------------------------------------------------------------------
# Profile & Preferences Tools
# -------------------------------------------------------------------------

@server.tool(
    name="get_candidate_profile",
    description="Returns structured candidate intelligence extracted from the user's resume, including target roles, skills, experience level, and preferences.",
)
async def get_candidate_profile() -> dict[str, Any]:
    return await log_tool_activity("get_candidate_profile", {}, handle_get_candidate_profile)


@server.tool(
    name="get_preferences",
    description="Returns candidate job search and synchronization preferences (freshness, locations, experience level, role types, source boards).",
)
async def get_preferences() -> dict[str, Any]:
    return await log_tool_activity("get_preferences", {}, handle_get_preferences)


@server.tool(
    name="update_preferences",
    description="Updates candidate search and filtering preferences safely. Validates fields and values.",
)
async def update_preferences(updates: dict[str, Any]) -> dict[str, Any]:
    return await log_tool_activity("update_preferences", {"updates": updates}, lambda: handle_update_preferences(updates=updates))


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
    args = {
        "query": query,
        "roles": roles,
        "locations": locations,
        "experience_max": experience_max,
        "freshness_hours": freshness_hours,
        "include_remote": include_remote,
        "limit": limit,
    }
    return await log_tool_activity(
        "search_jobs",
        args,
        lambda: handle_search_jobs(**args),
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
    args = {"query": query, "limit": limit, "freshness_hours": freshness_hours}
    return await log_tool_activity(
        "semantic_search_jobs",
        args,
        lambda: handle_semantic_search_jobs(**args),
    )


@server.tool(
    name="get_job",
    description="Get full details of a specific job by ID, including original application URL, description, requirements, and match score.",
)
async def get_job(job_id: str) -> dict[str, Any]:
    return await log_tool_activity("get_job", {"job_id": job_id}, lambda: handle_get_job(job_id=job_id))


@server.tool(
    name="get_jobs",
    description="Get details for multiple jobs at once given a list of job UUID strings.",
)
async def get_jobs(job_ids: list[str]) -> dict[str, Any]:
    return await log_tool_activity("get_jobs", {"job_ids": job_ids}, lambda: handle_get_jobs(job_ids=job_ids))


@server.tool(
    name="sync_jobs",
    description="Triggers live aggregation and sync from job boards (LinkedIn, Naukri, Internshala). Rate-limited and non-blocking.",
)
async def sync_jobs(
    source: str = "ALL",
    freshness_hours: int = 24,
    skills: list[str] | None = None,
) -> dict[str, Any]:
    args = {"source": source, "freshness_hours": freshness_hours, "skills": skills}
    return await log_tool_activity("sync_jobs", args, lambda: handle_sync_jobs(**args))


# -------------------------------------------------------------------------
# Matching & Ranking Tools
# -------------------------------------------------------------------------

@server.tool(
    name="match_job",
    description="Evaluate and return match breakdown for a specific job against candidate profile (skills, semantic similarity, experience, role relevance, location).",
)
async def match_job(job_id: str) -> dict[str, Any]:
    return await log_tool_activity("match_job", {"job_id": job_id}, lambda: handle_match_job(job_id=job_id))


@server.tool(
    name="rank_jobs",
    description="Rank a list of job IDs by relevance and match score against candidate profile. Returns ordered list with score breakdown.",
)
async def rank_jobs(job_ids: list[str]) -> dict[str, Any]:
    return await log_tool_activity("rank_jobs", {"job_ids": job_ids}, lambda: handle_rank_jobs(job_ids=job_ids))


# -------------------------------------------------------------------------
# Curation, Bookmarking & Pipeline Tools
# -------------------------------------------------------------------------

@server.tool(
    name="save_job",
    description="Save a job to candidate's saved list. When policy requires approval, queues approval request for user review instead of mutating directly.",
)
async def save_job(
    job_id: str, notes: str | None = None, reason: str | None = None
) -> dict[str, Any]:
    args = {"job_id": job_id, "notes": notes, "reason": reason}
    return await log_tool_activity("save_job", args, lambda: handle_save_job(**args))


@server.tool(
    name="batch_save_jobs",
    description="Recommend and save a batch of relevant jobs for the candidate. Subject to autonomy approval policy.",
)
async def batch_save_jobs(
    job_ids: list[str], notes: str | None = None, reason: str | None = None
) -> dict[str, Any]:
    args = {"job_ids": job_ids, "notes": notes, "reason": reason}
    return await log_tool_activity("batch_save_jobs", args, lambda: handle_batch_save_jobs(**args))


@server.tool(
    name="dismiss_job",
    description="Dismiss or ignore a job so it does not appear in candidate recommendations. Subject to approval policy.",
)
async def dismiss_job(job_id: str, reason: str | None = None) -> dict[str, Any]:
    args = {"job_id": job_id, "reason": reason}
    return await log_tool_activity("dismiss_job", args, lambda: handle_dismiss_job(**args))


@server.tool(
    name="ignore_job",
    description="Mark a job as ignored so it does not clutter recommendations (alias of dismiss_job).",
)
async def ignore_job(job_id: str, reason: str | None = None) -> dict[str, Any]:
    args = {"job_id": job_id, "reason": reason}
    return await log_tool_activity("ignore_job", args, lambda: handle_ignore_job(**args))


@server.tool(
    name="check_approval_status",
    description="Check whether a previously queued approval request (e.g. from save_job, batch_save_jobs) was approved, rejected, or is still pending.",
)
async def check_approval_status(approval_id: str) -> dict[str, Any]:
    return await handle_check_approval_status(approval_id=approval_id)


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
    job_id: str, status: str, notes: str | None = None, reason: str | None = None
) -> dict[str, Any]:
    args = {"job_id": job_id, "status": status, "notes": notes, "reason": reason}
    return await log_tool_activity("update_application", args, lambda: handle_update_application_status(**args))


@server.tool(
    name="update_application_status",
    description="Update manual tracking status for a job (DISCOVERED, SAVED, VIEWED, PREPARING, READY_TO_APPLY, APPLIED, INTERVIEW, REJECTED, OFFER, IGNORED). Subject to approval gate.",
)
async def update_application_status(
    job_id: str, status: str, notes: str | None = None, reason: str | None = None
) -> dict[str, Any]:
    args = {"job_id": job_id, "status": status, "notes": notes, "reason": reason}
    return await log_tool_activity("update_application_status", args, lambda: handle_update_application_status(**args))


@server.tool(
    name="update_pipeline_status",
    description="Update candidate job pipeline status (DISCOVERED, SAVED, VIEWED, PREPARING, READY_TO_APPLY, APPLIED, INTERVIEW, REJECTED, OFFER, IGNORED). Transitions to APPLIED strictly require user confirmation.",
)
async def update_pipeline_status(
    job_id: str, status: str, notes: str | None = None, reason: str | None = None
) -> dict[str, Any]:
    args = {"job_id": job_id, "status": status, "notes": notes, "reason": reason}
    return await log_tool_activity("update_pipeline_status", args, lambda: handle_update_application_status(**args))


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
    return await log_tool_activity("get_search_history", {"limit": limit}, handle_get_search_history)


@server.tool(
    name="notify_activity",
    description="Broadcast a high-level, human-readable milestone message to the user activity stream (e.g. 'Planned search for Bengaluru ML roles', 'Filtered 45 jobs down to 8 matches'). NEVER output raw chain-of-thought.",
)
async def notify_activity(
    message: str,
    category: str = "milestone",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return await handle_notify_activity(message=message, category=category, metadata=metadata)


# -------------------------------------------------------------------------
# Deep Browser Research Tools (Phase 8)
# -------------------------------------------------------------------------

@server.tool(
    name="research_job_page",
    description="Deeply inspects the live job posting / careers portal URL via browser automation to extract detailed requirements, team context, application questions, and active hiring status.",
)
async def research_job_page(
    job_id: str,
    timeout_seconds: int = 25,
) -> dict[str, Any]:
    args = {"job_id": job_id, "timeout_seconds": timeout_seconds}
    return await log_tool_activity(
        "research_job_page",
        args,
        lambda: handle_research_job_page(job_id=job_id, timeout_seconds=timeout_seconds),
    )


@server.tool(
    name="get_job_research",
    description="Fetches previously recorded browser research insights and context for a job.",
)
async def get_job_research(job_id: str) -> dict[str, Any]:
    return await handle_get_job_research(job_id=job_id)


# -------------------------------------------------------------------------
# Application Preparation Tools (Phase 9)
# -------------------------------------------------------------------------

@server.tool(
    name="prepare_application",
    description="Prepares a complete application (resume selection, tailored cover letter, Q&A answers) for a job without submitting. Places application in READY_FOR_REVIEW state.",
)
async def prepare_application(
    job_id: str,
    resume_mode: str = "EXISTING",
    include_cover_letter: bool = True,
    questions: list[str] | None = None,
) -> dict[str, Any]:
    args = {
        "job_id": job_id,
        "resume_mode": resume_mode,
        "include_cover_letter": include_cover_letter,
        "questions": questions,
    }
    return await log_tool_activity(
        "prepare_application",
        args,
        lambda: handle_prepare_application(
            job_id=job_id,
            resume_mode=resume_mode,
            include_cover_letter=include_cover_letter,
            questions=questions,
        ),
    )


@server.tool(
    name="prepare_resume",
    description="Prepares candidate resume for a job: 'EXISTING' preserves active resume as-is; 'TAILORED' reframes experience with strict anti-hallucination.",
)
async def prepare_resume(job_id: str, mode: str = "EXISTING") -> dict[str, Any]:
    args = {"job_id": job_id, "mode": mode}
    return await log_tool_activity(
        "prepare_resume",
        args,
        lambda: handle_prepare_resume(job_id=job_id, mode=mode),
    )


@server.tool(
    name="generate_cover_letter",
    description="Generates an authentic, tailored cover letter based on candidate profile and deep browser research.",
)
async def generate_cover_letter(
    job_id: str,
    tone: str = "PROFESSIONAL",
    custom_notes: str | None = None,
) -> dict[str, Any]:
    args = {"job_id": job_id, "tone": tone, "custom_notes": custom_notes}
    return await log_tool_activity(
        "generate_cover_letter",
        args,
        lambda: handle_generate_cover_letter(job_id=job_id, tone=tone, custom_notes=custom_notes),
    )


@server.tool(
    name="generate_application_answers",
    description="Generates answers to screening questions grounded strictly in candidate profile facts, flagging missing information.",
)
async def generate_application_answers(
    job_id: str,
    questions: list[str],
) -> dict[str, Any]:
    args = {"job_id": job_id, "questions": questions}
    return await log_tool_activity(
        "generate_application_answers",
        args,
        lambda: handle_generate_application_answers(job_id=job_id, questions=questions),
    )


@server.tool(
    name="get_application_preparation",
    description="Retrieves the current application preparation status, tailored resume, cover letter, and answers for a job.",
)
async def get_application_preparation(job_id: str) -> dict[str, Any]:
    return await handle_get_application_preparation(job_id=job_id)


# -------------------------------------------------------------------------
# Daily Digest & Scheduled Autonomous Search Tools
# -------------------------------------------------------------------------

@server.tool(
    name="get_daily_digests",
    description="Retrieves recent daily job digests and briefings generated for the candidate.",
)
async def get_daily_digests(limit: int = 7) -> dict[str, Any]:
    return await log_tool_activity(
        "get_daily_digests",
        {"limit": limit},
        lambda: handle_get_daily_digests(limit=limit),
    )


@server.tool(
    name="create_daily_digest",
    description="Saves a formatted morning job digest into the candidate feed and tracks recommended job IDs to prevent duplicate alerts.",
)
async def create_daily_digest(
    summary: str,
    job_ids: list[str],
    status: str = "DELIVERED",
) -> dict[str, Any]:
    args = {"summary": summary, "job_ids": job_ids, "status": status}
    return await log_tool_activity(
        "create_daily_digest",
        args,
        lambda: handle_create_daily_digest(summary=summary, job_ids=job_ids, status=status),
    )


@server.tool(
    name="run_scheduled_job_search",
    description="Executes the autonomous morning job search workflow: searches fresh jobs (<24h), checks candidate profile & preferences, eliminates previously alerted duplicates, scores fit, and creates daily briefing.",
)
async def run_scheduled_job_search(
    freshness_hours: int = 24,
    match_threshold: int | None = None,
) -> dict[str, Any]:
    args = {"freshness_hours": freshness_hours, "match_threshold": match_threshold}
    return await log_tool_activity(
        "run_scheduled_job_search",
        args,
        lambda: handle_run_scheduled_job_search(
            freshness_hours=freshness_hours, match_threshold=match_threshold
        ),
    )


if __name__ == "__main__":
    transport = "stdio"
    if len(sys.argv) > 1 and sys.argv[1] in ("sse", "streamable-http"):
        transport = sys.argv[1]
    server.run(transport=transport)
