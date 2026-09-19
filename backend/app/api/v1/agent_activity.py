import asyncio
import json
import uuid
from typing import AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.database import get_db
from app.models.user import User
from app.schemas.agent_activity import (
    AgentEventResponse,
    AgentRunDetailResponse,
    AgentRunResponse,
    StartAgentRunRequest,
)
from app.schemas.agent_approval import (
    AgentApprovalResponse,
    AutonomyPolicyResponse,
    AutonomyPolicyUpdateRequest,
    ResolveApprovalRequest,
    ResolveApprovalResponse,
)
from app.services.agent_activity_service import AgentActivityService
from app.services.agent_approval_service import AgentApprovalService
from app.services.user_service import get_or_create_default_user

router = APIRouter(prefix="/agent", tags=["agent-activity"])


@router.get("/runs", response_model=list[AgentRunResponse])
async def list_agent_runs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve history of agent execution runs."""
    user = await get_or_create_default_user(db)
    return await AgentActivityService.list_runs(
        db=db, user_id=user.id, limit=limit, offset=offset
    )


@router.post("/runs", response_model=AgentRunResponse, status_code=status.HTTP_201_CREATED)
async def start_agent_run(
    request: StartAgentRunRequest,
    db: AsyncSession = Depends(get_db),
):
    """Start an active agent execution run session."""
    user = await get_or_create_default_user(db)
    return await AgentActivityService.start_run(
        db=db,
        user_id=user.id,
        trigger=request.trigger,
        summary=request.summary,
        metrics=request.metrics,
    )


@router.get("/runs/{run_id}", response_model=AgentRunDetailResponse)
async def get_agent_run_detail(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve details of a specific agent run and its events."""
    user = await get_or_create_default_user(db)
    run = await AgentActivityService.get_run(db, run_id)
    if not run or run.user_id != user.id:
        raise HTTPException(status_code=404, detail="Agent run not found")

    events = await AgentActivityService.get_run_events(db, run_id)
    return AgentRunDetailResponse(
        id=run.id,
        user_id=run.user_id,
        status=run.status,
        trigger=run.trigger,
        summary=run.summary,
        metrics=run.metrics,
        created_at=run.created_at,
        completed_at=run.completed_at,
        events=[AgentEventResponse.model_validate(e) for e in events],
    )


@router.post("/runs/{run_id}/cancel", response_model=AgentRunResponse)
async def cancel_agent_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Cancel an active agent execution run."""
    user = await get_or_create_default_user(db)
    run = await AgentActivityService.get_run(db, run_id)
    if not run or run.user_id != user.id:
        raise HTTPException(status_code=404, detail="Agent run not found")

    if run.status in ("completed", "failed", "cancelled"):
        return run

    run.status = "cancelled"
    await db.commit()
    await db.refresh(run)

    await AgentActivityService._publish_event(
        run_id=str(run.id),
        event_type="status_update",
        data={"run_id": str(run.id), "status": run.status, "summary": "Run cancelled by user"},
    )
    return run


@router.get("/runs/{run_id}/stream")
async def stream_agent_events(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Server-Sent Events (SSE) stream for live agent activity."""
    user = await get_or_create_default_user(db)
    run = await AgentActivityService.get_run(db, run_id)
    if not run or run.user_id != user.id:
        raise HTTPException(status_code=404, detail="Agent run not found")

    async def event_generator() -> AsyncGenerator[str, None]:
        # First send past events for this run
        existing_events = await AgentActivityService.get_run_events(db, run_id)
        for ev in existing_events:
            ev_data = {
                "id": str(ev.id),
                "run_id": str(ev.run_id),
                "event_type": ev.event_type,
                "tool_name": ev.tool_name,
                "action_summary": ev.action_summary,
                "payload": ev.payload,
                "duration_ms": ev.duration_ms,
                "created_at": ev.created_at.isoformat(),
            }
            yield f"event: {ev.event_type}\ndata: {json.dumps(ev_data)}\n\n"

        # If run is already finished, complete stream
        if run.status in ("completed", "failed", "cancelled"):
            yield f"event: status_update\ndata: {json.dumps({'run_id': str(run.id), 'status': run.status, 'summary': run.summary})}\n\n"
            return

        # Subscribe to live Redis channel
        redis = await get_redis()
        if not redis:
            yield f"event: error\ndata: {json.dumps({'message': 'Redis unavailable for live stream'})}\n\n"
            return

        pubsub = redis.pubsub()
        channel = f"agent:run:{run_id}"
        await pubsub.subscribe(channel)

        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "message":
                    payload = json.loads(message["data"])
                    ev_type = payload.get("event_type", "message")
                    ev_data = payload.get("data", {})
                    yield f"event: {ev_type}\ndata: {json.dumps(ev_data)}\n\n"

                    # If run completed or failed, close the SSE connection
                    if ev_type == "status_update" and ev_data.get("status") in ("completed", "failed", "cancelled"):
                        break

                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# -------------------------------------------------------------------------
# Phase 7 — Agent Approvals & Autonomy Policy Endpoints
# -------------------------------------------------------------------------

@router.get("/approvals", response_model=list[AgentApprovalResponse])
async def list_agent_approvals(
    status: str | None = Query(None, description="Optional status filter: PENDING, APPROVED, REJECTED, EXPIRED"),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List agent approval requests for candidate review."""
    user = await get_or_create_default_user(db)
    return await AgentApprovalService.list_approvals(
        db=db, user_id=user.id, status=status, limit=limit
    )


@router.post("/approvals/{approval_id}/resolve", response_model=ResolveApprovalResponse)
async def resolve_agent_approval(
    approval_id: uuid.UUID,
    request: ResolveApprovalRequest,
    db: AsyncSession = Depends(get_db),
):
    """Approve or reject a pending agent action."""
    user = await get_or_create_default_user(db)
    try:
        res = await AgentApprovalService.resolve_approval(
            db=db,
            user_id=user.id,
            approval_id=approval_id,
            decision=request.decision,
            partial_job_ids=request.partial_job_ids,
            resolution_notes=request.resolution_notes,
        )
        return ResolveApprovalResponse(**res)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/autonomy-policy", response_model=AutonomyPolicyResponse)
async def get_autonomy_policy(
    db: AsyncSession = Depends(get_db),
):
    """Get candidate configurable agent autonomy policy."""
    user = await get_or_create_default_user(db)
    policy = await AgentApprovalService.get_autonomy_policy(db, user.id)
    return AutonomyPolicyResponse(autonomy_policy=policy)


@router.put("/autonomy-policy", response_model=AutonomyPolicyResponse)
async def update_autonomy_policy(
    request: AutonomyPolicyUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update candidate configurable agent autonomy policy."""
    user = await get_or_create_default_user(db)
    updated = await AgentApprovalService.update_autonomy_policy(
        db=db, user_id=user.id, policy_updates=request.autonomy_policy
    )
    return AutonomyPolicyResponse(autonomy_policy=updated)

