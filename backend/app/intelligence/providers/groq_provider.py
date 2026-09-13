from typing import Any
import structlog
from langchain_groq import ChatGroq

from app.config import settings
from app.intelligence.langchain_adapter import LangChainAIProvider
from app.intelligence.models import ProviderCapabilities

logger = structlog.get_logger(__name__)


class GroqProvider(LangChainAIProvider):
    """Groq ultra-fast LPU inference provider built on official LangChain ChatGroq."""

    provider_name: str = "groq"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        **extra_kwargs: Any,
    ):
        target_model = model or settings.GROQ_MODEL
        target_api_key = api_key or settings.GROQ_API_KEY or "gsk_dummy_groq_key"
        target_timeout = timeout or settings.GROQ_TIMEOUT

        capabilities = ProviderCapabilities(
            supports_streaming=True,
            supports_tools=True,
            supports_structured_output=True,
            supports_vision=False,
            supports_reasoning=False,
            supports_model_discovery=True,
        )

        chat_kwargs: dict[str, Any] = {
            "model_name": target_model,
            "groq_api_key": target_api_key,
            "timeout": target_timeout,
            **extra_kwargs,
        }
        if base_url:
            chat_kwargs["base_url"] = base_url.rstrip("/")

        chat_model = ChatGroq(**chat_kwargs)

        super().__init__(
            llm=chat_model,
            provider_name="groq",
            model=target_model,
            capabilities=capabilities,
        )
