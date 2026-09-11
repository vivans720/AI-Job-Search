import structlog
from app.config import settings
from app.crawling.crawler_provider import CrawlerProvider, NoOpCrawlerProvider
from app.crawling.crawl4ai_provider import Crawl4AICrawlerProvider

logger = structlog.get_logger(__name__)

_crawler_provider: CrawlerProvider | None = None


def is_crawl4ai_dependency_installed() -> bool:
    try:
        import crawl4ai  # noqa: F401
        return True
    except Exception:
        return False


def get_crawler_provider() -> CrawlerProvider:
    """Returns singleton provider. Noop when disabled or dependency missing."""
    global _crawler_provider
    if _crawler_provider is None:
        enabled = getattr(settings, "CRAWL4AI_ENABLED", True)
        if enabled and is_crawl4ai_dependency_installed():
            _crawler_provider = Crawl4AICrawlerProvider(
                max_concurrency=getattr(settings, "CRAWL4AI_MAX_CONCURRENCY", 3),
                timeout=getattr(settings, "CRAWL4AI_TIMEOUT", 20.0),
                headless=getattr(settings, "CRAWL4AI_HEADLESS", True),
            )
        else:
            logger.info("crawl4ai_disabled_using_noop", enabled=enabled)
            _crawler_provider = NoOpCrawlerProvider()
    return _crawler_provider


async def get_crawler_capability() -> dict:
    """Distinct states: code exists, dependency installed, enabled, healthy."""
    from app.crawling.crawl4ai_provider import Crawl4AICrawlerProvider as LiveProvider

    installed = is_crawl4ai_dependency_installed()
    enabled = bool(getattr(settings, "CRAWL4AI_ENABLED", True))
    provider = get_crawler_provider()
    healthy = await provider.health_check()
    return {
        "installed": installed,
        "enabled": enabled,
        "healthy": bool(healthy),
        "provider": type(provider).__name__,
        "live": isinstance(provider, LiveProvider) and enabled and installed,
        "used_by": ["linkedin", "internshala", "naukri"] if isinstance(provider, LiveProvider) and enabled else [],
    }


def reset_crawler_provider() -> None:
    """Resets the singleton instance (used in test fixtures)."""
    global _crawler_provider
    _crawler_provider = None
