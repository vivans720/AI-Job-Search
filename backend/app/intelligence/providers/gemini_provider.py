from typing import Any
import structlog
from openai import AsyncOpenAI

from app.config import settings
from app.intelligence.base import BaseAIProvider, clean_and_extract_json

logger = structlog.get_logger(__name__)


class GeminiProvider(BaseAIProvider):
    """Google Gemini provider via its official OpenAI-compatible endpoint."""

    provider_name: str = "gemini"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ):
        self.base_url = (base_url or settings.GEMINI_BASE_URL).rstrip("/")
        self.api_key = api_key or settings.GEMINI_API_KEY or "dummy-gemini-key"
        self.model = model or settings.GEMINI_MODEL
        self.timeout = timeout or settings.GEMINI_TIMEOUT
        # Gemini provides OpenAI v1 compatibility at /v1beta/openai/
        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout,
        )

    async def complete(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        model = kwargs.pop("model", self.model)
        temperature = kwargs.pop("temperature", 0.2)
        max_tokens = kwargs.pop("max_tokens", 4096)

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
            logger.error("gemini_complete_failed", error=str(e), model=model)
            raise

    async def complete_json(
        self, messages: list[dict[str, str]], schema: type | dict | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        model = kwargs.pop("model", self.model)
        temperature = kwargs.pop("temperature", 0.1)
        max_tokens = kwargs.pop("max_tokens", 4096)

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
            return clean_and_extract_json(raw)
        except Exception as e:
            logger.warning("gemini_json_fallback", error=str(e))
            text = await self.complete(
                messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            return clean_and_extract_json(text)
