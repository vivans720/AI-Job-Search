from typing import Any
import structlog
from langchain_ollama import ChatOllama

from app.config import settings
from app.intelligence.langchain_adapter import LangChainAIProvider
from app.intelligence.models import ProviderCapabilities

logger = structlog.get_logger(__name__)


class OllamaProvider(LangChainAIProvider):
    """Local Ollama provider built on official LangChain ChatOllama."""

    provider_name: str = "ollama"

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        **extra_kwargs: Any,
    ):
        target_model = model or settings.OLLAMA_MODEL
        target_base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        # ChatOllama expects host url without /v1
        if target_base_url.endswith("/v1"):
            target_base_url = target_base_url[:-3]

        capabilities = ProviderCapabilities(
            supports_streaming=True,
            supports_tools=True,
            supports_structured_output=True,
            supports_vision=False,
            supports_reasoning=False,
            supports_model_discovery=True,
        )

        chat_model = ChatOllama(
            model=target_model,
            base_url=target_base_url,
            **extra_kwargs,
        )

        super().__init__(
            llm=chat_model,
            provider_name="ollama",
            model=target_model,
            capabilities=capabilities,
        )
