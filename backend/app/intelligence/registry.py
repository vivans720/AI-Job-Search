from typing import Any, Type
import structlog

from app.config import settings
from app.intelligence.base import BaseAIProvider
from app.intelligence.models import AIModel, ProviderCapabilities, ProviderMetadata
from app.intelligence.providers.anthropic_provider import AnthropicProvider
from app.intelligence.providers.cerebras_provider import CerebrasProvider
from app.intelligence.providers.gemini_provider import GeminiProvider
from app.intelligence.providers.groq_provider import GroqProvider
from app.intelligence.providers.mistral_provider import MistralProvider
from app.intelligence.providers.nvidia_provider import NVIDIAProvider
from app.intelligence.providers.ollama_provider import OllamaProvider
from app.intelligence.providers.opencode_provider import OpenCodeProvider
from app.intelligence.providers.openai_compatible import OpenAICompatibleProvider
from app.intelligence.providers.openai_provider import OpenAIProvider
from app.intelligence.providers.openrouter_provider import OpenRouterProvider

logger = structlog.get_logger(__name__)


class ProviderRegistry:
    """Central registry of all supported AI providers and model metadata."""

    _providers: dict[str, Type[BaseAIProvider]] = {}
    _metadata: dict[str, ProviderMetadata] = {}

    @classmethod
    def register(cls, provider_id: str, provider_cls: Type[BaseAIProvider], metadata: ProviderMetadata) -> None:
        cls._providers[provider_id.lower()] = provider_cls
        cls._metadata[provider_id.lower()] = metadata

    @classmethod
    def get_provider_class(cls, provider_id: str) -> Type[BaseAIProvider] | None:
        return cls._providers.get(provider_id.lower())

    @classmethod
    def get_metadata(cls, provider_id: str) -> ProviderMetadata | None:
        return cls._metadata.get(provider_id.lower())

    @classmethod
    def list_providers(cls) -> list[ProviderMetadata]:
        return list(cls._metadata.values())

    @classmethod
    def resolve_model_reference(cls, model_ref: str) -> tuple[str, str]:
        """Parses model reference string into (provider_id, model_name).

        Examples:
        - "openrouter/meta-llama/llama-3.3-70b-instruct" -> ("openrouter", "meta-llama/llama-3.3-70b-instruct")
        - "groq/llama-3.3-70b-versatile" -> ("groq", "llama-3.3-70b-versatile")
        - "anthropic/claude-3-5-haiku" -> ("anthropic", "claude-3-5-haiku")
        - "gpt-4o-mini" -> ("openai", "gpt-4o-mini")
        """
        ref = model_ref.strip()
        if "/" in ref:
            prefix, rest = ref.split("/", 1)
            p_id = prefix.lower()
            if p_id in cls._providers:
                return p_id, rest
            # Special case for "google/gemini" or "nvidia-nim/..."
            if p_id in ("google", "gemini"):
                return "gemini", rest
            if p_id in ("claude", "anthropic"):
                return "anthropic", rest
            if p_id in ("nvidia", "nim", "nvidia-nim"):
                return "nvidia-nim", rest
        return "openai", ref


# Register all 11 providers
ProviderRegistry.register(
    "ollama",
    OllamaProvider,
    ProviderMetadata(
        id="ollama",
        name="Ollama (Local LLM)",
        type="local",
        default_model=settings.OLLAMA_MODEL,
        requires_api_key=False,
        description="Local-first private inference. Zero cloud cost, high privacy.",
        capabilities=ProviderCapabilities(
            supports_streaming=True,
            supports_tools=True,
            supports_structured_output=True,
            supports_vision=False,
            supports_reasoning=False,
            supports_model_discovery=True,
        ),
    ),
)

ProviderRegistry.register(
    "openai",
    OpenAIProvider,
    ProviderMetadata(
        id="openai",
        name="OpenAI",
        type="cloud",
        default_model=settings.OPENAI_MODEL,
        requires_api_key=True,
        description="Official OpenAI API (GPT-4o, GPT-4o-mini, o1/o3-mini).",
        capabilities=ProviderCapabilities(
            supports_streaming=True,
            supports_tools=True,
            supports_structured_output=True,
            supports_vision=True,
            supports_reasoning=True,
            supports_model_discovery=True,
        ),
    ),
)

ProviderRegistry.register(
    "gemini",
    GeminiProvider,
    ProviderMetadata(
        id="gemini",
        name="Google AI / Gemini",
        type="cloud",
        default_model=settings.GEMINI_MODEL,
        requires_api_key=True,
        description="Google Gemini via official OpenAI-compatible endpoint with multimodal and thinking support.",
        capabilities=ProviderCapabilities(
            supports_streaming=True,
            supports_tools=True,
            supports_structured_output=True,
            supports_vision=True,
            supports_reasoning=True,
            supports_model_discovery=True,
        ),
    ),
)

ProviderRegistry.register(
    "anthropic",
    AnthropicProvider,
    ProviderMetadata(
        id="anthropic",
        name="Anthropic Claude",
        type="cloud",
        default_model=settings.ANTHROPIC_MODEL,
        requires_api_key=True,
        description="Anthropic Claude 3.5 Haiku / Sonnet via native Messages API.",
        capabilities=ProviderCapabilities(
            supports_streaming=True,
            supports_tools=True,
            supports_structured_output=True,
            supports_vision=True,
            supports_reasoning=True,
            supports_model_discovery=False,
        ),
    ),
)

ProviderRegistry.register(
    "groq",
    GroqProvider,
    ProviderMetadata(
        id="groq",
        name="Groq",
        type="cloud",
        default_model=settings.GROQ_MODEL,
        requires_api_key=True,
        description="Ultra-fast LPU inference for Llama 3.3, Mixtral, and Gemma models.",
        capabilities=ProviderCapabilities(
            supports_streaming=True,
            supports_tools=True,
            supports_structured_output=True,
            supports_vision=False,
            supports_reasoning=False,
            supports_model_discovery=True,
        ),
    ),
)

ProviderRegistry.register(
    "openrouter",
    OpenRouterProvider,
    ProviderMetadata(
        id="openrouter",
        name="OpenRouter",
        type="cloud",
        default_model=settings.OPENROUTER_MODEL,
        requires_api_key=True,
        description="Unified gateway with full model routing across 200+ models and providers.",
        capabilities=ProviderCapabilities(
            supports_streaming=True,
            supports_tools=True,
            supports_structured_output=True,
            supports_vision=True,
            supports_reasoning=True,
            supports_model_discovery=True,
        ),
    ),
)

ProviderRegistry.register(
    "cerebras",
    CerebrasProvider,
    ProviderMetadata(
        id="cerebras",
        name="Cerebras",
        type="cloud",
        default_model=settings.CEREBRAS_MODEL,
        requires_api_key=True,
        description="Wafer-scale high-throughput inference for Llama 3 models.",
        capabilities=ProviderCapabilities(
            supports_streaming=True,
            supports_tools=True,
            supports_structured_output=True,
            supports_vision=False,
            supports_reasoning=False,
            supports_model_discovery=True,
        ),
    ),
)

ProviderRegistry.register(
    "mistral",
    MistralProvider,
    ProviderMetadata(
        id="mistral",
        name="Mistral AI",
        type="cloud",
        default_model=settings.MISTRAL_MODEL,
        requires_api_key=True,
        description="Mistral Small, Large, and Codestral inference models.",
        capabilities=ProviderCapabilities(
            supports_streaming=True,
            supports_tools=True,
            supports_structured_output=True,
            supports_vision=True,
            supports_reasoning=False,
            supports_model_discovery=True,
        ),
    ),
)

ProviderRegistry.register(
    "nvidia-nim",
    NVIDIAProvider,
    ProviderMetadata(
        id="nvidia-nim",
        name="NVIDIA NIM",
        type="cloud",
        default_model=settings.NVIDIA_NIM_MODEL,
        requires_api_key=True,
        description="NVIDIA NIM microservices hosted on API catalog or self-hosted enterprise containers.",
        capabilities=ProviderCapabilities(
            supports_streaming=True,
            supports_tools=True,
            supports_structured_output=True,
            supports_vision=True,
            supports_reasoning=True,
            supports_model_discovery=True,
        ),
    ),
)

ProviderRegistry.register(
    "opencode",
    OpenCodeProvider,
    ProviderMetadata(
        id="opencode",
        name="OpenCode",
        type="local",
        default_model=settings.OPENCODE_MODEL,
        requires_api_key=False,
        description="OpenCode AI coding agent gateway and local runtime integration.",
        capabilities=ProviderCapabilities(
            supports_streaming=True,
            supports_tools=True,
            supports_structured_output=True,
            supports_vision=False,
            supports_reasoning=True,
            supports_model_discovery=True,
        ),
    ),
)

ProviderRegistry.register(
    "openai-compatible",
    OpenAICompatibleProvider,
    ProviderMetadata(
        id="openai-compatible",
        name="Custom / OpenAI-Compatible",
        type="cloud",
        default_model=settings.LLM_MODEL,
        requires_api_key=False,
        description="Any custom OpenAI-compatible endpoint (vLLM, LM Studio, LiteLLM, OmniRoute).",
        capabilities=ProviderCapabilities(
            supports_streaming=True,
            supports_tools=True,
            supports_structured_output=True,
            supports_vision=False,
            supports_reasoning=False,
            supports_model_discovery=True,
        ),
    ),
)
