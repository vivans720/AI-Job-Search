from typing import Any
import structlog
from langchain_mistralai import ChatMistralAI

from app.config import settings
from app.intelligence.langchain_adapter import LangChainAIProvider
from app.intelligence.models import ProviderCapabilities

logger = structlog.get_logger(__name__)


class MistralProvider(LangChainAIProvider):
    """Mistral AI provider built on official LangChain ChatMistralAI."""

    provider_name: str = "mistral"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        **extra_kwargs: Any,
    ):
        target_model = model or settings.MISTRAL_MODEL
        target_api_key = api_key or settings.MISTRAL_API_KEY or "dummy-mistral-key"
        target_timeout = timeout or settings.MISTRAL_TIMEOUT

        capabilities = ProviderCapabilities(
            supports_streaming=True,
            supports_tools=True,
            supports_structured_output=True,
            supports_vision=True,
            supports_reasoning=False,
            supports_model_discovery=True,
        )

        chat_kwargs: dict[str, Any] = {
            "model_name": target_model,
            "api_key": target_api_key,
            "timeout": target_timeout,
            **extra_kwargs,
        }
        if base_url:
            chat_kwargs["endpoint"] = base_url.rstrip("/")

        chat_model = ChatMistralAI(**chat_kwargs)

        super().__init__(
            llm=chat_model,
            provider_name="mistral",
            model=target_model,
            capabilities=capabilities,
        )
