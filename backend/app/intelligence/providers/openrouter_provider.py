from typing import Any
from app.config import settings
from app.intelligence.models import ProviderCapabilities
from app.intelligence.providers.openai_compatible import OpenAICompatibleProvider


class OpenRouterProvider(OpenAICompatibleProvider):
    """OpenRouter multi-model aggregation gateway built on LangChain ChatOpenAI
    with routing headers and model identification.
    """

    provider_name: str = "openrouter"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        **extra_kwargs: Any,
    ):
        super().__init__(
            base_url=base_url or settings.OPENROUTER_BASE_URL,
            api_key=api_key or settings.OPENROUTER_API_KEY,
            model=model or settings.OPENROUTER_MODEL,
            timeout=timeout or settings.OPENROUTER_TIMEOUT,
            provider_name="openrouter",
            default_headers={
                "HTTP-Referer": "https://ai-job-agent.local",
                "X-Title": "AI Job Agent India",
            },
            capabilities=ProviderCapabilities(
                supports_streaming=True,
                supports_tools=True,
                supports_structured_output=True,
                supports_vision=True,
                supports_reasoning=True,
                supports_model_discovery=True,
            ),
            **extra_kwargs,
        )
