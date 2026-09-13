from typing import Any, AsyncIterator
from pydantic import BaseModel, Field


class AIModel(BaseModel):
    """Normalized model descriptor."""

    provider: str
    model_id: str
    display_name: str
    context_window: int | None = None
    max_output_tokens: int | None = None

    supports_tools: bool = False
    supports_streaming: bool = True
    supports_structured_output: bool = True
    supports_vision: bool = False
    supports_reasoning: bool = False


class ProviderCapabilities(BaseModel):
    supports_streaming: bool = True
    supports_tools: bool = False
    supports_structured_output: bool = True
    supports_vision: bool = False
    supports_reasoning: bool = False
    supports_model_discovery: bool = False


class ProviderMetadata(BaseModel):
    id: str
    name: str
    type: str  # "local" | "cloud"
    default_model: str
    configured: bool = False
    description: str = ""
    capabilities: ProviderCapabilities = Field(default_factory=ProviderCapabilities)
    base_url: str | None = None
    requires_api_key: bool = True
    models: list[AIModel] = Field(default_factory=list)


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]


class ToolCallResult(BaseModel):
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    finish_reason: str | None = None
    usage: dict[str, int] | None = None


# Streaming Event Model
class TextDelta(BaseModel):
    type: str = "text"
    text: str


class ToolCallDelta(BaseModel):
    type: str = "tool_call"
    index: int
    id: str | None = None
    name: str | None = None
    arguments: str | None = None


class UsageEvent(BaseModel):
    type: str = "usage"
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class StreamCompleted(BaseModel):
    type: str = "completed"
    finish_reason: str = "stop"


class StreamError(BaseModel):
    type: str = "error"
    error: str
    code: str | None = None


StreamEvent = TextDelta | ToolCallDelta | UsageEvent | StreamCompleted | StreamError


class AITelemetry(BaseModel):
    provider: str
    model: str
    latency_ms: float = 0.0
    time_to_first_token_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    success: bool = True
    error_type: str | None = None
    retry_count: int = 0
    fallback_used: bool = False
    fallback_provider: str | None = None
    estimated_cost: float | None = None


class ProviderHealth(BaseModel):
    provider: str
    model: str
    reachable: bool
    latency_ms: float = 0.0
    error: str | None = None
    sample_response: str | None = None
    capabilities: ProviderCapabilities = Field(default_factory=ProviderCapabilities)
