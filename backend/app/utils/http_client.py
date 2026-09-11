import asyncio
import random
import socket
from dataclasses import dataclass, field
from typing import Any, Iterator
from urllib.parse import urlparse
import httpx
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


@dataclass
class HTTPResult:
    """Standardized result of a resilient HTTP request."""
    status_code: int
    text: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    error: str | None = None
    attempt_count: int = 1
    routed_via: str = "direct"  # "direct" or "tor"

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    @property
    def is_blocked(self) -> bool:
        return self.status_code in (403, 406)

    @property
    def is_rate_limited(self) -> bool:
        return self.status_code == 429

    def __iter__(self) -> Iterator[Any]:
        """Allows unpacking as `status_code, text = result` for tuple compatibility."""
        yield self.status_code
        yield self.text


def is_tor_proxy_available(proxy_url: str | None = None) -> bool:
    """
    Verifies if a local Tor SOCKS5 proxy is actively listening.
    Default proxy_url comes from settings.TOR_PROXY_URL (e.g. socks5://127.0.0.1:9050).
    """
    url = proxy_url or getattr(settings, "TOR_PROXY_URL", "socks5://127.0.0.1:9050")
    try:
        parsed = urlparse(url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 9050
        with socket.create_connection((host, port), timeout=0.3):
            return True
    except (OSError, socket.error):
        return False


async def fetch_via_tor_proxy(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 20.0,
    follow_redirects: bool = True,
    caller_tag: str = "http_client",
    proxy_url: str | None = None,
) -> HTTPResult | None:
    """
    Attempts to execute request routed through local Tor SOCKS5 proxy.
    Returns HTTPResult if completed, or None if SOCKS routing fails or dependency missing.
    """
    tor_proxy = proxy_url or getattr(settings, "TOR_PROXY_URL", "socks5://127.0.0.1:9050")
    req_headers = headers or {}
    try:
        async with httpx.AsyncClient(proxy=tor_proxy, headers=req_headers, timeout=timeout) as client:
            logger.info("http_tor_fallback_dispatched", caller=caller_tag, url=url, proxy=tor_proxy)
            resp = await client.get(url, follow_redirects=follow_redirects)
            return HTTPResult(
                status_code=resp.status_code,
                text=resp.text,
                headers=dict(resp.headers),
                attempt_count=1,
                routed_via="tor",
                error=None if 200 <= resp.status_code < 300 else f"TOR_STATUS_{resp.status_code}",
            )
    except Exception as e:
        logger.warning("http_tor_fallback_failed", caller=caller_tag, url=url, error=str(e))
        return None


async def resilient_fetch(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    follow_redirects: bool = True,
    caller_tag: str = "http_client",
    enable_tor_fallback: bool = True,
) -> HTTPResult:
    """
    Executes an asynchronous HTTP GET request with exponential backoff, random jitter,
    and anti-bot / rate-limit detection with automatic Tor SOCKS5 proxy fallback.

    - 200 OK: Returns immediately.
    - 403 / 406: Anti-bot blocked. Tries Tor SOCKS5 proxy fallback before returning.
    - 429: Rate limited. Retries with exponential backoff; triggers Tor fallback if persistent.
    - 5xx / Network / Timeout errors: Retried with exponential backoff up to max_retries.
    """
    req_headers = headers or {}

    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(headers=req_headers, timeout=timeout) as client:
                response = await client.get(url, follow_redirects=follow_redirects)
                status_code = response.status_code
                resp_headers = dict(response.headers)

                if 200 <= status_code < 300:
                    return HTTPResult(
                        status_code=status_code,
                        text=response.text,
                        headers=resp_headers,
                        attempt_count=attempt,
                        routed_via="direct",
                    )

                # Anti-bot detection (Cloudflare, Akamai, reCAPTCHA, etc.)
                if status_code in (403, 406):
                    logger.warning(
                        "http_anti_bot_blocked",
                        caller=caller_tag,
                        url=url,
                        status_code=status_code,
                        attempt=attempt,
                    )
                    # Attempt Tor fallback if configured and available
                    if enable_tor_fallback and getattr(settings, "TOR_FALLBACK_ON_BLOCKED", True) and is_tor_proxy_available():
                        tor_res = await fetch_via_tor_proxy(
                            url,
                            headers=req_headers,
                            timeout=timeout + 5.0,
                            follow_redirects=follow_redirects,
                            caller_tag=caller_tag,
                        )
                        if tor_res and tor_res.is_success:
                            return tor_res

                    return HTTPResult(
                        status_code=status_code,
                        text=response.text,
                        headers=resp_headers,
                        error="ANTI_BOT_BLOCKED",
                        attempt_count=attempt,
                        routed_via="direct",
                    )

                # Rate limited
                if status_code == 429:
                    wait_sec = min(base_delay * (2 ** (attempt - 1)) + random.uniform(0.1, 0.9), max_delay)
                    logger.warning(
                        "http_rate_limited",
                        caller=caller_tag,
                        url=url,
                        attempt=attempt,
                        wait_sec=round(wait_sec, 2),
                    )
                    if attempt < max_retries:
                        await asyncio.sleep(wait_sec)
                        continue

                    # On final rate-limit exhaustion, attempt Tor fallback
                    if enable_tor_fallback and getattr(settings, "TOR_FALLBACK_ON_BLOCKED", True) and is_tor_proxy_available():
                        tor_res = await fetch_via_tor_proxy(
                            url,
                            headers=req_headers,
                            timeout=timeout + 5.0,
                            follow_redirects=follow_redirects,
                            caller_tag=caller_tag,
                        )
                        if tor_res and tor_res.is_success:
                            return tor_res

                    return HTTPResult(
                        status_code=status_code,
                        text=response.text,
                        headers=resp_headers,
                        error="RATE_LIMITED",
                        attempt_count=attempt,
                        routed_via="direct",
                    )

                # Server errors (5xx)
                if status_code >= 500:
                    wait_sec = min(base_delay * (2 ** (attempt - 1)) + random.uniform(0.1, 0.5), max_delay)
                    logger.warning(
                        "http_server_error",
                        caller=caller_tag,
                        status=status_code,
                        url=url,
                        attempt=attempt,
                        wait_sec=round(wait_sec, 2),
                    )
                    if attempt < max_retries:
                        await asyncio.sleep(wait_sec)
                        continue
                    return HTTPResult(
                        status_code=status_code,
                        text=response.text,
                        headers=resp_headers,
                        error=f"SERVER_ERROR_{status_code}",
                        attempt_count=attempt,
                    )

                # Other client errors (404, 400, etc.)
                logger.warning(
                    "http_client_error",
                    caller=caller_tag,
                    status_code=status_code,
                    url=url,
                )
                return HTTPResult(
                    status_code=status_code,
                    text=response.text,
                    headers=resp_headers,
                    error=f"CLIENT_ERROR_{status_code}",
                    attempt_count=attempt,
                )

        except (httpx.TimeoutException, httpx.NetworkError) as e:
            wait_sec = min(base_delay * (2 ** (attempt - 1)) + random.uniform(0.1, 0.5), max_delay)
            logger.warning(
                "http_transient_error",
                caller=caller_tag,
                error=str(e),
                url=url,
                attempt=attempt,
                wait_sec=round(wait_sec, 2),
            )
            if attempt == max_retries:
                return HTTPResult(
                    status_code=0,
                    text="",
                    error=str(e),
                    attempt_count=attempt,
                )
            await asyncio.sleep(wait_sec)

        except Exception as e:
            logger.error(
                "http_fetch_fatal_error",
                caller=caller_tag,
                error=str(e),
                url=url,
                attempt=attempt,
            )
            return HTTPResult(
                status_code=0,
                text="",
                error=str(e),
                attempt_count=attempt,
            )

    return HTTPResult(status_code=0, text="", error="MAX_RETRIES_EXCEEDED", attempt_count=max_retries)


async def resilient_fetch_text(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
    max_retries: int = 3,
    base_delay: float = 1.0,
    follow_redirects: bool = True,
    caller_tag: str = "http_client",
) -> str | None:
    """Convenience helper that returns the text body on 200 OK, or None on failure."""
    res = await resilient_fetch(
        url,
        headers=headers,
        timeout=timeout,
        max_retries=max_retries,
        base_delay=base_delay,
        follow_redirects=follow_redirects,
        caller_tag=caller_tag,
    )
    return res.text if res.is_success else None
