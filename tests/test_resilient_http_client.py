import pytest
from unittest.mock import AsyncMock, patch
import httpx
from app.utils.http_client import resilient_fetch, resilient_fetch_text, HTTPResult


@pytest.mark.asyncio
async def test_resilient_fetch_200_ok():
    mock_response = httpx.Response(
        status_code=200,
        text="<html>Success</html>",
        headers={"content-type": "text/html"},
        request=httpx.Request("GET", "https://example.com"),
    )

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=mock_response):
        result = await resilient_fetch("https://example.com", max_retries=2)
        assert result.is_success is True
        assert result.status_code == 200
        assert result.text == "<html>Success</html>"
        assert result.is_blocked is False
        assert result.is_rate_limited is False

        # Verify tuple unpacking support
        status, body = result
        assert status == 200
        assert body == "<html>Success</html>"


@pytest.mark.asyncio
async def test_resilient_fetch_anti_bot_blocked():
    mock_response = httpx.Response(
        status_code=403,
        text="Cloudflare / Captcha Blocked",
        headers={"content-type": "text/html"},
        request=httpx.Request("GET", "https://example.com"),
    )

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=mock_response):
        result = await resilient_fetch("https://example.com", max_retries=3)
        assert result.is_success is False
        assert result.is_blocked is True
        assert result.status_code == 403
        assert result.error == "ANTI_BOT_BLOCKED"


@pytest.mark.asyncio
async def test_resilient_fetch_rate_limit_retry():
    rate_limit_resp = httpx.Response(
        status_code=429,
        text="Too many requests",
        request=httpx.Request("GET", "https://example.com"),
    )
    ok_resp = httpx.Response(
        status_code=200,
        text="Recovered",
        request=httpx.Request("GET", "https://example.com"),
    )

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, side_effect=[rate_limit_resp, ok_resp]):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await resilient_fetch("https://example.com", max_retries=3, base_delay=0.01)
            assert result.is_success is True
            assert result.status_code == 200
            assert result.text == "Recovered"
            assert result.attempt_count == 2


@pytest.mark.asyncio
async def test_resilient_fetch_text_convenience():
    ok_resp = httpx.Response(
        status_code=200,
        text="Job Content",
        request=httpx.Request("GET", "https://example.com"),
    )

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=ok_resp):
        text = await resilient_fetch_text("https://example.com")
        assert text == "Job Content"
