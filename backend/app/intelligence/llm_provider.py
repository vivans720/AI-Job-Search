from typing import Any
import structlog

from app.config import settings
from app.intelligence.base import BaseAIProvider, clean_and_extract_json
from app.intelligence.gateway import AIGateway
from app.intelligence.registry import ProviderRegistry
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

# Backward compatibility aliases
LLMProvider = BaseAIProvider
OllamaLLM = OllamaProvider
OmniRouteLLM = OpenAIProvider

_cached_providers: dict[str, BaseAIProvider] = {}


def _instantiate_single_provider(
    provider_name: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: float | None = None,
) -> BaseAIProvider:
    raw_name = (provider_name or settings.LLM_PROVIDER).strip()
    # Check if model reference has prefix, e.g. "openrouter/meta-llama/..."
    resolved_provider, resolved_model = ProviderRegistry.resolve_model_reference(raw_name)
    if resolved_provider != "openai" and raw_name != "openai" and not model:
        name = resolved_provider
        model = resolved_model
    else:
        name = raw_name.lower()

    if name in ("ollama", "local"):
        return OllamaProvider(base_url=base_url, model=model, timeout=timeout)

    elif name in ("openai",):
        return OpenAIProvider(
            base_url=base_url or settings.OPENAI_BASE_URL,
            api_key=api_key or settings.OPENAI_API_KEY,
            model=model or settings.OPENAI_MODEL,
            timeout=timeout or settings.OPENAI_TIMEOUT,
            provider_name="openai",
        )

    elif name in ("gemini", "google"):
        return GeminiProvider(
            base_url=base_url or settings.GEMINI_BASE_URL,
            api_key=api_key or settings.GEMINI_API_KEY,
            model=model or settings.GEMINI_MODEL,
            timeout=timeout or settings.GEMINI_TIMEOUT,
        )

    elif name in ("anthropic", "claude"):
        return AnthropicProvider(
            base_url=base_url or settings.ANTHROPIC_BASE_URL,
            api_key=api_key or settings.ANTHROPIC_API_KEY,
            model=model or settings.ANTHROPIC_MODEL,
            timeout=timeout or settings.ANTHROPIC_TIMEOUT,
        )

    elif name in ("groq",):
        return GroqProvider(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout=timeout,
        )

    elif name in ("openrouter",):
        return OpenRouterProvider(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout=timeout,
        )

    elif name in ("cerebras",):
        return CerebrasProvider(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout=timeout,
        )

    elif name in ("mistral",):
        return MistralProvider(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout=timeout,
        )

    elif name in ("nvidia-nim", "nvidia", "nim"):
        return NVIDIAProvider(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout=timeout,
        )

    elif name in ("opencode",):
        return OpenCodeProvider(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout=timeout,
        )

    elif name in ("deepseek",):
        return OpenAIProvider(
            base_url=base_url or settings.DEEPSEEK_BASE_URL,
            api_key=api_key or settings.DEEPSEEK_API_KEY,
            model=model or settings.DEEPSEEK_MODEL,
            timeout=timeout or settings.DEEPSEEK_TIMEOUT,
            provider_name="deepseek",
        )

    elif name in ("openai-compatible", "openai_compatible", "generic", "vllm", "omniroute", "custom"):
        return OpenAIProvider(
            base_url=base_url or settings.CUSTOM_AI_BASE_URL or settings.LLM_BASE_URL,
            api_key=api_key or settings.CUSTOM_AI_API_KEY or settings.LLM_API_KEY,
            model=model or settings.CUSTOM_AI_MODEL or settings.LLM_MODEL,
            timeout=timeout or settings.LLM_TIMEOUT,
            provider_name=name,
        )

    else:
        logger.warning("unknown_provider_fallback_to_ollama", requested=name)
        return OllamaProvider(base_url=base_url, model=model, timeout=timeout)


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
    """Factory creating an AI provider instance or resilient AIGateway."""
    primary = _instantiate_single_provider(
        provider_name=provider_name,
        model=model,
        base_url=base_url,
        api_key=api_key,
        timeout=timeout,
    )

    if not enable_gateway:
        return primary

    fb_name = fallback_provider or settings.LLM_FALLBACK_PROVIDER
    secondary: BaseAIProvider | None = None
    if fb_name and fb_name.lower() != (provider_name or settings.LLM_PROVIDER).lower():
        secondary = _instantiate_single_provider(
            provider_name=fb_name,
            model=fallback_model or settings.LLM_FALLBACK_MODEL,
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
    """Returns a cached or dynamically configured AI provider singleton wrapped in AIGateway."""
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

    cache_key = "default_gateway" if enable_gateway else "default_raw"
    if cache_key not in _cached_providers:
        _cached_providers[cache_key] = create_ai_provider(enable_gateway=enable_gateway)
    return _cached_providers[cache_key]


def reset_ai_provider_cache() -> None:
    """Clear cached provider instances on configuration update."""
    global _cached_providers
    _cached_providers.clear()
