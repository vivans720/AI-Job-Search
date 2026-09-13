from typing import Any
from app.config import settings
from app.intelligence.models import ProviderCapabilities
from app.intelligence.providers.openai_compatible import OpenAICompatibleProvider


class NVIDIAProvider(OpenAICompatibleProvider):
    """NVIDIA NIM provider (supports hosted API and self-hosted on-prem NIM containers)
    built on LangChain ChatOpenAI.
    """

    provider_name: str = "nvidia-nim"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        **extra_kwargs: Any,
    ):
        super().__init__(
            base_url=base_url or settings.NVIDIA_NIM_BASE_URL,
            api_key=api_key or settings.NVIDIA_NIM_API_KEY,
            model=model or settings.NVIDIA_NIM_MODEL,
            timeout=timeout or settings.NVIDIA_NIM_TIMEOUT,
            provider_name="nvidia-nim",
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
