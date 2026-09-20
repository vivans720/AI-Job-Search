import sys
from pathlib import Path
from typing import Any

backend_dir = Path(__file__).resolve().parent.parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.services.browser_session_service import BrowserSessionService


async def handle_get_browser_session_status(
    platform: str | None = None,
) -> dict[str, Any]:
    """
    Phase 11: Inspects authenticated browser session status for job portals.
    If platform is provided ('linkedin' or 'naukri'), checks that platform;
    otherwise returns status for all supported platforms.
    """
    if platform:
        return BrowserSessionService.get_session_status(platform)
    return BrowserSessionService.get_all_sessions_status()


async def handle_verify_browser_session(
    platform: str,
    timeout_seconds: int = 20,
) -> dict[str, Any]:
    """
    Phase 11: Actively verifies whether saved browser session cookies for a platform
    remain valid or have expired.
    """
    return await BrowserSessionService.verify_platform_session(
        platform=platform,
        timeout_seconds=timeout_seconds,
    )


async def handle_disconnect_browser_session(
    platform: str,
) -> dict[str, Any]:
    """
    Phase 11: Disconnects authenticated session by flushing cookies and profile storage.
    Public discovery continues without interruption.
    """
    return BrowserSessionService.disconnect_session(platform)
