import json
from abc import ABC, abstractmethod
from typing import Any
import structlog
from openai import AsyncOpenAI, BadRequestError

from app.config import settings

logger = structlog.get_logger(__name__)


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        """Standard text completion."""
        pass

    @abstractmethod
    async def complete_json(
        self, messages: list[dict[str, str]], schema: type | dict | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        """JSON structured completion."""
        pass


class OllamaLLM(LLMProvider):
    """LLM provider calling local Ollama (OpenAI-compatible) endpoint."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
    ):
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.model = model or settings.OLLAMA_MODEL
        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key="ollama",
            timeout=settings.OLLAMA_TIMEOUT,
        )

    async def complete(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        model = kwargs.pop("model", self.model)
        temperature = kwargs.pop("temperature", 0.2)
        max_tokens = kwargs.pop("max_tokens", settings.OLLAMA_CONTEXT_WINDOW)

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,  # type: ignore
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            content = response.choices[0].message.content or ""
            return content.strip()
        except Exception as e:
            logger.error("ollama_complete_failed", error=str(e), model=model)
            raise

    async def complete_json(
        self, messages: list[dict[str, str]], schema: type | dict | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        """Attempts response_format json_object; falls back to text extraction."""
        model = kwargs.pop("model", self.model)
        temperature = kwargs.pop("temperature", 0.1)
        max_tokens = kwargs.pop("max_tokens", settings.OLLAMA_CONTEXT_WINDOW)

        # Attempt structured JSON mode (Ollama may not support)
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,  # type: ignore
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                **kwargs,
            )
            raw = response.choices[0].message.content or "{}"
            return json.loads(raw)
        except BadRequestError as e:
            logger.warning("ollama_json_mode_unsupported_fallback", error=str(e))
            text = await self.complete(messages, model=model, temperature=temperature, max_tokens=max_tokens, **kwargs)
            return self._extract_json_from_text(text)
        except Exception as e:
            logger.warning("ollama_json_mode_failed_fallback", error=str(e))
            text = await self.complete(messages, model=model, temperature=temperature, max_tokens=max_tokens, **kwargs)
            return self._extract_json_from_text(text)

    def _extract_json_from_text(self, text: str) -> dict[str, Any]:
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
            return json.loads(cleaned[start : end + 1])
        return json.loads(cleaned)


class OmniRouteLLM(LLMProvider):
    """LLM provider calling local OmniRoute (OpenAI-compatible) endpoint."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.base_url = base_url or settings.LLM_BASE_URL
        self.api_key = api_key or settings.LLM_API_KEY
        self.model = model or settings.LLM_MODEL
        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key or "sk-dummy-key",
        )

    async def complete(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        model = kwargs.pop("model", self.model)
        temperature = kwargs.pop("temperature", 0.2)

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,  # type: ignore
                temperature=temperature,
                **kwargs,
            )
            content = response.choices[0].message.content or ""
            return content.strip()
        except Exception as e:
            logger.error("llm_complete_failed", error=str(e), model=model)
            raise

    async def complete_json(
        self, messages: list[dict[str, str]], schema: type | dict | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        """Attempts response_format json_object; falls back to text extraction."""
        model = kwargs.pop("model", self.model)
        temperature = kwargs.pop("temperature", 0.1)

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,  # type: ignore
                temperature=temperature,
                response_format={"type": "json_object"},
                **kwargs,
            )
            raw = response.choices[0].message.content or "{}"
            return json.loads(raw)
        except Exception as e:
            logger.warning("json_mode_failed_attempting_fallback", error=str(e))
            text = await self.complete(messages, model=model, temperature=temperature, **kwargs)
            return self._extract_json_from_text(text)

    def _extract_json_from_text(self, text: str) -> dict[str, Any]:
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
            return json.loads(cleaned[start : end + 1])
        return json.loads(cleaned)


_default_llm_provider: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:
    global _default_llm_provider
    if _default_llm_provider is None:
        if settings.LLM_PROVIDER == "ollama":
            _default_llm_provider = OllamaLLM()
        else:
            _default_llm_provider = OmniRouteLLM()
    return _default_llm_provider
