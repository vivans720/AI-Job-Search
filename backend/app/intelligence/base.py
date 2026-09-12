import json
import time
from abc import ABC, abstractmethod
from typing import Any
import structlog

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
    """Unified interface for all LLM providers (Ollama, OpenAI, Gemini, Anthropic, DeepSeek)."""

    provider_name: str = "base"
    model: str = "default"

    @abstractmethod
    async def complete(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        """Standard text completion given a chat conversation format."""
        pass

    @abstractmethod
    async def complete_json(
        self, messages: list[dict[str, str]], schema: type | dict | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        """Structured JSON completion given a chat conversation format and optional schema."""
        pass

    async def test_connection(self) -> dict[str, Any]:
        """Ping the provider to verify model availability, credentials, and measure latency."""
        t0 = time.perf_counter()
        try:
            res = await self.complete([{"role": "user", "content": "Respond with 'ok'"}], max_tokens=5)
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            return {
                "provider": self.provider_name,
                "model": self.model,
                "reachable": True,
                "latency_ms": latency_ms,
                "sample_response": res[:50],
            }
        except Exception as e:
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            return {
                "provider": self.provider_name,
                "model": self.model,
                "reachable": False,
                "latency_ms": latency_ms,
                "error": str(e),
            }
