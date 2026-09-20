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

    # LLM Inference Gateway (OmniRoute single model gateway)
    LLM_PROVIDER: str = "omniroute"
    LLM_TIMEOUT: float = 45.0

    # OmniRoute (Single AI Gateway Inference Endpoint)
    OMNIROUTE_BASE_URL: str = "http://localhost:8000/v1"
    OMNIROUTE_API_KEY: str = ""
    OMNIROUTE_MODEL: str = "gpt-4o-mini"
    OMNIROUTE_TIMEOUT: float = 45.0
    DEFAULT_AGENT_MODEL: str = "gpt-4o-mini"


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
    BROWSER_PROFILE_ROOT: str = "~/.config/job_agent_browser_profile"
    BROWSER_HEADLESS: bool = True
    BROWSER_SLOW_MO: int = 50

    # Tor Network Proxy Fallback
    TOR_PROXY_URL: str = "socks5://127.0.0.1:9050"
    TOR_ENABLED: bool = True
    TOR_FALLBACK_ON_BLOCKED: bool = True

    # Source Rate Limiting (req / window_seconds)
    RATE_LIMIT_LINKEDIN_RATE: int = 10
    RATE_LIMIT_LINKEDIN_PER: float = 60.0
    RATE_LIMIT_NAUKRI_RATE: int = 15
    RATE_LIMIT_NAUKRI_PER: float = 60.0
    RATE_LIMIT_INTERNSHALA_RATE: int = 20
    RATE_LIMIT_INTERNSHALA_PER: float = 60.0

    # Sync Query & Pagination Limits
    SYNC_DEFAULT_JOB_LIMIT: int = 100
    SYNC_MAX_PAGES_FRESH: int = 3
    SYNC_MAX_PAGES_STANDARD: int = 5
    INTERNSHALA_MAX_PAGES: int = 4

    # Audit logging
    SYNC_AUDIT_LOG_PATH: str = "backend/data/sync_log.jsonl"


settings = Settings()
