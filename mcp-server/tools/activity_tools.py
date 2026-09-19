import sys
import uuid
from pathlib import Path
from typing import Any, Optional

backend_dir = Path(__file__).resolve().parent.parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database import async_session_factory
from app.services.agent_activity_service import AgentActivityService
from middleware.activity_logger import ensure_active_run


async def handle_notify_activity(
    message: str,
    category: str = "milestone",
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Log explicit agent milestone activity event for frontend visibility.
    Categories: planning, analyzing, filtering, shortlisting, milestone.
    """
    run_id = await ensure_active_run()
    if not run_id:
        return {"status": "ok", "recorded": False, "reason": "No active run"}

    async with async_session_factory() as db:
        event = await AgentActivityService.log_event(
            db=db,
            run_id=run_id,
            event_type="milestone",
            tool_name="notify_activity",
            action_summary=message,
            payload={"category": category, **(metadata or {})},
        )
        return {
            "status": "ok",
            "recorded": True,
            "event_id": str(event.id),
            "action_summary": message,
        }
