from typing import Any
import httpx
import structlog

from app.config import settings
from app.intelligence.base import BaseAIProvider, clean_and_extract_json

logger = structlog.get_logger(__name__)


class AnthropicProvider(BaseAIProvider):
    """Anthropic Claude provider via direct Messages REST API."""

    provider_name: str = "anthropic"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ):
        self.base_url = (base_url or settings.ANTHROPIC_BASE_URL).rstrip("/")
        self.api_key = api_key or settings.ANTHROPIC_API_KEY or "dummy-anthropic-key"
        self.model = model or settings.ANTHROPIC_MODEL
        self.timeout = timeout or settings.ANTHROPIC_TIMEOUT

    async def complete(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        model = kwargs.pop("model", self.model)
        temperature = kwargs.pop("temperature", 0.2)
        max_tokens = kwargs.pop("max_tokens", 4096)

        # Anthropic separates system message from user/assistant messages
        system_content = ""
        claude_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_content += ("\n" + content if system_content else content)
            else:
                claude_messages.append({"role": role, "content": content})

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": model,
            "messages": claude_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_content:
            payload["system"] = system_content

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/messages",
                headers=headers,
                json=payload,
            )
            if resp.status_code != 200:
                logger.error("anthropic_error_response", status=resp.status_code, body=resp.text)
                resp.raise_for_status()
            data = resp.json()
            content_blocks = data.get("content", [])
            full_text = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")
            return full_text.strip()

    async def complete_json(
        self, messages: list[dict[str, str]], schema: type | dict | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        """Runs complete and extracts JSON object."""
        # Instruct Claude to output strictly JSON
        augmented_messages = list(messages)
        augmented_messages.append({
            "role": "user",
            "content": "Ensure the response is valid, parsable JSON without preamble or explanation.",
        })
        text = await self.complete(augmented_messages, **kwargs)
        return clean_and_extract_json(text)
