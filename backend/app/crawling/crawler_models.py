from typing import Any
from pydantic import BaseModel, Field


class CrawlRequest(BaseModel):
    """Encapsulates parameters for web page crawling."""
    url: str
    headers: dict[str, str] = Field(default_factory=dict)
    timeout: float = 20.0
    wait_for: str | None = None
    js_code: str | None = None
    css_selector: str | None = None
    cache_mode: str = "BYPASS"  # "BYPASS", "ENABLED", "READ_ONLY"
    enable_stealth: bool = True
    screenshot: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class CrawlResult(BaseModel):
    """Standard result returned by a CrawlerProvider."""
    url: str
    status_code: int = 200
    success: bool = True
    html: str = ""
    cleaned_html: str = ""
    markdown: str = ""
    error_message: str | None = None
    duration_sec: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractionRequest(BaseModel):
    """Request for extracting structured entities from a URL or raw HTML content."""
    url: str | None = None
    html: str | None = None
    schema_definition: dict[str, Any] = Field(default_factory=dict)
    css_selector: str | None = None
    timeout: float = 20.0


class ExtractionResult(BaseModel):
    """Result of structured data extraction."""
    success: bool = True
    data: list[dict[str, Any]] = Field(default_factory=list)
    raw_markdown: str = ""
    error_message: str | None = None
