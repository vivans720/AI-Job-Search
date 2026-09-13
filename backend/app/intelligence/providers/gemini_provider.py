from typing import Any
import structlog
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import settings
from app.intelligence.langchain_adapter import LangChainAIProvider
from app.intelligence.models import ProviderCapabilities

logger = structlog.get_logger(__name__)


class GeminiProvider(LangChainAIProvider):
    """Google Gemini provider built on official LangChain ChatGoogleGenerativeAI integration."""

    provider_name: str = "gemini"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        **extra_kwargs: Any,
    ):
        target_model = model or settings.GEMINI_MODEL
        target_api_key = api_key or settings.GEMINI_API_KEY or "dummy-gemini-key"
        target_timeout = timeout or settings.GEMINI_TIMEOUT

        m = target_model.lower()
        capabilities = ProviderCapabilities(
            supports_streaming=True,
            supports_tools=True,
            supports_structured_output=True,
            supports_vision=True,
            supports_reasoning="flash-thinking" in m or "thinking" in m or "pro" in m,
            supports_model_discovery=True,
        )

        chat_model = ChatGoogleGenerativeAI(
            model=target_model,
            google_api_key=target_api_key,
            timeout=target_timeout,
            **extra_kwargs,
        )

        super().__init__(
            llm=chat_model,
            provider_name="gemini",
            model=target_model,
            capabilities=capabilities,
        )
