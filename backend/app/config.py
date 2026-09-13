from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    POSTGRES_USER: str = "jobagent"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "jobagent"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = "postgresql+asyncpg://jobagent:password@localhost:5432/jobagent"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Default Candidate / User
    DEFAULT_USER_EMAIL: str = "candidate@jobsearchai.local"

    # Freshness (backend enforced)
    FRESHNESS_HOURS: int = 24
    DEFAULT_TIMEZONE: str = "Asia/Kolkata"

    # Experience
    EXPERIENCE_MAX_YEARS: int = 2

    # Search Limits
    MAX_SEARCH_ITERATIONS: int = 3
    MAX_RAW_JOBS_PER_SOURCE: int = 100
    MAX_JOBS_FOR_LLM_ANALYSIS: int = 15
    TOP_N_RESULTS: int = 10

    # Matching Weights (Skill-First Architecture)
    WEIGHT_REQUIRED_SKILL_MATCH: float = 0.65
    WEIGHT_PREFERRED_SKILL_MATCH: float = 0.10
    WEIGHT_TRANSFERABLE_SKILL_MATCH: float = 0.10
    WEIGHT_EXPERIENCE_MATCH: float = 0.05
    WEIGHT_LOCATION_MATCH: float = 0.05
    WEIGHT_PREFERENCE_MATCH: float = 0.05
    # Embedding
    EMBEDDING_PROVIDER: str = "local"
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIMENSIONS: int = 384

    # LLM Provider Selection (ollama | openai | gemini | anthropic | openai_compatible | omniroute)
    LLM_PROVIDER: str = "ollama"

    # Ollama (Primary local)
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    OLLAMA_MODEL: str = "qwen3.5:9b"
    OLLAMA_CONTEXT_WINDOW: int = 16384
    OLLAMA_TIMEOUT: float = 60.0

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_TIMEOUT: float = 45.0

    # Gemini (Google GenAI OpenAI-compatible endpoint or native)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    GEMINI_TIMEOUT: float = 45.0

    # Anthropic Claude
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-5-haiku-20241022"
    ANTHROPIC_BASE_URL: str = "https://api.anthropic.com/v1"
    ANTHROPIC_TIMEOUT: float = 45.0

    # Fallback Provider Configuration
    LLM_FALLBACK_PROVIDER: str | None = None
    LLM_FALLBACK_MODEL: str | None = None

    # DeepSeek
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_TIMEOUT: float = 45.0

    # Groq
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_TIMEOUT: float = 30.0

    # OpenRouter
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "meta-llama/llama-3.3-70b-instruct"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_TIMEOUT: float = 45.0

    # Cerebras
    CEREBRAS_API_KEY: str = ""
    CEREBRAS_MODEL: str = "llama3.3-70b"
    CEREBRAS_BASE_URL: str = "https://api.cerebras.ai/v1"
    CEREBRAS_TIMEOUT: float = 30.0

    # Mistral
    MISTRAL_API_KEY: str = ""
    MISTRAL_MODEL: str = "mistral-small-latest"
    MISTRAL_BASE_URL: str = "https://api.mistral.ai/v1"
    MISTRAL_TIMEOUT: float = 45.0

    # NVIDIA NIM
    NVIDIA_NIM_API_KEY: str = ""
    NVIDIA_NIM_MODEL: str = "meta/llama-3.3-70b-instruct"
    NVIDIA_NIM_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_NIM_TIMEOUT: float = 45.0

    # OpenCode (Local / Remote AI Coding gateway)
    OPENCODE_BASE_URL: str = "http://localhost:4096/v1"
    OPENCODE_MODEL: str = "opencode-default"
    OPENCODE_API_KEY: str = ""
    OPENCODE_TIMEOUT: float = 45.0

    # Generic / Local Fallback AI
    LLM_BASE_URL: str = "http://localhost:11434/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "auto/best-fast"
    LLM_TIMEOUT: float = 45.0
    CUSTOM_AI_BASE_URL: str = ""
    CUSTOM_AI_API_KEY: str = ""
    CUSTOM_AI_MODEL: str = ""


    # Sources
    SOURCE_SAMPLE_ENABLED: bool = False
    SOURCE_INTERNSHALA_ENABLED: bool = True
    SOURCE_NAUKRI_ENABLED: bool = True
    SOURCE_LINKEDIN_ENABLED: bool = True

    # Crawl4AI Infrastructure
    CRAWL4AI_ENABLED: bool = True
    CRAWL4AI_HEADLESS: bool = True
    CRAWL4AI_MAX_CONCURRENCY: int = 3
    CRAWL4AI_TIMEOUT: float = 20.0

    # Browser & Scraping Hardening
    BROWSER_USER_DATA_DIR: str = "~/.config/job_agent_browser_profile"
    BROWSER_HEADLESS: bool = True
    BROWSER_SLOW_MO: int = 50

    # Tor Network Proxy Fallback
    TOR_PROXY_URL: str = "socks5://127.0.0.1:9050"
    TOR_ENABLED: bool = True
    TOR_FALLBACK_ON_BLOCKED: bool = True


settings = Settings()
