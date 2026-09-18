import asyncio
import time
from typing import Any, AsyncIterator
import structlog
import httpx
from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError

from app.intelligence.base import BaseAIProvider
from app.intelligence.models import (
    AIModel,
    ProviderCapabilities,
    StreamEvent,
    ToolCallResult,
    ToolDefinition,
)

logger = structlog.get_logger(__name__)


class AIGateway(BaseAIProvider):
    """Production-grade AI Gateway wrapping a primary provider with:
    - Bounded exponential backoff retries (429, 5xx, timeouts)
    - Transient-only fallback to a secondary provider
    - Structured telemetry
    - Capability negotiation
    """

    def __init__(
        self,
        primary: BaseAIProvider,
        fallback: BaseAIProvider | None = None,
        max_retries: int = 2,
        initial_backoff: float = 0.5,
    ):
        self.primary = primary
        self.fallback = fallback
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.provider_name = f"gateway({primary.provider_name})"
        self.model = primary.model

    def get_capabilities(self, model: str | None = None) -> ProviderCapabilities:
        return self.primary.get_capabilities(model)

    def _is_transient_error(self, e: Exception) -> bool:
        """Determines whether an exception is transient (retryable/eligible for fallback)."""
        if isinstance(e, (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError)):
            return True
        if isinstance(e, (httpx.TimeoutException, httpx.NetworkError)):
            return True
        err_msg = str(e).lower()
        transient_indicators = [
            "429",
            "500",
            "502",
            "503",
            "504",
            "timeout",
            "timed out",
            "connection reset",
            "connection refused",
            "rate limit",
            "overloaded",
        ]
        return any(ind in err_msg for ind in transient_indicators)

    async def _execute_with_resilience(self, method_name: str, *args: Any, **kwargs: Any) -> Any:
        t0 = time.perf_counter()
        retries = 0
        current_provider = self.primary
        fallback_used = False

        while True:
            try:
                method = getattr(current_provider, method_name)
                result = await method(*args, **kwargs)
                latency = round((time.perf_counter() - t0) * 1000, 2)

                # Record successful telemetry
                logger.info(
                    "ai_gateway_invocation",
                    provider=current_provider.provider_name,
                    model=current_provider.model,
                    method=method_name,
                    latency_ms=latency,
                    retries=retries,
                    fallback_used=fallback_used,
                    success=True,
                )
                return result

            except Exception as e:
                is_transient = self._is_transient_error(e)
                logger.warning(
                    "ai_gateway_error",
                    provider=current_provider.provider_name,
                    method=method_name,
                    error=str(e),
                    is_transient=is_transient,
                    retries=retries,
                )

                # If transient and retries remain on primary
                if is_transient and retries < self.max_retries:
                    retries += 1
                    sleep_time = self.initial_backoff * (2 ** (retries - 1))
                    await asyncio.sleep(sleep_time)
                    continue

                # If transient and fallback available and haven't switched yet
                if is_transient and self.fallback and not fallback_used:
                    logger.warning(
                        "ai_gateway_triggering_fallback",
                        from_provider=self.primary.provider_name,
                        to_provider=self.fallback.provider_name,
                        reason=str(e),
                    )
                    current_provider = self.fallback
                    fallback_used = True
                    retries = 0
                    continue

                # Non-transient error or exhausted all retries/fallback
                latency = round((time.perf_counter() - t0) * 1000, 2)
                logger.error(
                    "ai_gateway_invocation_failed",
                    provider=current_provider.provider_name,
                    method=method_name,
                    latency_ms=latency,
                    error=str(e),
                    fallback_used=fallback_used,
                )
                raise

    async def complete(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        return await self._execute_with_resilience("complete", messages, **kwargs)

    async def complete_json(
        self, messages: list[dict[str, str]], schema: type | dict | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        return await self._execute_with_resilience("complete_json", messages, schema=schema, **kwargs)

    async def stream(self, messages: list[dict[str, str]], **kwargs: Any) -> AsyncIterator[StreamEvent]:
        # Direct stream delegation to primary, fallback if initial connect fails
        try:
            async for evt in self.primary.stream(messages, **kwargs):
                yield evt
        except Exception as e:
            if self._is_transient_error(e) and self.fallback:
                logger.warning("stream_fallback_triggered", error=str(e))
                async for evt in self.fallback.stream(messages, **kwargs):
                    yield evt
            else:
                raise

    async def complete_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[ToolDefinition | dict[str, Any]],
        **kwargs: Any,
    ) -> ToolCallResult:
        return await self._execute_with_resilience("complete_with_tools", messages, tools, **kwargs)

    async def list_models(self) -> list[AIModel]:
        return await self.primary.list_models()

    async def test_connection(self) -> dict[str, Any]:
        primary_res = await self.primary.test_connection()
        if self.fallback:
            fallback_res = await self.fallback.test_connection()
            primary_res["fallback_status"] = fallback_res
        return primary_res
