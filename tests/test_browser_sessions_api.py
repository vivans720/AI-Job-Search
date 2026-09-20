import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch
from app.main import app


@pytest.mark.asyncio
async def test_get_browser_sessions_endpoint(tmp_path):
    with patch("app.services.browser_session_service.settings") as mock_settings:
        mock_settings.BROWSER_PROFILE_ROOT = str(tmp_path)
        mock_settings.BROWSER_LINKEDIN_ENABLED = False
        mock_settings.BROWSER_NAUKRI_ENABLED = False

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.get("/api/v1/browser/sessions")
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "ok"
            assert data["default_mode"] == "public_discovery"
            assert "linkedin" in data["sessions"]
            assert data["sessions"]["linkedin"]["connected"] is False


@pytest.mark.asyncio
async def test_get_platform_session_status_endpoint(tmp_path):
    with patch("app.services.browser_session_service.settings") as mock_settings:
        mock_settings.BROWSER_PROFILE_ROOT = str(tmp_path)
        mock_settings.BROWSER_LINKEDIN_ENABLED = True

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.get("/api/v1/browser/sessions/linkedin/status")
            assert res.status_code == 200
            data = res.json()
            assert data["platform"] == "linkedin"
            assert data["supported"] is True

            # Unsupported platform
            bad_res = await ac.get("/api/v1/browser/sessions/unknown_platform/status")
            assert bad_res.status_code == 404


@pytest.mark.asyncio
async def test_disconnect_browser_session_endpoint(tmp_path):
    with patch("app.services.browser_session_service.settings") as mock_settings:
        mock_settings.BROWSER_PROFILE_ROOT = str(tmp_path)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post("/api/v1/browser/sessions/linkedin/disconnect")
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "ok"
            assert data["disconnected"] is True
