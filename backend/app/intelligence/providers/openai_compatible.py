from typing import Any
import structlog
from langchain_openai import ChatOpenAI

from app.intelligence.langchain_adapter import LangChainAIProvider
from app.intelligence.models import ProviderCapabilities

logger = structlog.get_logger(__name__)


class OpenAICompatibleProvider(LangChainAIProvider):
    """Reusable OpenAI-compatible provider adapter built on LangChain ChatOpenAI.
    Serves as the foundation for generic endpoints, Groq, OpenRouter, Cerebras,
    Mistral, NVIDIA NIM, and OpenCode.
    """

    provider_name: str = "openai_compatible"

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        model: str = "default",
        timeout: float = 45.0,
        provider_name: str = "openai_compatible",
        default_headers: dict[str, str] | None = None,
        capabilities: ProviderCapabilities | None = None,
        **extra_kwargs: Any,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or "dummy-key"
        self.timeout = timeout
        self.default_headers = default_headers or {}

        caps = capabilities or ProviderCapabilities(
            supports_streaming=True,
            supports_tools=True,
            supports_structured_output=True,
            supports_vision=False,
            supports_reasoning=False,
            supports_model_discovery=True,
        )

        chat_model = ChatOpenAI(
            model=model,
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout,
            default_headers=self.default_headers if self.default_headers else None,
            **extra_kwargs,
        )

        super().__init__(
            llm=chat_model,
            provider_name=provider_name,
            model=model,
            capabilities=caps,
        )
