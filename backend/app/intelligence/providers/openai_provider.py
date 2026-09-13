from typing import Any
import structlog
from langchain_openai import ChatOpenAI

from app.config import settings
from app.intelligence.langchain_adapter import LangChainAIProvider
from app.intelligence.models import ProviderCapabilities

logger = structlog.get_logger(__name__)


class OpenAIProvider(LangChainAIProvider):
    """OpenAI provider built on official LangChain ChatOpenAI integration."""

    provider_name: str = "openai"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        provider_name: str = "openai",
        **extra_kwargs: Any,
    ):
        target_model = model or (settings.OPENAI_MODEL if provider_name == "openai" else settings.LLM_MODEL)
        target_base_url = (base_url or (settings.OPENAI_BASE_URL if provider_name == "openai" else settings.LLM_BASE_URL)).rstrip("/")
        target_api_key = api_key or (settings.OPENAI_API_KEY if provider_name == "openai" else settings.LLM_API_KEY) or "sk-dummy-key"
        target_timeout = timeout or settings.OPENAI_TIMEOUT
        self.base_url = target_base_url
        self.api_key = target_api_key
        self.timeout = target_timeout

        m = target_model.lower()
        is_reasoning = m.startswith("o1") or m.startswith("o3")
        capabilities = ProviderCapabilities(
            supports_streaming=True,
            supports_tools=not is_reasoning,
            supports_structured_output=True,
            supports_vision="vision" in m or "4o" in m,
            supports_reasoning=is_reasoning,
            supports_model_discovery=True,
        )

        chat_model = ChatOpenAI(
            model=target_model,
            base_url=target_base_url,
            api_key=target_api_key,
            timeout=target_timeout,
            **extra_kwargs,
        )

        super().__init__(
            llm=chat_model,
            provider_name=provider_name,
            model=target_model,
            capabilities=capabilities,
        )
