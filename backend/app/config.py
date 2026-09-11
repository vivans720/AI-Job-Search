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

    # LLM Provider Selection
    LLM_PROVIDER: str = "ollama"

    # Ollama (Primary)
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    OLLAMA_MODEL: str = "qwen3.5:9b"
    OLLAMA_CONTEXT_WINDOW: int = 16384
    OLLAMA_TIMEOUT: float = 60.0

    # OmniRoute / OpenAI Compatible (Fallback)
    LLM_BASE_URL: str = "http://localhost:20128/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "auto/best-fast"

    # LLM Skill Extraction Fallback
    LLM_SKILL_EXTRACTION_ENABLED: bool = True
    LLM_SKILL_EXTRACTION_TIMEOUT: float = 10.0
    LLM_SKILL_EXTRACTION_MIN_DESCRIPTION_LENGTH: int = 200
    LLM_SKILL_EXTRACTION_MIN_DETERMINISTIC_SKILLS: int = 2

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
