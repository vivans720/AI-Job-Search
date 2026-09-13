from typing import Any
from app.config import settings
from app.intelligence.models import ProviderCapabilities
from app.intelligence.providers.openai_compatible import OpenAICompatibleProvider


class CerebrasProvider(OpenAICompatibleProvider):
    """Cerebras wafer-scale engine ultra-fast LLM inference provider built on LangChain ChatOpenAI."""

    provider_name: str = "cerebras"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        **extra_kwargs: Any,
    ):
        super().__init__(
            base_url=base_url or settings.CEREBRAS_BASE_URL,
            api_key=api_key or settings.CEREBRAS_API_KEY,
            model=model or settings.CEREBRAS_MODEL,
            timeout=timeout or settings.CEREBRAS_TIMEOUT,
            provider_name="cerebras",
            capabilities=ProviderCapabilities(
                supports_streaming=True,
                supports_tools=True,
                supports_structured_output=True,
                supports_vision=False,
                supports_reasoning=False,
                supports_model_discovery=True,
            ),
            **extra_kwargs,
        )
