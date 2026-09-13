# Multi-Provider AI Gateway & LLM Integration Guide

This document describes the multi-provider LLM gateway architecture of **AI Job Agent India**.

## 1. Supported Providers & Capability Matrix

| Provider | Type | Default Model | Streaming | Tool Calling | Structured JSON | Vision | Reasoning | Key / Auth |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Ollama** | Local | `qwen3.5:9b` | ✓ | ✓ | ✓ | ✕ | ✕ | Zero key (private) |
| **OpenAI** | Cloud | `gpt-4o-mini` | ✓ | ✓ | ✓ | ✓ | ✓ (o1/o3) | `OPENAI_API_KEY` |
| **Google Gemini** | Cloud | `gemini-2.0-flash` | ✓ | ✓ | ✓ | ✓ | ✓ | `GEMINI_API_KEY` |
| **Anthropic Claude** | Cloud | `claude-3-5-haiku` | ✓ | ✓ | ✓ | ✓ | ✓ | `ANTHROPIC_API_KEY` |
| **Groq** | Cloud | `llama-3.3-70b-versatile` | ✓ | ✓ | ✓ | ✕ | ✕ | `GROQ_API_KEY` |
| **OpenRouter** | Cloud | `meta-llama/llama-3.3-70b` | ✓ | ✓ | ✓ | ✓ | ✓ | `OPENROUTER_API_KEY` |
| **Cerebras** | Cloud | `llama3.3-70b` | ✓ | ✓ | ✓ | ✕ | ✕ | `CEREBRAS_API_KEY` |
| **Mistral AI** | Cloud | `mistral-small-latest` | ✓ | ✓ | ✓ | ✓ | ✕ | `MISTRAL_API_KEY` |
| **NVIDIA NIM** | Cloud/Local | `meta/llama-3.3-70b-instruct` | ✓ | ✓ | ✓ | ✓ | ✓ | `NVIDIA_NIM_API_KEY` |
| **OpenCode** | Local | `opencode-default` | ✓ | ✓ | ✓ | ✕ | ✓ | Optional |
| **OpenAI-Compatible** | Cloud/Local | `auto/best-fast` | ✓ | ✓ | ✓ | ✕ | ✕ | Optional / Custom |

## 2. Gateway & LangChain Integration Architecture

LangChain serves as the underlying provider integration layer, wrapped cleanly behind the application's domain abstractions (`BaseAIProvider`, `AIGateway`, and `AIService`). Domain services, FastMCP tools, and API routes never import LangChain classes directly.

```
AIService / API Routes / FastMCP
          │
          ▼
      AIGateway (Bounded backoff, transient fallback, telemetry)
          │
          ▼
     BaseAIProvider
          │
          ▼
   LangChainAIProvider (Base adapter translating ChatModel to BaseAIProvider)
          │
  ┌───────┴──────────────────────────────────────────────────────┐
  ▼                                                              ▼
Specialized Partner ChatModels                           ChatOpenAI (Configurable)
- ChatAnthropic (langchain-anthropic)                    - OpenAI
- ChatGoogleGenerativeAI (langchain-google-genai)        - Groq (ChatGroq)
- ChatMistralAI (langchain-mistralai)                    - OpenRouter (ChatOpenAI + routing headers)
- ChatOllama (langchain-ollama)                          - NVIDIA NIM (ChatOpenAI hosted / self-hosted)
                                                         - Cerebras (ChatOpenAI)
                                                         - OpenCode (ChatOpenAI configurable base_url)
                                                         - Generic OpenAI-Compatible (vLLM / LM Studio)
```

1. **Provider Registry (`ProviderRegistry`)**: Central registry for all 11 providers with metadata, default models, and model reference routing (`provider/model_name`).
2. **LangChain Adapter (`LangChainAIProvider`)**: Normalizes chat completion, structured JSON output (`with_structured_output` or JSON mode fallback), tool calling (`bind_tools`), and token streaming across all models.
3. **Exponential Backoff Retries**: Automatically retries transient errors (HTTP 429, 5xx, timeouts, connection resets) with bounded backoff.
4. **Transient Fallback**: If the primary provider suffers an outage, the gateway automatically falls back to `LLM_FALLBACK_PROVIDER`. Non-transient errors (400 Bad Request, invalid syntax) are never routed to fallback.
5. **Normalized Streaming & Tool Calling**: Standard event models (`TextDelta`, `ToolCallDelta`, `UsageEvent`, `StreamCompleted`) abstract provider-specific differences.

## 3. Environment Variables

```env
# Primary & Fallback Selection
LLM_PROVIDER=ollama
LLM_MODEL=qwen3.5:9b
LLM_FALLBACK_PROVIDER=
LLM_FALLBACK_MODEL=

# Cloud Provider Keys & Endpoints
OPENAI_API_KEY=
GEMINI_API_KEY=
ANTHROPIC_API_KEY=
GROQ_API_KEY=
OPENROUTER_API_KEY=
CEREBRAS_API_KEY=
MISTRAL_API_KEY=
NVIDIA_NIM_API_KEY=
NVIDIA_NIM_BASE_URL=https://integrate.api.nvidia.com/v1

# Local Providers
OLLAMA_BASE_URL=http://localhost:11434/v1
OPENCODE_BASE_URL=http://localhost:4096/v1
CUSTOM_AI_BASE_URL=
CUSTOM_AI_API_KEY=
CUSTOM_AI_MODEL=
```
