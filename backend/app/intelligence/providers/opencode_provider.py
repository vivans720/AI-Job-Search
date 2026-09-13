from typing import Any
from app.config import settings
from app.intelligence.models import ProviderCapabilities
from app.intelligence.providers.openai_compatible import OpenAICompatibleProvider


class OpenCodeProvider(OpenAICompatibleProvider):
    """OpenCode integration gateway (local coding agent / multi-model router)
    built on LangChain ChatOpenAI.
    """

    provider_name: str = "opencode"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        **extra_kwargs: Any,
    ):
        super().__init__(
            base_url=base_url or settings.OPENCODE_BASE_URL,
            api_key=api_key or settings.OPENCODE_API_KEY or "opencode-local",
            model=model or settings.OPENCODE_MODEL,
            timeout=timeout or settings.OPENCODE_TIMEOUT,
            provider_name="opencode",
            capabilities=ProviderCapabilities(
                supports_streaming=True,
                supports_tools=True,
                supports_structured_output=True,
                supports_vision=False,
                supports_reasoning=True,
                supports_model_discovery=True,
            ),
            **extra_kwargs,
        )
