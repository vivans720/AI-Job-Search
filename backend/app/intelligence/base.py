import json
import time
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator
import structlog

from app.intelligence.models import (
    AIModel,
    ProviderCapabilities,
    StreamEvent,
    TextDelta,
    StreamCompleted,
    ToolCallResult,
    ToolDefinition,
)

logger = structlog.get_logger(__name__)


def clean_and_extract_json(text: str) -> dict[str, Any]:
    """Helper to reliably extract a JSON object from text with markdown fences or surrounding noise."""
    if not text or not isinstance(text, str):
        return {}
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = cleaned[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    try:
        return json.loads(cleaned)
    except Exception as e:
        logger.warning("json_extraction_failed", preview=text[:100], error=str(e))
        return {}


class BaseAIProvider(ABC):
    """Unified interface for all LLM providers with multi-provider gateway support."""

    provider_name: str = "base"
    model: str = "default"

    @abstractmethod
    async def complete(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        """Standard text completion given a chat conversation format."""
        pass

    async def generate_response(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        """Alias for complete() to maintain backward compatibility."""
        return await self.complete(messages, **kwargs)

    @abstractmethod
    async def complete_json(
        self, messages: list[dict[str, str]], schema: type | dict | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        """Structured JSON completion given a chat conversation format and optional schema."""
        pass

    async def stream(self, messages: list[dict[str, str]], **kwargs: Any) -> AsyncIterator[StreamEvent]:
        """Streaming completion returning standardized StreamEvents. Default fallback yields complete text."""
        full_text = await self.complete(messages, **kwargs)
        yield TextDelta(text=full_text)
        yield StreamCompleted(finish_reason="stop")

    async def complete_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[ToolDefinition | dict[str, Any]],
        **kwargs: Any,
    ) -> ToolCallResult:
        """Tool calling abstraction. Default fallback returns text only."""
        text = await self.complete(messages, **kwargs)
        return ToolCallResult(content=text, tool_calls=[])

    async def list_models(self) -> list[AIModel]:
        """List models available for this provider instance."""
        return [
            AIModel(
                provider=self.provider_name,
                model_id=self.model,
                display_name=self.model,
                supports_tools=self.get_capabilities().supports_tools,
                supports_streaming=self.get_capabilities().supports_streaming,
                supports_structured_output=self.get_capabilities().supports_structured_output,
                supports_vision=self.get_capabilities().supports_vision,
                supports_reasoning=self.get_capabilities().supports_reasoning,
            )
        ]

    def get_capabilities(self, model: str | None = None) -> ProviderCapabilities:
        """Inspect capabilities supported by this provider/model."""
        return ProviderCapabilities(
            supports_streaming=True,
            supports_tools=False,
            supports_structured_output=True,
            supports_vision=False,
            supports_reasoning=False,
            supports_model_discovery=False,
        )

    async def test_connection(self) -> dict[str, Any]:
        """Ping the provider to verify model availability, credentials, and measure latency."""
        t0 = time.perf_counter()
        try:
            res = await self.complete([{"role": "user", "content": "Respond with 'ok'"}], max_tokens=5)
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            caps = self.get_capabilities()
            return {
                "provider": self.provider_name,
                "model": self.model,
                "reachable": True,
                "latency_ms": latency_ms,
                "sample_response": res[:50],
                "capabilities": caps.model_dump(),
            }
        except Exception as e:
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            return {
                "provider": self.provider_name,
                "model": self.model,
                "reachable": False,
                "latency_ms": latency_ms,
                "error": str(e),
                "capabilities": self.get_capabilities().model_dump(),
            }
