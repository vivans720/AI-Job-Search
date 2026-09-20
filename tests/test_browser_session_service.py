import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from app.services.browser_session_service import BrowserSessionService, SUPPORTED_PLATFORMS


def test_supported_platforms_metadata():
    assert "linkedin" in SUPPORTED_PLATFORMS
    assert "naukri" in SUPPORTED_PLATFORMS
    assert SUPPORTED_PLATFORMS["linkedin"]["name"] == "LinkedIn"
    assert SUPPORTED_PLATFORMS["naukri"]["name"] == "Naukri"


def test_get_session_status_unsupported():
    res = BrowserSessionService.get_session_status("unsupported_portal")
    assert res["supported"] is False
    assert "Unsupported platform" in res["error"]


def test_get_session_status_disconnected(tmp_path):
    with patch("app.services.browser_session_service.settings") as mock_settings:
        mock_settings.BROWSER_PROFILE_ROOT = str(tmp_path)
        mock_settings.BROWSER_LINKEDIN_ENABLED = False

        status = BrowserSessionService.get_session_status("linkedin")
        assert status["platform"] == "linkedin"
        assert status["supported"] is True
        assert status["enabled"] is False
        assert status["connected"] is False
        assert status["mode"] == "public_discovery_default"


def test_get_session_status_connected_when_stored_and_enabled(tmp_path):
    with patch("app.services.browser_session_service.settings") as mock_settings:
        mock_settings.BROWSER_PROFILE_ROOT = str(tmp_path)
        mock_settings.BROWSER_LINKEDIN_ENABLED = True

        profile_dir = tmp_path / "linkedin" / "Default"
        profile_dir.mkdir(parents=True, exist_ok=True)
        (profile_dir / "Cookies").write_text("dummy_cookie_db")

        status = BrowserSessionService.get_session_status("linkedin")
        assert status["connected"] is True
        assert status["has_stored_session"] is True
        assert status["mode"] == "authenticated"


def test_get_all_sessions_status(tmp_path):
    with patch("app.services.browser_session_service.settings") as mock_settings:
        mock_settings.BROWSER_PROFILE_ROOT = str(tmp_path)
        mock_settings.BROWSER_LINKEDIN_ENABLED = False
        mock_settings.BROWSER_NAUKRI_ENABLED = False

        all_res = BrowserSessionService.get_all_sessions_status()
        assert all_res["status"] == "ok"
        assert all_res["default_mode"] == "public_discovery"
        assert "linkedin" in all_res["sessions"]
        assert "naukri" in all_res["sessions"]


def test_disconnect_session(tmp_path):
    with patch("app.services.browser_session_service.settings") as mock_settings:
        mock_settings.BROWSER_PROFILE_ROOT = str(tmp_path)

        profile_dir = tmp_path / "linkedin" / "Default"
        profile_dir.mkdir(parents=True, exist_ok=True)
        cookie_file = profile_dir / "Cookies"
        cookie_file.write_text("session_data")
        assert cookie_file.exists()

        res = BrowserSessionService.disconnect_session("linkedin")
        assert res["status"] == "ok"
        assert res["disconnected"] is True
        assert not cookie_file.exists()


@pytest.mark.asyncio
async def test_verify_session_passive_fallback(tmp_path):
    with patch("app.services.browser_session_service.settings") as mock_settings:
        mock_settings.BROWSER_PROFILE_ROOT = str(tmp_path)
        res = await BrowserSessionService.verify_platform_session("linkedin")
        assert res["status"] == "ok"
        assert res["platform"] == "linkedin"
