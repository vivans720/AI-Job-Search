from typing import Any
import structlog

from app.config import settings
from app.intelligence.base import BaseAIProvider, clean_and_extract_json
from app.intelligence.providers.ollama_provider import OllamaProvider
from app.intelligence.providers.openai_provider import OpenAIProvider
from app.intelligence.providers.gemini_provider import GeminiProvider
from app.intelligence.providers.anthropic_provider import AnthropicProvider

logger = structlog.get_logger(__name__)

# Backward compatibility alias
LLMProvider = BaseAIProvider
OllamaLLM = OllamaProvider
OmniRouteLLM = OpenAIProvider

_cached_providers: dict[str, BaseAIProvider] = {}


def create_ai_provider(
    provider_name: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: float | None = None,
) -> BaseAIProvider:
    """Factory creating an AI provider instance from name and custom configuration."""
    name = (provider_name or settings.LLM_PROVIDER).lower().strip()

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

    elif name in ("deepseek",):
        return OpenAIProvider(
            base_url=base_url or settings.DEEPSEEK_BASE_URL,
            api_key=api_key or settings.DEEPSEEK_API_KEY,
            model=model or settings.DEEPSEEK_MODEL,
            timeout=timeout or settings.DEEPSEEK_TIMEOUT,
            provider_name="deepseek",
        )

    elif name in ("omniroute", "openai_compatible", "generic", "vllm", "openrouter"):
        return OpenAIProvider(
            base_url=base_url or settings.LLM_BASE_URL,
            api_key=api_key or settings.LLM_API_KEY,
            model=model or settings.LLM_MODEL,
            timeout=timeout or settings.LLM_TIMEOUT,
            provider_name=name,
        )

    else:
        logger.warning("unknown_provider_fallback_to_ollama", requested=name)
        return OllamaProvider(base_url=base_url, model=model, timeout=timeout)


def get_llm_provider(
    provider_name: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> BaseAIProvider:
    """Returns a cached or dynamically configured AI provider singleton."""
    global _cached_providers

    # If dynamic custom config provided, do not cache global
    if any([provider_name, model, base_url, api_key]):
        return create_ai_provider(
            provider_name=provider_name,
            model=model,
            base_url=base_url,
            api_key=api_key,
        )

    cache_key = "default"
    if cache_key not in _cached_providers:
        _cached_providers[cache_key] = create_ai_provider()
    return _cached_providers[cache_key]


def reset_ai_provider_cache() -> None:
    """Clear cached provider instances on configuration update."""
    global _cached_providers
    _cached_providers.clear()
