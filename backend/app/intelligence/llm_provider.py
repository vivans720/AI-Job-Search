from typing import Any
import structlog

from app.config import settings
from app.intelligence.base import BaseAIProvider, clean_and_extract_json
from app.intelligence.gateway import AIGateway
from app.intelligence.registry import ProviderRegistry
from app.intelligence.providers.openai_compatible import OpenAICompatibleProvider

logger = structlog.get_logger(__name__)

_cached_providers: dict[str, BaseAIProvider] = {}


def _instantiate_single_provider(
    provider_name: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: float | None = None,
) -> BaseAIProvider:
    raw_name = (provider_name or settings.LLM_PROVIDER).strip()
    _, resolved_model = ProviderRegistry.resolve_model_reference(raw_name)
    target_model = model or (resolved_model if resolved_model != raw_name else None) or settings.OMNIROUTE_MODEL or settings.DEFAULT_AGENT_MODEL

    target_base_url = (base_url or settings.OMNIROUTE_BASE_URL).rstrip("/")
    target_api_key = api_key or settings.OMNIROUTE_API_KEY or "dummy-key"
    target_timeout = timeout or settings.OMNIROUTE_TIMEOUT or settings.LLM_TIMEOUT

    return OpenAICompatibleProvider(
        base_url=target_base_url,
        api_key=target_api_key,
        model=target_model,
        timeout=target_timeout,
        provider_name="omniroute",
    )


def create_ai_provider(
    provider_name: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: float | None = None,
    enable_gateway: bool = False,
    fallback_provider: str | None = None,
    fallback_model: str | None = None,
) -> BaseAIProvider:
    """Factory creating an OmniRoute gateway provider instance or resilient AIGateway."""
    primary = _instantiate_single_provider(
        provider_name=provider_name,
        model=model,
        base_url=base_url,
        api_key=api_key,
        timeout=timeout,
    )

    if not enable_gateway:
        return primary

    # If fallback model is specified, configure secondary provider instance against OmniRoute
    secondary: BaseAIProvider | None = None
    if fallback_model:
        secondary = _instantiate_single_provider(
            provider_name=fallback_provider or "omniroute",
            model=fallback_model,
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
        )

    return AIGateway(primary=primary, fallback=secondary)


def get_llm_provider(
    provider_name: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    fallback_provider: str | None = None,
    fallback_model: str | None = None,
    enable_gateway: bool = True,
) -> BaseAIProvider:
    """Returns a cached or dynamically configured OmniRoute AI provider wrapped in AIGateway."""
    global _cached_providers

    if any([provider_name, model, base_url, api_key, fallback_provider, fallback_model]):
        return create_ai_provider(
            provider_name=provider_name,
            model=model,
            base_url=base_url,
            api_key=api_key,
            enable_gateway=enable_gateway,
            fallback_provider=fallback_provider,
            fallback_model=fallback_model,
        )

    cache_key = f"default_{'gateway' if enable_gateway else 'raw'}"
    if cache_key not in _cached_providers:
        _cached_providers[cache_key] = create_ai_provider(enable_gateway=enable_gateway)
    return _cached_providers[cache_key]


def reset_ai_provider_cache() -> None:
    """Clear cached provider instances on configuration update."""
    global _cached_providers
    _cached_providers.clear()
