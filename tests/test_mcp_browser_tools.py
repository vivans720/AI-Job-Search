import sys
from pathlib import Path
import pytest
from unittest.mock import patch

mcp_dir = Path(__file__).resolve().parent.parent / "mcp-server"
if str(mcp_dir) not in sys.path:
    sys.path.insert(0, str(mcp_dir))

from server import server
from tools.browser_tools import (
    handle_get_browser_session_status,
    handle_verify_browser_session,
    handle_disconnect_browser_session,
)


@pytest.mark.asyncio
async def test_mcp_browser_session_tools_registration():
    """Verify Phase 11 browser session tools are registered on server."""
    tools = [t.name for t in server._tool_manager.list_tools()]
    assert "get_browser_session_status" in tools
    assert "verify_browser_session" in tools
    assert "disconnect_browser_session" in tools


@pytest.mark.asyncio
async def test_mcp_get_browser_session_status():
    status = await handle_get_browser_session_status()
    assert status["status"] == "ok"
    assert status["default_mode"] == "public_discovery"
    assert "linkedin" in status["sessions"]
    assert "naukri" in status["sessions"]

    li_status = await handle_get_browser_session_status(platform="linkedin")
    assert li_status["platform"] == "linkedin"
    assert li_status["supported"] is True


@pytest.mark.asyncio
async def test_mcp_verify_and_disconnect_browser_session(tmp_path):
    with patch("app.services.browser_session_service.settings") as mock_settings:
        mock_settings.BROWSER_PROFILE_ROOT = str(tmp_path)
        ver = await handle_verify_browser_session(platform="linkedin")
        assert ver["status"] == "ok"
        assert ver["platform"] == "linkedin"

        disc = await handle_disconnect_browser_session(platform="linkedin")
        assert disc["status"] == "ok"
        assert disc["disconnected"] is True
