from typing import Any, Type
import structlog

from app.config import settings
from app.intelligence.base import BaseAIProvider
from app.intelligence.models import AIModel, ProviderCapabilities, ProviderMetadata
from app.intelligence.providers.openai_compatible import OpenAICompatibleProvider

logger = structlog.get_logger(__name__)


class ProviderRegistry:
    """Central registry of supported AI gateways and model metadata.
    In Phase 1, OmniRoute serves as the unified OpenAI-compatible gateway.
    """

    _providers: dict[str, Type[BaseAIProvider]] = {}
    _metadata: dict[str, ProviderMetadata] = {}

    @classmethod
    def register(cls, provider_id: str, provider_cls: Type[BaseAIProvider], metadata: ProviderMetadata) -> None:
        cls._providers[provider_id.lower()] = provider_cls
        cls._metadata[provider_id.lower()] = metadata

    @classmethod
    def get_provider_class(cls, provider_id: str) -> Type[BaseAIProvider] | None:
        return cls._providers.get(provider_id.lower()) or cls._providers.get("omniroute")

    @classmethod
    def get_metadata(cls, provider_id: str) -> ProviderMetadata | None:
        return cls._metadata.get(provider_id.lower()) or cls._metadata.get("omniroute")

    @classmethod
    def list_providers(cls) -> list[ProviderMetadata]:
        return list(cls._metadata.values())

    @classmethod
    def resolve_model_reference(cls, model_ref: str) -> tuple[str, str]:
        """Parses model reference string into (provider_id, model_name).
        Under OmniRoute, models can be referenced directly or with omniroute/ prefix.
        """
        ref = model_ref.strip()
        if "/" in ref:
            prefix, rest = ref.split("/", 1)
            p_id = prefix.lower()
            if p_id in ("omniroute", "openai_compatible", "openai"):
                return "omniroute", rest
            return "omniroute", ref
        return "omniroute", ref


# Register OmniRoute as the single primary AI gateway
ProviderRegistry.register(
    "omniroute",
    OpenAICompatibleProvider,
    ProviderMetadata(
        id="omniroute",
        name="OmniRoute AI Gateway",
        type="cloud",
        default_model=settings.OMNIROUTE_MODEL,
        requires_api_key=False,
        base_url=settings.OMNIROUTE_BASE_URL,
        description="Unified model gateway providing automatic routing, fallbacks, and multi-model access.",
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
