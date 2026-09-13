try:
    from app.intelligence.providers.ollama_provider import OllamaProvider
except ImportError:
    OllamaProvider = None

try:
    from app.intelligence.providers.openai_provider import OpenAIProvider
except ImportError:
    OpenAIProvider = None

try:
    from app.intelligence.providers.gemini_provider import GeminiProvider
except ImportError:
    GeminiProvider = None

try:
    from app.intelligence.providers.anthropic_provider import AnthropicProvider
except ImportError:
    AnthropicProvider = None

__all__ = [
    "OllamaProvider",
    "OpenAIProvider",
    "GeminiProvider",
    "AnthropicProvider",
]
