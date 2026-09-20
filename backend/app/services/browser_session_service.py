import asyncio
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

SUPPORTED_PLATFORMS = {
    "linkedin": {
        "name": "LinkedIn",
        "login_url": "https://www.linkedin.com/login",
        "home_url": "https://www.linkedin.com/feed/",
        "cookie_names": ["li_at", "JSESSIONID"],
        "auth_indicators": ["div.feed-identity-module", "img.global-nav__me-photo", "nav.global-nav"],
    },
    "naukri": {
        "name": "Naukri",
        "login_url": "https://www.naukri.com/nlogin/login",
        "home_url": "https://www.naukri.com/mnjuser/homepage",
        "cookie_names": ["nauk_auth", "user_id"],
        "auth_indicators": ["div.nI-gNb-drawer", "div.user-profile", "a.nI-gNb-header__logo"],
    },
}


class BrowserSessionService:
    """
    Phase 11: Service managing authenticated browser sessions for job portals (LinkedIn, Naukri).
    Maintains persistent Chromium profiles, inspects cookie/storage status, and manages opt-in state.
    """

    @staticmethod
    def get_profile_dir(platform: str) -> Path:
        """Returns isolated user profile directory path for given platform."""
        platform_key = platform.lower().strip()
        root_dir = Path(os.path.expanduser(settings.BROWSER_PROFILE_ROOT)).resolve()
        profile_path = root_dir / platform_key
        profile_path.mkdir(parents=True, exist_ok=True)
        return profile_path

    @staticmethod
    def is_platform_enabled(platform: str) -> bool:
        """Checks if authenticated browser mode is enabled in configuration for platform."""
        platform_key = platform.lower().strip()
        if platform_key == "linkedin":
            return getattr(settings, "BROWSER_LINKEDIN_ENABLED", False)
        if platform_key == "naukri":
            return getattr(settings, "BROWSER_NAUKRI_ENABLED", False)
        return False

    @staticmethod
    def get_session_status(platform: str) -> dict[str, Any]:
        """
        Inspects directory presence and storage artifacts (Cookies, Network, Session Storage)
        to evaluate whether a browser session has been saved for the platform.
        """
        platform_key = platform.lower().strip()
        meta = SUPPORTED_PLATFORMS.get(platform_key)
        if not meta:
            return {
                "platform": platform_key,
                "supported": False,
                "error": f"Unsupported platform '{platform}'. Supported: {list(SUPPORTED_PLATFORMS.keys())}",
            }

        profile_dir = BrowserSessionService.get_profile_dir(platform_key)
        enabled = BrowserSessionService.is_platform_enabled(platform_key)

        # Look for typical Chromium storage files
        # Default/Network/Cookies or Default/Cookies
        has_network_dir = (profile_dir / "Default" / "Network").exists() or (profile_dir / "Default").exists()
        cookies_db = (
            (profile_dir / "Default" / "Network" / "Cookies").exists()
            or (profile_dir / "Default" / "Cookies").exists()
        )
        session_storage = (
            (profile_dir / "Default" / "Session Storage").exists()
            or (profile_dir / "Default" / "Local Storage").exists()
        )

        has_session_files = cookies_db or session_storage
        connected = has_session_files and enabled

        last_modified = None
        if has_session_files:
            try:
                # Find newest file modification time
                newest_mtime = 0.0
                for f in profile_dir.rglob("*"):
                    if f.is_file():
                        mtime = f.stat().st_mtime
                        if mtime > newest_mtime:
                            newest_mtime = mtime
                if newest_mtime > 0:
                    last_modified = datetime.fromtimestamp(newest_mtime, tz=timezone.utc).isoformat()
            except Exception:
                pass

        return {
            "platform": platform_key,
            "display_name": meta["name"],
            "supported": True,
            "enabled": enabled,
            "connected": connected,
            "has_stored_session": has_session_files,
            "profile_dir": str(profile_dir),
            "last_active_at": last_modified,
            "login_url": meta["login_url"],
            "mode": "authenticated" if connected else "public_discovery_default",
        }

    @staticmethod
    def get_all_sessions_status() -> dict[str, Any]:
        """Returns session connection status across all supported platforms."""
        statuses = {}
        for p in SUPPORTED_PLATFORMS:
            statuses[p] = BrowserSessionService.get_session_status(p)
        return {
            "status": "ok",
            "default_mode": "public_discovery",
            "sessions": statuses,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    async def verify_platform_session(
        platform: str,
        timeout_seconds: int = 20,
    ) -> dict[str, Any]:
        """
        Launches headless persistent context targeting home feed to verify if session remains authenticated.
        Falls back to passive heuristic inspection if Playwright binary is not found.
        """
        platform_key = platform.lower().strip()
        meta = SUPPORTED_PLATFORMS.get(platform_key)
        if not meta:
            return {"status": "error", "error": f"Unsupported platform '{platform}'"}

        profile_dir = BrowserSessionService.get_profile_dir(platform_key)
        has_session_files = (profile_dir / "Default").exists()

        try:
            from playwright.async_api import async_playwright
            from app.utils.browser_stealth import DEFAULT_STEALTH_USER_AGENT, apply_stealth_context

            async with async_playwright() as pw:
                launch_args = [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--no-first-run",
                    "--no-default-browser-check",
                ]
                context = await pw.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    headless=True,
                    args=launch_args,
                    user_agent=DEFAULT_STEALTH_USER_AGENT,
                )
                await apply_stealth_context(context)
                page = context.pages[0] if context.pages else await context.new_page()

                logger.info("verifying_browser_session", platform=platform_key, url=meta["home_url"])
                response = await page.goto(
                    meta["home_url"],
                    timeout=timeout_seconds * 1000,
                    wait_until="domcontentloaded",
                )
                current_url = page.url
                page_title = await page.title()

                # Evaluate auth status: Did it redirect to login or show auth indicators?
                is_login_redirect = "login" in current_url.lower() or "signin" in current_url.lower()

                has_auth_el = False
                for sel in meta["auth_indicators"]:
                    try:
                        el = await page.query_selector(sel)
                        if el:
                            has_auth_el = True
                            break
                    except Exception:
                        continue

                await context.close()

                is_authenticated = (not is_login_redirect) and (has_auth_el or response and response.status == 200)

                return {
                    "status": "ok",
                    "platform": platform_key,
                    "authenticated": is_authenticated,
                    "current_url": current_url,
                    "page_title": page_title,
                    "session_expired": is_login_redirect,
                    "verified_at": datetime.now(timezone.utc).isoformat(),
                }
        except Exception as e:
            logger.warning("verify_browser_session_fallback", platform=platform_key, error=str(e))
            # Passive fallback based on file presence
            return {
                "status": "ok",
                "platform": platform_key,
                "authenticated": has_session_files,
                "note": "Verified heuristically via local profile storage files.",
                "verified_at": datetime.now(timezone.utc).isoformat(),
            }

    @staticmethod
    def disconnect_session(platform: str) -> dict[str, Any]:
        """
        Disconnects authenticated session by clearing cookies and storage files from profile directory.
        Leaves public discovery unaffected.
        """
        platform_key = platform.lower().strip()
        if platform_key not in SUPPORTED_PLATFORMS:
            return {"status": "error", "error": f"Unsupported platform '{platform}'"}

        profile_dir = BrowserSessionService.get_profile_dir(platform_key)
        try:
            if profile_dir.exists():
                shutil.rmtree(profile_dir)
                profile_dir.mkdir(parents=True, exist_ok=True)

            logger.info("browser_session_disconnected", platform=platform_key, dir=str(profile_dir))
            return {
                "status": "ok",
                "platform": platform_key,
                "disconnected": True,
                "message": f"Successfully cleared browser session for {platform_key.capitalize()}.",
            }
        except Exception as e:
            logger.error("browser_session_disconnect_failed", platform=platform_key, error=str(e))
            return {
                "status": "error",
                "platform": platform_key,
                "error": f"Failed to remove profile directory: {str(e)}",
            }
