from typing import Any
import structlog
from langchain_anthropic import ChatAnthropic

from app.config import settings
from app.intelligence.langchain_adapter import LangChainAIProvider
from app.intelligence.models import ProviderCapabilities

logger = structlog.get_logger(__name__)


class AnthropicProvider(LangChainAIProvider):
    """Anthropic Claude provider built on official LangChain ChatAnthropic integration."""

    provider_name: str = "anthropic"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        **extra_kwargs: Any,
    ):
        target_model = model or settings.ANTHROPIC_MODEL
        target_api_key = api_key or settings.ANTHROPIC_API_KEY or "dummy-anthropic-key"
        target_timeout = timeout or settings.ANTHROPIC_TIMEOUT
        target_base_url = base_url or settings.ANTHROPIC_BASE_URL

        m = target_model.lower()
        capabilities = ProviderCapabilities(
            supports_streaming=True,
            supports_tools=True,
            supports_structured_output=True,
            supports_vision="sonnet" in m or "3-5" in m or "opus" in m,
            supports_reasoning="3-7" in m or "thinking" in m,
            supports_model_discovery=False,
        )

        chat_kwargs: dict[str, Any] = {
            "model_name": target_model,
            "api_key": target_api_key,
            "timeout": target_timeout,
            **extra_kwargs,
        }
        if target_base_url and "api.anthropic.com" not in target_base_url:
            chat_kwargs["base_url"] = target_base_url.rstrip("/")

        chat_model = ChatAnthropic(**chat_kwargs)

        super().__init__(
            llm=chat_model,
            provider_name="anthropic",
            model=target_model,
            capabilities=capabilities,
        )
