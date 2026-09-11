import random
from typing import Any
import structlog

logger = structlog.get_logger(__name__)

STEALTH_INIT_SCRIPT = """
// 1. Strip Webdriver signatures
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// 2. Emulate Chrome runtime
window.chrome = { runtime: {} };

// 3. Emulate browser plugins
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });

// 4. Emulate regional language preferences
Object.defineProperty(navigator, 'languages', { get: () => ['en-IN', 'en-US', 'en'] });
"""

DEFAULT_STEALTH_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)

BLOCKED_RESOURCE_TYPES = frozenset({"image", "media", "font"})

BLOCKED_EXTENSIONS = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".ico",
    ".mp4",
    ".webm",
    ".avi",
    ".mov",
)

BLOCKED_URL_SUBSTRINGS = (
    "analytics",
    "telemetry",
    "doubleclick",
    "google-analytics",
    "googletagmanager",
    "hotjar",
    "datadog",
    "segment.io",
    "clarity.ms",
    "newrelic",
    "facebook.net",
    "connect.facebook",
    "branch.io",
    "sentry.io",
)


def get_random_viewport() -> dict[str, int]:
    """Generates a randomized screen geometry within standard desktop bounds."""
    width = random.randint(1366, 1920)
    height = random.randint(768, 1080)
    return {"width": width, "height": height}


def should_abort_resource(resource_type: str, url: str) -> bool:
    """
    Evaluates whether an outbound browser asset request should be cancelled.
    Blocks media assets, custom web fonts, and third-party tracking beacons.
    """
    res_type = (resource_type or "").lower()
    if res_type in BLOCKED_RESOURCE_TYPES:
        return True

    url_lower = (url or "").lower()
    for ext in BLOCKED_EXTENSIONS:
        if url_lower.endswith(ext) or f"{ext}?" in url_lower:
            return True

    for pattern in BLOCKED_URL_SUBSTRINGS:
        if pattern in url_lower:
            return True

    return False


async def apply_stealth_context(context: Any) -> None:
    """
    Applies strict anti-fingerprinting configurations to a Playwright BrowserContext.
    Costs nothing and bypasses basic automated-browser triggers.
    """
    # 1. Inject anti-detection script before any page script loads
    await context.add_init_script(STEALTH_INIT_SCRIPT)

    # 2. Randomise screen geometries to simulate a real user window
    viewport = get_random_viewport()
    if hasattr(context, "set_viewport_size"):
        await context.set_viewport_size(viewport)
    elif hasattr(context, "pages"):
        for p in context.pages:
            if hasattr(p, "set_viewport_size"):
                await p.set_viewport_size(viewport)

    # 3. Set a stable, common user-agent and language headers
    await context.set_extra_http_headers({
        "User-Agent": DEFAULT_STEALTH_USER_AGENT,
        "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
    })

    logger.debug("browser_stealth_context_applied", viewport=viewport)


async def configure_resource_filters(page: Any) -> None:
    """
    Blocks media and tracking assets in real-time.
    Saves bandwidth, reduces memory footprint, and speeds up data ingestion.
    """
    def route_filter(route: Any) -> None:
        try:
            req = route.request
            if should_abort_resource(req.resource_type, req.url):
                return route.abort()
            return route.continue_()
        except Exception:
            return route.continue_()

    # Apply structural block rules across all outbound asset loops
    await page.route("**/*", route_filter)
    logger.debug("browser_resource_filters_configured")
