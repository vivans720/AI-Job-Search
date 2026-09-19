import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class AgentEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    event_type: str
    tool_name: Optional[str] = None
    action_summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    duration_ms: Optional[int] = None
    created_at: datetime


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    status: str
    trigger: str
    summary: Optional[str] = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    completed_at: Optional[datetime] = None


class AgentRunDetailResponse(AgentRunResponse):
    events: list[AgentEventResponse] = Field(default_factory=list)


class StartAgentRunRequest(BaseModel):
    trigger: str = "chat"
    summary: Optional[str] = None
    metrics: Optional[dict[str, Any]] = None
