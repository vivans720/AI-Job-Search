import uuid
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field


class AutonomyPolicyUpdateRequest(BaseModel):
    autonomy_policy: dict[str, str] = Field(
        ...,
        description="Policy mapping for actions: 'autonomous' or 'approval_required'",
        example={
            "search": "autonomous",
            "analyze": "autonomous",
            "save_job": "approval_required",
            "dismiss_job": "approval_required",
            "update_pipeline_status": "approval_required",
        },
    )


class AutonomyPolicyResponse(BaseModel):
    autonomy_policy: dict[str, str]


class AgentApprovalResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    run_id: uuid.UUID | None
    action_type: str
    status: str
    job_id: uuid.UUID | None
    payload: dict[str, Any]
    reason: str | None
    created_at: datetime
    expires_at: datetime | None
    resolved_at: datetime | None
    resolution_notes: str | None
    job_summary: dict[str, Any] | None = None

    model_config = {"from_attributes": True}


class ResolveApprovalRequest(BaseModel):
    decision: str = Field(..., description="'APPROVE' or 'REJECT'")
    partial_job_ids: list[str] | None = Field(
        default=None,
        description="Optional list of job IDs to approve for batch actions (leaves remainder untouched/rejected)",
    )
    resolution_notes: str | None = None


class ResolveApprovalResponse(BaseModel):
    approval_id: uuid.UUID
    status: str
    decision: str
    executed_count: int
    executed_job_ids: list[str]
    notes: str | None = None
