import asyncio
import json
from pathlib import Path
import time
from typing import Any
import httpx
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

SESSION_DIR = Path(__file__).resolve().parent.parent / "data" / "sessions"
SESSION_DIR.mkdir(parents=True, exist_ok=True)


class GuestSessionManager:
    """
    Manages zero-login anonymous visitor cookies and headers.
    Avoids user account bans by generating and refreshing valid guest cookies
    (e.g., bcookie, JSESSIONID, csrf tokens) using standard public entrypoints.
    """

    def __init__(self, source_name: str):
        self.source_name = source_name.lower()
        self.session_file = SESSION_DIR / f"{self.source_name}_guest_state.json"
        self._cached_cookies: dict[str, str] = {}
        self._last_refreshed: float = 0.0
        self._ttl: float = 3600 * 6  # 6 hour validity

    def load_cached_cookies(self) -> dict[str, str]:
        if self._cached_cookies and (time.time() - self._last_refreshed < self._ttl):
            return self._cached_cookies

        if self.session_file.exists():
            try:
                data = json.loads(self.session_file.read_text(encoding="utf-8"))
                saved_time = data.get("saved_at", 0)
                if time.time() - saved_time < self._ttl:
                    self._cached_cookies = data.get("cookies", {})
                    self._last_refreshed = saved_time
                    return self._cached_cookies
            except Exception as e:
                logger.warning("guest_session_read_failed", source=self.source_name, error=str(e))

        return {}

    def save_cookies(self, cookies: dict[str, str]):
        self._cached_cookies = cookies
        self._last_refreshed = time.time()
        try:
            payload = {
                "source": self.source_name,
                "saved_at": self._last_refreshed,
                "cookies": cookies,
            }
            self.session_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            logger.info("guest_session_saved", source=self.source_name, cookie_count=len(cookies))
        except Exception as e:
            logger.error("guest_session_save_error", source=self.source_name, error=str(e))

    async def get_valid_cookies(self) -> dict[str, str]:
        existing = self.load_cached_cookies()
        if existing:
            return existing

        return await self.refresh_guest_cookies()

    async def refresh_guest_cookies(self) -> dict[str, str]:
        """Bootstrap fresh guest session tokens from public homepage / entrypoints."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
        }

        cookies: dict[str, str] = {}
        try:
            async with httpx.AsyncClient(headers=headers, timeout=12.0, follow_redirects=True) as client:
                if self.source_name == "linkedin":
                    resp = await client.get("https://www.linkedin.com/jobs")
                    for k, v in resp.cookies.items():
                        cookies[k] = v
                    if "JSESSIONID" not in cookies:
                        cookies["JSESSIONID"] = f'"ajax:{int(time.time() * 1000)}"'

                elif self.source_name == "naukri":
                    resp = await client.get("https://www.naukri.com")
                    for k, v in resp.cookies.items():
                        cookies[k] = v

                elif self.source_name == "internshala":
                    resp = await client.get("https://internshala.com")
                    for k, v in resp.cookies.items():
                        cookies[k] = v

            if cookies:
                self.save_cookies(cookies)
        except Exception as e:
            logger.warning("guest_session_bootstrap_failed", source=self.source_name, error=str(e))

        return cookies


_guest_managers: dict[str, GuestSessionManager] = {}

def get_guest_session_manager(source_name: str) -> GuestSessionManager:
    source = source_name.lower()
    if source not in _guest_managers:
        _guest_managers[source] = GuestSessionManager(source)
    return _guest_managers[source]
