from abc import ABC, abstractmethod
from app.crawling.crawler_models import CrawlRequest, CrawlResult, ExtractionRequest, ExtractionResult


class CrawlerProvider(ABC):
    """Abstract interface decoupling source adapters from concrete crawler engines."""

    @abstractmethod
    async def fetch(self, request: CrawlRequest) -> CrawlResult:
        """Fetch raw HTML and markdown from the requested URL."""
        pass

    @abstractmethod
    async def extract(self, request: ExtractionRequest) -> ExtractionResult:
        """Extract structured records according to schema or CSS rules."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Probe provider health and underlying browser/runtime availability."""
        pass


class NoOpCrawlerProvider(CrawlerProvider):
    """Disabled provider. Never launches browser. Always fails closed."""

    async def fetch(self, request: CrawlRequest) -> CrawlResult:
        return CrawlResult(
            url=request.url,
            status_code=503,
            success=False,
            error_message="crawl4ai disabled",
            metadata=request.metadata,
        )

    async def extract(self, request: ExtractionRequest) -> ExtractionResult:
        return ExtractionResult(success=False, error_message="crawl4ai disabled")

    async def health_check(self) -> bool:
        return False
