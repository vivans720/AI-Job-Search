import os
import time
import uuid
from typing import Any, Callable, Optional
import structlog
from app.database import async_session_factory
from app.services.agent_activity_service import AgentActivityService
from app.services.user_service import get_or_create_default_user

logger = structlog.get_logger(__name__)

_current_run_id: Optional[str] = None


def set_current_run_id(run_id: Optional[str]) -> None:
    global _current_run_id
    _current_run_id = run_id


def get_current_run_id() -> Optional[str]:
    global _current_run_id
    if _current_run_id:
        return _current_run_id
    return os.getenv("ACTIVE_AGENT_RUN_ID")


async def ensure_active_run() -> Optional[uuid.UUID]:
    """Return active run ID or auto-create a default running session."""
    active_str = get_current_run_id()
    if active_str:
        try:
            return uuid.UUID(active_str)
        except ValueError:
            pass

    # Auto-create run for session if none provided
    try:
        async with async_session_factory() as db:
            user = await get_or_create_default_user(db)
            run = await AgentActivityService.start_run(
                db=db,
                user_id=user.id,
                trigger="mcp_session",
                summary="Autonomous Agent Job Discovery Session",
            )
            set_current_run_id(str(run.id))
            return run.id
    except Exception as e:
        logger.warning("auto_create_agent_run_failed", error=str(e))
        return None


def summarize_tool_call(tool_name: str, kwargs: dict[str, Any], result: Any) -> str:
    """Generate concise human-readable summary without chain-of-thought."""
    if tool_name == "get_candidate_profile":
        return "Read candidate profile and target preferences"
    elif tool_name == "get_preferences":
        return "Loaded job discovery search preferences"
    elif tool_name == "search_jobs":
        query = kwargs.get("query_text") or "criteria"
        location = kwargs.get("location")
        loc_str = f" in {location}" if location else ""
        cnt = result.get("total_matched") or len(result.get("jobs", [])) if isinstance(result, dict) else 0
        return f"Searched jobs for '{query}'{loc_str} (found {cnt})"
    elif tool_name == "semantic_search_jobs":
        query = kwargs.get("query_text") or "candidate profile"
        cnt = len(result.get("jobs", [])) if isinstance(result, dict) else 0
        return f"Ran semantic neural search for '{query}' (retrieved {cnt} candidates)"
    elif tool_name == "rank_jobs":
        cnt = len(result.get("ranked_jobs", [])) if isinstance(result, dict) else 0
        return f"Analyzed match scoring and shortlisted {cnt} top jobs"
    elif tool_name == "save_job":
        return f"Saved job {kwargs.get('job_id')}"
    elif tool_name == "dismiss_job" or tool_name == "ignore_job":
        return f"Dismissed irrelevant job {kwargs.get('job_id')}"
    elif tool_name == "sync_jobs":
        sources = kwargs.get("sources") or "configured sources"
        return f"Triggered real-time scraping sync across {sources}"
    elif tool_name == "notify_activity":
        return kwargs.get("message") or "Agent progress update"
    return f"Executed {tool_name}"


async def log_tool_activity(
    tool_name: str,
    kwargs: dict[str, Any],
    func: Callable[..., Any],
) -> Any:
    """Wrap tool execution with automatic AgentEvent logging."""
    start_time = time.perf_counter()
    run_id = await ensure_active_run()
    
    # Execute actual tool
    try:
        result = await func(**kwargs)
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        if run_id:
            try:
                summary = summarize_tool_call(tool_name, kwargs, result)
                # Keep payload bounded
                safe_payload = {
                    "args": {k: (v if len(str(v)) < 200 else str(v)[:200] + "...") for k, v in kwargs.items()},
                    "item_count": len(result.get("jobs", [])) if isinstance(result, dict) and "jobs" in result else None,
                }
                async with async_session_factory() as db:
                    await AgentActivityService.log_event(
                        db=db,
                        run_id=run_id,
                        event_type="tool_complete",
                        tool_name=tool_name,
                        action_summary=summary,
                        payload=safe_payload,
                        duration_ms=duration_ms,
                    )
            except Exception as log_err:
                logger.warning("mcp_tool_log_failed", tool=tool_name, error=str(log_err))

        return result
    except Exception as e:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        if run_id:
            try:
                async with async_session_factory() as db:
                    await AgentActivityService.log_event(
                        db=db,
                        run_id=run_id,
                        event_type="tool_error",
                        tool_name=tool_name,
                        action_summary=f"Failed {tool_name}: {str(e)[:150]}",
                        payload={"error": str(e)},
                        duration_ms=duration_ms,
                    )
            except Exception:
                pass
        raise
