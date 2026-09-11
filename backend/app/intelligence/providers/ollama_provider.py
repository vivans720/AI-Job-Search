from typing import Any
import structlog
from openai import AsyncOpenAI, BadRequestError

from app.config import settings
from app.intelligence.base import BaseAIProvider, clean_and_extract_json

logger = structlog.get_logger(__name__)


class OllamaProvider(BaseAIProvider):
    """Local Ollama provider communicating via OpenAI-compatible endpoint."""

    provider_name: str = "ollama"

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL
        self.timeout = timeout or settings.OLLAMA_TIMEOUT
        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key="ollama",
            timeout=self.timeout,
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
        except (BadRequestError, Exception) as e:
            logger.warning("ollama_json_mode_failed_attempting_fallback", error=str(e))
            text = await self.complete(
                messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            return clean_and_extract_json(text)
